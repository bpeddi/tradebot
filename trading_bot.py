"""Moving average crossover trading bot for Alpaca paper trading.

Runs independently for each configured symbol: fetches recent daily bars
from TastyTrade, computes a short/long exponential moving average (EMA)
pair, and places a market order through Alpaca when a real crossover
occurred on the most recent bar (short EMA crossing above or below the long
EMA). Buys invest a fixed dollar amount per symbol via a notional
(fractional-share) order when flat; a bearish crossover closes out the full
existing position. A failure on one symbol (e.g. no data returned) doesn't
stop the others from running.
"""
import asyncio
import contextlib
import io
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from dotenv import load_dotenv
from tastytrade import DXLinkStreamer, Session
from tastytrade.dxfeed import Candle

load_dotenv()

# Where config.json / state.json / trades.db live. Defaults to the repo root
# (today's behavior, unchanged for local dev); in Docker this is set to a
# bind-mounted volume so edits made through the dashboard and the bot's own
# trade history survive container redeploys.
DATA_DIR = os.environ.get("MYTRADEBOT_DATA_DIR", ".")


def _data_path(filename):
    return os.path.join(DATA_DIR, filename)


def load_config(path=None):
    with open(path or _data_path("config.json")) as f:
        return json.load(f)


def load_state(path=None):
    """Per-symbol persisted state (currently just whether a symbol's cold-start
    check has already run), so restarting the bot doesn't re-trigger it."""
    try:
        with open(path or _data_path("state.json")) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state, path=None):
    with open(path or _data_path("state.json"), "w") as f:
        json.dump(state, f, indent=2)


def _ensure_column(conn, table, column, col_type):
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db(path=None):
    """Local trade log — one row per order placed, for a future P&L dashboard.
    check_same_thread=False: callers (e.g. the web backend) may open a
    connection in one thread and use it in another within the same request."""
    conn = sqlite3.connect(path or _data_path("trades.db"), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id          TEXT UNIQUE,
            symbol            TEXT NOT NULL,
            side              TEXT NOT NULL,
            qty               REAL,
            notional          REAL,
            filled_qty        REAL,
            filled_avg_price  REAL,
            status            TEXT,
            reason            TEXT,
            submitted_at      TEXT,
            recorded_at       TEXT NOT NULL,
            synced_at         TEXT
        )
    """)
    # Migrate older trades.db files that predate filled_qty/synced_at.
    _ensure_column(conn, "trades", "filled_qty", "REAL")
    _ensure_column(conn, "trades", "synced_at", "TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            symbol        TEXT PRIMARY KEY,
            close         REAL,
            short_ma      REAL,
            long_ma       REAL,
            distance_pct  REAL,
            signal        TEXT,
            evaluated_at  TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at    TEXT NOT NULL,
            finished_at   TEXT NOT NULL,
            status        TEXT NOT NULL,
            error_message TEXT,
            log           TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def log_run(conn, started_at, finished_at, status, error_message, log_text, keep_last=200):
    """Persist one full run's outcome (success/partial/error) and captured
    console output — written regardless of what triggered the run (cron,
    the web UI's Run Bot Now, or a direct CLI invocation), so the dashboard
    can always show 'was the last run OK' without depending on cron.log."""
    conn.execute(
        """
        INSERT INTO runs (started_at, finished_at, status, error_message, log)
        VALUES (?, ?, ?, ?, ?)
        """,
        (started_at, finished_at, status, error_message, log_text),
    )
    # Light retention: keep only the most recent N runs so trades.db doesn't
    # grow unbounded over months of twice-daily runs.
    conn.execute(
        "DELETE FROM runs WHERE id NOT IN (SELECT id FROM runs ORDER BY id DESC LIMIT ?)",
        (keep_last,),
    )
    conn.commit()


def log_evaluation(conn, evaluation):
    """Persist the latest EMA crossover snapshot for a symbol — every bot run
    (scheduled or manual) overwrites this row, so the dashboard can show
    'last run' data without a live TastyTrade call."""
    conn.execute(
        """
        INSERT INTO watchlist (symbol, close, short_ma, long_ma, distance_pct, signal, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            close=excluded.close, short_ma=excluded.short_ma, long_ma=excluded.long_ma,
            distance_pct=excluded.distance_pct, signal=excluded.signal, evaluated_at=excluded.evaluated_at
        """,
        (
            evaluation["symbol"],
            evaluation["close"],
            evaluation["short_ma"],
            evaluation["long_ma"],
            evaluation["distance_pct"],
            evaluation["signal"],
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def log_trade(conn, symbol, side, order, reason):
    conn.execute(
        """
        INSERT OR REPLACE INTO trades
            (order_id, symbol, side, qty, notional, filled_qty, filled_avg_price,
             status, reason, submitted_at, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order.get("id"),
            symbol,
            side,
            float(order["qty"]) if order.get("qty") else None,
            float(order["notional"]) if order.get("notional") else None,
            float(order["filled_qty"]) if order.get("filled_qty") else None,
            float(order["filled_avg_price"]) if order.get("filled_avg_price") else None,
            order.get("status"),
            reason,
            order.get("submitted_at"),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


# Alpaca order statuses that mean "still open — keep polling for a fill."
_OPEN_ORDER_STATUSES = (
    "new", "accepted", "pending_new", "accepted_for_bidding",
    "partially_filled", "pending_cancel", "pending_replace", "calculated",
)


def sync_fills(conn):
    """Check every locally-logged order that isn't in a terminal state yet against
    Alpaca, and update its fill status/qty/price. Run this before evaluating new
    signals so position checks and the trade log both reflect real fills."""
    placeholders = ",".join("?" * len(_OPEN_ORDER_STATUSES))
    rows = conn.execute(
        f"SELECT order_id FROM trades WHERE status IN ({placeholders})",
        _OPEN_ORDER_STATUSES,
    ).fetchall()

    updated = 0
    for (order_id,) in rows:
        try:
            resp = requests.get(
                f"{alpaca_endpoint()}/orders/{order_id}",
                headers=alpaca_headers(), timeout=10,
            )
            resp.raise_for_status()
            order = resp.json()
        except Exception as exc:
            print(f"Sync: failed to fetch order {order_id}: {exc}", file=sys.stderr)
            continue

        conn.execute(
            """
            UPDATE trades
            SET status=?, filled_qty=?, filled_avg_price=?, synced_at=?
            WHERE order_id=?
            """,
            (
                order.get("status"),
                float(order["filled_qty"]) if order.get("filled_qty") else None,
                float(order["filled_avg_price"]) if order.get("filled_avg_price") else None,
                datetime.now(timezone.utc).isoformat(),
                order_id,
            ),
        )
        updated += 1

    conn.commit()
    if updated:
        print(f"Synced fill status for {updated} pending order(s).")
    return updated


def alpaca_headers():
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        print("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env", file=sys.stderr)
        sys.exit(1)
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }


def alpaca_endpoint():
    return os.environ.get("ALPACA_END_POINT", "https://paper-api.alpaca.markets/v2").rstrip("/")


async def fetch_price_data(symbol, lookback_days, candle_interval):
    """Fetch recent OHLCV bars for symbol via TastyTrade's dxfeed Candle stream."""
    start_time = datetime.now() - timedelta(days=lookback_days)
    rows = {}

    async with Session(
        provider_secret=os.environ["TT_SECRET"],
        refresh_token=os.environ["TT_REFRESH"],
    ) as session:
        async with DXLinkStreamer(session) as streamer:
            await streamer.subscribe_candle([symbol], interval=candle_interval, start_time=start_time)
            while True:
                candle = await asyncio.wait_for(streamer.get_event(Candle), timeout=15)
                if not candle.remove:
                    ts = datetime.fromtimestamp(candle.time / 1000)
                    rows[ts] = {
                        "Open": float(candle.open),
                        "High": float(candle.high),
                        "Low": float(candle.low),
                        "Close": float(candle.close),
                        "Volume": float(candle.volume or 0),
                    }
                if candle.snapshot_end or candle.snapshot_snip:
                    break

    if not rows:
        raise RuntimeError(f"No price data returned for {symbol}")

    data = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    data.index = pd.to_datetime(data.index)
    return data


def compute_crossover(data, short_window, long_window):
    data = data.copy()
    data["short_ma"] = data["Close"].ewm(span=short_window, adjust=False).mean()
    data["long_ma"] = data["Close"].ewm(span=long_window, adjust=False).mean()
    # EMA has no warm-up NaNs, so trim the first long_window-1 rows instead,
    # matching the minimum-history requirement the old SMA-based dropna gave.
    data = data.iloc[long_window - 1:]

    if len(data) < 2:
        return None, data

    prev_short, prev_long = data["short_ma"].iloc[-2], data["long_ma"].iloc[-2]
    curr_short, curr_long = data["short_ma"].iloc[-1], data["long_ma"].iloc[-1]

    if prev_short <= prev_long and curr_short > curr_long:
        return "bullish", data
    if prev_short >= prev_long and curr_short < curr_long:
        return "bearish", data
    return None, data


def get_position_qty(symbol):
    """Return the exact position qty string from Alpaca, or None if flat."""
    url = f"{alpaca_endpoint()}/positions/{symbol}"
    resp = requests.get(url, headers=alpaca_headers(), timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()["qty"]


def get_all_positions():
    """Return every open Alpaca position, including Alpaca's own unrealized P&L."""
    url = f"{alpaca_endpoint()}/positions"
    resp = requests.get(url, headers=alpaca_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_open_orders():
    """Return every order that hasn't filled/canceled/expired yet. A symbol
    with an open buy order has capital committed to it even though it isn't
    a position yet — slot accounting and duplicate-buy checks both need to
    treat that the same as an actual open position."""
    url = f"{alpaca_endpoint()}/orders"
    resp = requests.get(url, headers=alpaca_headers(), params={"status": "open", "limit": 500}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def place_order(symbol, side, qty=None, notional=None):
    url = f"{alpaca_endpoint()}/orders"
    body = {
        "symbol": symbol,
        "side": side,
        "type": "market",
        "time_in_force": "day",
    }
    if notional is not None:
        body["notional"] = str(notional)
    else:
        body["qty"] = str(qty)
    resp = requests.post(url, headers=alpaca_headers(), json=body, timeout=10)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Order failed: {resp.status_code} {resp.text}")
    return resp.json()


async def evaluate_symbol(symbol, short_window, long_window, lookback_days, candle_interval, since_ts=None):
    """Fetch price data and compute the EMA crossover signal for symbol.
    Read-only — no Alpaca calls, no state/order side effects. Used both by
    process_symbol and by the dashboard's watchlist preview.

    distance_pct is how far the short EMA is from the long EMA, as a percent
    of the long EMA: positive means short > long (bullish side), negative
    means short < long (bearish side); magnitude near 0 means close to a
    crossover either way.

    since_ts (optional): an ISO timestamp of a bar to count forward from —
    used by the re-arm rule to know how many bars have closed since a
    symbol was last sold. Only included in the result (as bars_since) when
    passed, so callers that don't care about it (e.g. the dashboard's
    watchlist preview) don't pay for the extra computation."""
    data = await fetch_price_data(symbol, lookback_days, candle_interval)
    signal, data = compute_crossover(data, short_window, long_window)
    latest = data.iloc[-1]
    short_ma = float(latest["short_ma"])
    long_ma = float(latest["long_ma"])
    distance_pct = (short_ma - long_ma) / long_ma * 100 if long_ma else 0.0
    result = {
        "symbol": symbol,
        "close": float(latest["Close"]),
        "short_ma": short_ma,
        "long_ma": long_ma,
        "distance_pct": distance_pct,
        "signal": signal,
        "bar_ts": latest.name.isoformat(),
    }
    if since_ts:
        # data.index is timezone-naive (fetch_price_data builds it via
        # datetime.fromtimestamp with no tz). since_ts is normally naive too
        # (bar_ts above is stored the same way), but can arrive as a
        # timezone-aware ISO string (e.g. backfilled from Alpaca's
        # submitted_at, which has a trailing 'Z') — strip tzinfo so the
        # comparison doesn't raise.
        since = pd.Timestamp(since_ts)
        if since.tzinfo is not None:
            since = since.tz_localize(None)
        result["bars_since"] = int((data.index > since).sum())
    return result


async def process_symbol(symbol, short_window, long_window, lookback_days,
                          candle_interval, per_slot_amount, max_slots, slots_used,
                          committed_symbols, rotatable_positions, rotation_weakness_pct,
                          rotation_enabled, state, conn):
    """Evaluate one symbol and, if warranted, buy/sell it. Sells never are
    slot-gated, since a sell only ever frees a slot. A bullish signal when
    the portfolio is full rotates: among held positions that are ALSO
    showing technical weakness (price below its own short EMA, or distance
    to crossover under rotation_weakness_pct — including already negative,
    i.e. already past its own crossover without a fresh-cross bar catching
    it), the weakest by unrealized P&L % is sold to fund the new buy.
    Deliberately does *not* just sell "whichever position has the lowest
    dollar return" — a position having a one-day dip inside an otherwise
    intact uptrend isn't technically weak, and selling it anyway means
    exiting winners for no chart-based reason. If no position both exists
    and qualifies as weak (portfolio "full" only via unfilled orders, or
    every held position still looks technically healthy), the buy is
    skipped instead. Returns the net slot delta this call caused, which the
    caller accumulates into a running slots_used count as it walks the
    symbol list top to bottom."""
    print(f"\n=== {symbol} ===")
    print(f"Fetching last {lookback_days} days of {symbol} {candle_interval} data from TastyTrade...")
    prior = state.get(symbol, {})
    sold_bar_ts = prior.get("sold_bar_ts")
    evaluation = await evaluate_symbol(symbol, short_window, long_window, lookback_days, candle_interval,
                                        since_ts=sold_bar_ts)
    signal = evaluation["signal"]
    log_evaluation(conn, evaluation)

    print(f"Latest close:     {evaluation['close']:.2f}")
    print(f"Short MA({short_window}):  {evaluation['short_ma']:.2f}")
    print(f"Long MA({long_window}):   {evaluation['long_ma']:.2f}")
    print(f"Distance to crossover: {evaluation['distance_pct']:+.2f}%")

    is_first_run = symbol not in state
    reason = f"ema_crossover_{signal}" if signal else None
    is_cold_start_candidate = False
    is_rearm_candidate = False
    if signal is None and is_first_run and evaluation["short_ma"] > evaluation["long_ma"]:
        print(f"First run for {symbol}: already in an uptrend (short EMA > long EMA) "
              "— treating as an initial bullish entry.")
        signal = "bullish"
        reason = "cold_start_uptrend"
        is_cold_start_candidate = True

    # Re-arm: a symbol that was sold doesn't need a brand-new crossover flip
    # to get back in — if it's simply resumed the same uptrend it was sold
    # out of (no fresh cross, so a plain crossover check would never fire),
    # treat it like a fresh cold-start entry once a couple of bars have
    # closed since the sale. The 2-bar buffer avoids re-buying immediately
    # off the same bar/noise that triggered the sell.
    if (signal is None and not is_first_run and sold_bar_ts
            and evaluation["short_ma"] > evaluation["long_ma"]
            and evaluation.get("bars_since", 0) >= 2):
        print(f"{symbol}: {evaluation['bars_since']} bar(s) closed since it was last sold, and it's "
              "back in an uptrend (short EMA > long EMA) with no fresh crossover yet — re-arming as "
              "an entry signal.")
        signal = "bullish"
        reason = "rearm_after_sell"
        is_rearm_candidate = True

    # Mark initialized now for every outcome except one: a cold-start (or
    # re-arm) buy that gets skipped purely for lack of a free slot. That
    # symbol never actually got its entry, so it should stay eligible to
    # try again on a later run once a slot opens up — not be treated as
    # "done" just because it lost out on slot ordering this run. Merging
    # rather than replacing preserves sold_bar_ts across runs.
    state.setdefault(symbol, {})["initialized"] = True

    position_qty_str = get_position_qty(symbol)
    position_qty = float(position_qty_str) if position_qty_str is not None else 0.0
    print(f"Current position: {position_qty} shares")

    if signal is None:
        if position_qty > 0:
            print(f"No crossover on the latest bar. Already holding {symbol} — no action taken.")
        else:
            print("No crossover on the latest bar. No action taken.")
        return 0

    print(f"Crossover detected: {signal}")

    if signal == "bullish":
        if position_qty > 0 or symbol in committed_symbols:
            print("Already holding a position (or have an unfilled buy order pending). Skipping buy.")
            return 0

        retry_suffix = (" — will retry cold-start next run once a slot frees up." if is_cold_start_candidate
                         else " — will retry re-arm next run once a slot frees up." if is_rearm_candidate
                         else " — will retry next run.")

        rotation_sell_reason = None
        if slots_used >= max_slots:
            if not rotation_enabled:
                if is_cold_start_candidate:
                    del state[symbol]
                print(f"All portfolio slots are filled ({slots_used}/{max_slots}) and rotation is "
                      f"disabled for this instance (A/B comparison — slots only free up via a real "
                      f"bearish crossover sell). Skipping buy for {symbol}" + retry_suffix)
                return 0

            if not rotatable_positions:
                if is_cold_start_candidate:
                    del state[symbol]
                print(f"All portfolio slots are filled ({slots_used}/{max_slots}) and no open position "
                      f"is available to rotate out (full due to unfilled buy orders). "
                      f"Skipping buy for {symbol}" + retry_suffix)
                return 0

            # Only consider rotating out positions that are ALSO technically
            # weak — not just whichever has the smallest $ gain right now.
            # A single weak bar isn't enough to sell on, though: a position
            # mid-consolidation (close/short/long EMA all bunched together)
            # can trip this on routine noise without the trend actually
            # having turned — caught live in production (ZETA, +0.94%
            # distance and a few cents under its own short EMA, still
            # technically in an uptrend). So weakness must show up on two
            # separate evaluations (a new bar must have formed in between)
            # before a position is actually eligible to be sold; the first
            # time just flags it. A symbol that stops looking weak before
            # the second confirmation has its flag cleared, resetting the
            # streak rather than carrying a stale flag forward.
            weak_candidates = {}
            for candidate_symbol, pos in rotatable_positions.items():
                try:
                    cand_eval = await evaluate_symbol(
                        candidate_symbol, short_window, long_window, lookback_days, candle_interval
                    )
                except Exception as exc:
                    print(f"  Could not evaluate {candidate_symbol} for rotation weakness check: {exc}",
                          file=sys.stderr)
                    continue
                is_weak_now = (cand_eval["close"] < cand_eval["short_ma"]
                                or cand_eval["distance_pct"] < rotation_weakness_pct)
                cand_state = state.setdefault(candidate_symbol, {})
                flagged_bar_ts = cand_state.get("weak_flagged_bar_ts")
                if is_weak_now:
                    if flagged_bar_ts and flagged_bar_ts != cand_eval["bar_ts"]:
                        weak_candidates[candidate_symbol] = (pos, cand_eval)
                    else:
                        cand_state["weak_flagged_bar_ts"] = cand_eval["bar_ts"]
                        print(f"  {candidate_symbol} looks technically weak this bar "
                              f"(distance {cand_eval['distance_pct']:+.2f}%) — flagging for confirmation, "
                              f"not yet eligible to rotate out.")
                elif flagged_bar_ts:
                    del cand_state["weak_flagged_bar_ts"]

            if not weak_candidates:
                if is_cold_start_candidate:
                    del state[symbol]
                print(f"All portfolio slots are filled ({slots_used}/{max_slots}), but no held position "
                      f"has technical weakness confirmed over two separate runs (price below its own "
                      f"short EMA, or distance to crossover under {rotation_weakness_pct:.1f}%) to "
                      f"rotate out. Skipping buy for {symbol}" + retry_suffix)
                return 0

            weakest_symbol = min(
                weak_candidates, key=lambda s: float(weak_candidates[s][0]["unrealized_plpc"])
            )
            weakest, weakest_eval = weak_candidates[weakest_symbol]
            rotatable_positions.pop(weakest_symbol)
            weakest_pct = float(weakest["unrealized_plpc"]) * 100
            print(f"All {max_slots} portfolio slots are filled — rotating out technically weak "
                  f"holding {weakest_symbol} ({weakest_pct:+.2f}% unrealized) to free a slot for {symbol}.")
            sell_order = place_order(weakest_symbol, "sell", qty=weakest["qty"])
            rotation_sell_reason = f"rotated_out_for_{symbol}"
            log_trade(conn, weakest_symbol, sell_order.get("side"), sell_order, rotation_sell_reason)
            # Re-arm bookkeeping: the bar this rotation-sell happened on is
            # the baseline for weakest_symbol's own 2-bar re-arm wait. Also
            # clear its weak-confirmation flag — it's sold, the streak is moot.
            weakest_state = state.setdefault(weakest_symbol, {})
            weakest_state["sold_bar_ts"] = weakest_eval["bar_ts"]
            weakest_state.pop("weak_flagged_bar_ts", None)
            print(f"  Sold {weakest_symbol}: order {sell_order.get('id')}, status {sell_order.get('status')}")

        order = place_order(symbol, "buy", notional=per_slot_amount)
        delta = 0 if rotation_sell_reason else 1
        # Consumed the re-arm wait (if any) — a future sell will set a fresh one.
        state[symbol].pop("sold_bar_ts", None)
    else:
        if position_qty <= 0:
            print("No position to sell. Skipping sell.")
            return 0
        order = place_order(symbol, "sell", qty=position_qty_str)
        delta = -1
        state.setdefault(symbol, {})["sold_bar_ts"] = evaluation["bar_ts"]

    log_trade(conn, symbol, order.get("side"), order, reason)

    print("Order submitted.")
    print(f"Order ID:  {order.get('id')}")
    print(f"Side:      {order.get('side')}")
    print(f"Qty:       {order.get('qty')}")
    print(f"Notional:  {order.get('notional')}")
    print(f"Status:    {order.get('status')}")
    return delta


async def main_async():
    config = load_config()
    symbols = config["symbols"]
    candle_interval = config.get("candle_interval", "1d")
    short_window = config["short_window"]
    long_window = config["long_window"]
    lookback_days = config.get("lookback_days", 100)
    max_investment = config["max_investment"]
    max_slots = config["max_slots"]
    if max_slots < 1:
        raise ValueError("max_slots must be at least 1")
    per_slot_amount = round(max_investment / max_slots, 2)
    rotation_weakness_pct = config.get("rotation_weakness_pct", 1.0)
    rotation_enabled = config.get("rotation_enabled", True)

    state = load_state()
    conn = init_db()
    symbol_errors = []

    try:
        sync_fills(conn)

        try:
            positions = get_all_positions()
            open_orders = get_open_orders()
            committed_symbols = {p["symbol"] for p in positions} | \
                {o["symbol"] for o in open_orders if o.get("side") == "buy"}
            # Mutable pool of symbol -> position dict (needs qty + unrealized_plpc);
            # process_symbol pops from this when it rotates a weak holding out.
            rotatable_positions = {p["symbol"]: p for p in positions}
            slots_used = len(committed_symbols)
        except Exception as exc:
            print(f"Could not fetch current positions/orders to determine slot usage: {exc}", file=sys.stderr)
            committed_symbols = set()
            rotatable_positions = {}
            slots_used = 0

        print(f"\nPortfolio: {slots_used}/{max_slots} slots used (open positions + unfilled buy orders). "
              f"Per-slot commitment: ${per_slot_amount:,.2f} (${max_investment:,.2f} / {max_slots} slots)")

        for symbol in symbols:
            try:
                delta = await process_symbol(symbol, short_window, long_window, lookback_days,
                                              candle_interval, per_slot_amount, max_slots, slots_used,
                                              committed_symbols, rotatable_positions, rotation_weakness_pct,
                                              rotation_enabled, state, conn)
                slots_used += delta or 0
            except Exception as exc:
                msg = f"Error processing {symbol}: {exc}"
                print(msg, file=sys.stderr)
                symbol_errors.append(msg)
            save_state(state)
    finally:
        conn.close()

    return symbol_errors


class _Tee:
    """Mirrors writes to multiple streams — used to capture full console
    output for the run log while still printing normally."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
        return len(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def main():
    started_at = datetime.now(timezone.utc).isoformat()
    buffer = io.StringIO()
    status = "success"
    error_message = None

    try:
        with contextlib.redirect_stdout(_Tee(sys.stdout, buffer)), \
             contextlib.redirect_stderr(_Tee(sys.stderr, buffer)):
            symbol_errors = asyncio.run(main_async())
        if symbol_errors:
            status = "partial"
            error_message = "; ".join(symbol_errors)
    except Exception as exc:
        status = "error"
        error_message = str(exc)
        buffer.write(f"FATAL: {exc}\n")
        print(f"FATAL: {exc}", file=sys.stderr)

    finished_at = datetime.now(timezone.utc).isoformat()
    try:
        conn = init_db()
        log_run(conn, started_at, finished_at, status, error_message, buffer.getvalue())
        conn.close()
    except Exception as log_exc:
        print(f"Warning: failed to persist run log: {log_exc}", file=sys.stderr)

    if status == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
