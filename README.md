# mytradebot

A moving-average crossover trading bot for Alpaca paper trading, with
TastyTrade as the market-data source and a web dashboard for configuring,
scheduling, and monitoring it.

## How it works

For each symbol in `config.json`, the bot fetches recent candles from
TastyTrade and computes a short/long EMA pair (9/21 by default, on 4h
candles). A **real crossover** — the short EMA moving from at/below to
above the long EMA, or vice versa — triggers a trade:

- **Bullish crossover, flat** → buy, sized to one portfolio "slot"
  (`max_investment / max_slots` dollars, via a fractional/notional order).
- **Bearish crossover, holding** → sell the full position.
- Already holding, or no position to sell → no action.

**Portfolio slots.** Symbols are evaluated top-to-bottom in the configured
order. A slot counts as used for both open *positions* and open *unfilled
buy orders* — a pending order still has real capital committed to it even
before it fills, so it's not available to double-spend. When a bullish
signal fires and the portfolio is full, the bot **rotates**: among held
positions that are *also* showing real technical weakness (price below its
own short EMA, or distance to crossover under `rotation_weakness_pct`, a
configurable threshold — default 1.0%), it sells the weakest by unrealized
P&L % to fund the new buy. A position just having a one-day dip inside an
otherwise healthy uptrend doesn't qualify, even if it happens to have the
smallest $ gain at that instant — only genuinely fading positions do.
Weakness also has to be **confirmed on two separate runs** (a new 4h bar
must have formed in between) before a position is actually eligible to be
sold — the first run that observes it just flags it in `state.json`; a
symbol mid-consolidation (close/short/long EMA all bunched close together)
can trip the weak check on one noisy bar without the trend having actually
turned, so a single bar isn't enough to act on. If the symbol stops looking
weak before the second confirmation, the flag clears. If nothing held is
confirmed-weak, or the portfolio is only "full" because of unfilled pending
orders, the new buy is skipped instead and retried next run.

**Cold start.** The first time a symbol is ever evaluated (no prior state),
if it's already in an uptrend with no fresh crossover on that bar, the bot
treats that as an initial buy signal instead of waiting for a crossover
that may never come if the trend already started before the bot was
watching it. This only fires once per symbol (tracked in `state.json`) —
*unless* it loses out purely because the portfolio was full with nothing
to rotate out yet, in which case it stays eligible and retries on a later
run once a slot opens, rather than permanently losing its shot.

**Re-arm after a sell.** Selling a position (bearish crossover, or getting
rotated out) doesn't put a symbol back into cold-start — that's a one-time-
ever flag. But a sold symbol can still get back in: if it's simply resumed
the same uptrend it was sold out of (short EMA back above long EMA, but no
fresh crossover bar — a plain crossover check would never fire on that),
the bot re-arms it as an entry signal once **2 bars have closed** since the
sale. The 2-bar buffer avoids immediately re-buying off the same bar/noise
that triggered the sell. Like cold-start, if it loses out purely for lack
of a free slot, it stays eligible rather than losing its shot.

Every run — whether triggered by cron, the dashboard's "Run Bot Now", or a
direct CLI invocation — logs its full output and an overall status
(success / partial / error) to `trades.db`, along with every order placed
and a snapshot of each symbol's EMA/crossover state.

## Project structure

```
mytradebot/
├── trading_bot.py        # the bot itself — CLI entry point, all trading logic
├── config.json            # strategy config (symbols, EMA windows, slots, $)
├── state.json              # per-symbol cold-start tracking (gitignored)
├── trades.db                # SQLite: trades, watchlist snapshots, run history (gitignored)
├── requirements.txt
├── .env                       # credentials (gitignored) — see .env.example
├── check_alpaca_balance.py    # standalone: verify Alpaca connection
├── place_order.py              # standalone: manually fire a test order
├── Dockerfile                   # single image: just uvicorn, no OS packages needed
├── docker-entrypoint.sh           # seeds /data/config.json, execs uvicorn
├── deploy.sh                       # build frontend, rsync to EC2, build+run image there
└── web/                              # dashboard
    ├── requirements.txt           # extends the root requirements
    ├── api/                        # FastAPI backend
    │   ├── main.py                   # app, CORS, JWT middleware, routers, scheduler lifespan
    │   ├── deps.py                     # auth (bcrypt + JWT)
    │   ├── db.py                        # users/schedule tables on trades.db
    │   ├── scheduler.py                   # in-process async scheduler (no OS cron)
    │   ├── paths.py                       # repo-root / venv-python resolution
    │   └── routers/                        # auth, config, bot, trades, schedule
    └── frontend/                    # React + TypeScript + Tailwind
        └── src/components/            # dashboard, config, schedule, trades, settings
```

## Setup

### 1. Python environment

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Credentials

Copy `.env.example` to `.env` and fill in:

| Variable | What it's for |
|---|---|
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` / `ALPACA_END_POINT` | Order placement (Alpaca **paper** trading) |
| `TT_SECRET` / `TT_REFRESH` / `TT_CLIENT_ID` | TastyTrade OAuth2 — market data |
| `JWT_SECRET` | Signs the dashboard's login tokens — **generate a real random value**, don't leave the code default |

### 3. Strategy config (`config.json`)

| Field | Meaning |
|---|---|
| `symbols` | Tickers to track, evaluated in this order |
| `candle_interval` | Candle width for TastyTrade (e.g. `"4h"`, `"1d"`) |
| `short_window` / `long_window` | EMA periods |
| `lookback_days` | How much history to fetch per symbol |
| `max_investment` | Total dollars committed across the whole portfolio |
| `max_slots` | Max concurrent positions — per-slot size is `max_investment / max_slots` |
| `rotation_weakness_pct` | How close to (or past) its own crossover a held position must be to qualify for rotation (default `1.0`) |
| `rotation_enabled` | When `false`, a full portfolio skips new buys instead of rotating a weak holding out — a slot only frees up via a real bearish crossover sell (default `true`) |

## Running the bot

```powershell
.venv\Scripts\python.exe trading_bot.py
```

Exits non-zero if the run failed outright; prints (and logs to `trades.db`)
per-symbol detail either way.

## Running the dashboard

**Backend** (from the repo root, so `trading_bot.py` and `web` are both importable):

```powershell
.venv\Scripts\python.exe -m pip install -r web\requirements.txt
.venv\Scripts\python.exe -m uvicorn web.api.main:app --host 127.0.0.1 --port 8001
```

**Frontend** (separate terminal):

```powershell
cd web\frontend
npm install
npm run dev
```

Opens on `http://localhost:5180` (falls back to the next free port if
taken) and proxies `/api` to the backend on `:8001`.

First visit: register the one admin account (registration locks itself
after that — see Settings tab to change the password later). Then:

- **Dashboard** — portfolio slots used, holdings with live unrealized P&L,
  realized P&L, last-run watchlist snapshot, run history with logs, manual
  run trigger, and a "Sync Fills" button to reconcile pending orders against
  Alpaca's real fill status on demand (without running the strategy) — useful
  right after a run places orders, since the strategy run itself only syncs
  at its *start*, so same-run fills (e.g. a rotation sell+buy) would
  otherwise sit unsynced, and unmatched, until the next scheduled run.
- **Config** — edit strategy parameters; shows the computed $-per-slot live.
- **Schedule** — set two daily run times (Mon–Fri); shows the computed next
  run time. Handled by an in-process scheduler inside the dashboard's own
  server (polls every 30s) — no OS cron, works identically on every host.
- **Trades** — full order log.
- **Settings** — change password.

### Production build

```powershell
cd web\frontend && npm run build
```

Once `web/frontend/dist/` exists, the FastAPI app serves it directly at
`/` — a single `uvicorn` process is the whole app, no separate frontend
server needed.

## Deployment

**Deployed and confirmed live** on EC2 (same box as `tasty_trade`) at
`http://34.192.71.198:8081` — registration, login, dashboard, and a real
"Run Bot Now" click have all been verified working through the actual
browser against the production deployment. See `PLAN.md` for exactly
what's been tested, including why OS cron was dropped in favor of an
in-process scheduler.
The image needs no `apt-get` step at all — just `uvicorn`. Persistent
state (`config.json`, `state.json`, `trades.db`) lives under
`MYTRADEBOT_DATA_DIR` (`/data`), bind-mounted from the host so redeploys
never wipe live config or trade history.

**One-time EC2 setup** (same box as `tasty_trade`, which already has Docker
installed):

```bash
ssh -i strack.pem ec2-user@34.192.71.198
sudo mkdir -p /opt/mytradebot/data && sudo chown -R ec2-user:ec2-user /opt/mytradebot
exit

scp -i "C:/Users/balap/.ssh/strack.pem" .env ec2-user@34.192.71.198:/opt/mytradebot/.env
```

Then, with the EC2 security group allowing inbound :8081:

```bash
./deploy.sh
```

builds the frontend locally, rsyncs the code (excluding secrets/local data),
builds the image on the EC2 box, and runs it with `--network=host`,
`--env-file /opt/mytradebot/.env`, `-v /opt/mytradebot/data:/data`, and
`--restart unless-stopped`.

### Second instance (`deploy-bot2.sh`) — rotation A/B comparison

A second, fully independent deployment of the exact same code runs
alongside production for a live paper-trading comparison: identical symbol
list / `$` / slots, but `"rotation_enabled": false`, so it never sells a
held position to make room for a new signal — a slot only frees up via a
real bearish crossover. Both the build/sync/run logic are shared (in
`deploy_common.sh`) so a fix to one instance's deploy path never silently
diverges from the other's.

| | Production (`deploy.sh`) | Bot2 (`deploy-bot2.sh`) |
|---|---|---|
| Container | `mytradebot` | `mytradebot2` |
| Port | `:8081` | `:8082` |
| Remote dir | `/opt/mytradebot` | `/opt/mytradebot2` |
| Alpaca account | production | dedicated third paper account — **never** shared with production or the local-dev account |

One-time setup for bot2, mirroring the original EC2 setup above but at
`/opt/mytradebot2`: `sudo mkdir -p /opt/mytradebot2/data`, `scp` an `.env`
there with its own `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` (TastyTrade creds
and `JWT_SECRET` can be reused or regenerated), and open `:8082` in the EC2
security group. Then `./deploy-bot2.sh`.

## Security notes

- Dashboard registration is **bootstrap-only** — it works once, then
  returns 403 forever. If you ever need a second account, that needs a
  deliberate code change, not a public signup flow.
- Change the login password from any placeholder via the Settings tab
  before this is reachable from anywhere but `localhost`.
- `JWT_SECRET` must be a real random value in `.env` — an empty or default
  value means tokens are effectively unsigned.
