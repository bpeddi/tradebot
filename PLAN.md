# mytradebot — Project Plan & Status

## Context

Started as a simple single-symbol moving-average crossover bot. It has since
grown into a multi-symbol, slot-based portfolio strategy with its own trade
log, run history, and a web dashboard for managing it day to day — because
running it purely by hand (editing `config.json` directly, no visibility
into what the last scheduled run actually did) didn't scale once the symbol
list grew past a handful of tickers.

## Current status: built and verified

**Strategy (`trading_bot.py`)**
- EMA(9/21) crossover on 4h candles from TastyTrade, per symbol.
- Portfolio-level sizing: `max_investment` / `max_slots` → one "slot" =
  `max_investment / max_slots` dollars. Symbols are evaluated top-to-bottom
  in `config.json`'s list; a buy only fires if a slot is free. Slot usage
  counts both open *positions* and open *unfilled buy orders*
  (`get_open_orders()`) — a real bug this caught: with 8 slots configured
  but one old pending order left over from testing, the bot counted 0/8
  used and bought 8 *more* symbols on top of it, 9 commitments against an
  8-slot budget. Fixed by computing `committed_symbols` from positions +
  open buy orders once per run, used both for slot counting and to stop a
  symbol with an already-pending buy from getting a second one stacked on
  it. Verified via targeted offline tests reproducing the exact scenario.
- **Rotation**: when a bullish signal fires and the portfolio is full, the
  bot sells a held position to fund the new buy instead of just skipping
  it. Deliberately *not* "sell the highest-profit position" (the user's
  first instinct) — that would mean repeatedly cutting the best-performing
  trend short to chase an unconfirmed new signal.
  First version picked the weakest holding by raw unrealized P&L % alone —
  caught live in production doing something undesirable: it sold HNGE and
  LIFE, both clearly still in healthy, intact uptrends on the chart (no
  bearish crossover, short EMA still well above long EMA), purely because
  they had a smaller $ gain than other holdings at that instant (often
  just a normal one-day pullback, not a trend breakdown). Refined:
  rotation now only considers held positions that are **also** showing
  real technical weakness — price has dipped below its own short EMA, or
  its distance to crossover has shrunk under a configurable
  `rotation_weakness_pct` threshold (default 1.0%, covers "about to flip
  bearish" and "already flipped without a fresh-cross bar catching it").
  Among only those qualifying positions, the weakest by unrealized P&L %
  is sold. If nothing held qualifies as technically weak — or the
  portfolio is "full" only via unfilled pending orders — the buy is
  skipped instead, same fallback as before. Verified via offline tests
  reproducing the exact HNGE/LIFE scenario: a technically healthy position
  with the worst raw % is correctly passed over in favor of a technically
  weak one with a less-bad %, and rotation correctly refuses to sell
  anything when every held position still looks healthy.
- Cold-start rule: the first time a symbol is ever evaluated, if it's
  already in an uptrend (short EMA > long EMA) with no fresh crossover,
  that counts as an initial entry — otherwise the bot would miss any trend
  already in progress when it starts tracking a symbol. Tracked per-symbol
  in `state.json` so it only fires once. Caught live in production: a
  cold-start candidate that loses out purely on slot ordering (portfolio
  already full by the time its turn comes, nothing to rotate out yet) used
  to get marked `initialized` anyway — permanently burning its one shot
  even though it never actually bought. Fixed: that one specific outcome
  (cold-start candidate + no rotatable position available) leaves the
  symbol unmarked, so it's reconsidered for cold-start again next run once
  a slot opens up, instead of needing a brand-new crossover from then on.
  Verified via offline tests for both the skip-and-stay-eligible case and
  the later successful retry once a slot frees.
- Orders execute on Alpaca paper trading (notional/fractional buys, full-
  position sells). All data/order code paths verified live against both
  TastyTrade and Alpaca APIs.

**Persistence (`trades.db`, SQLite)**
- `trades` — every order placed, synced against Alpaca for fill status on
  every run (`sync_fills`).
- `watchlist` — latest EMA/crossover snapshot per symbol, written on every
  run; this is what the dashboard shows without needing a live API call.
- `runs` — full console output + success/partial/error status for every
  run, regardless of what triggered it (cron, the dashboard's "Run Bot
  Now", or a direct CLI invocation).

**Web dashboard (`web/api` FastAPI + `web/frontend` React/TS/Tailwind)**
- JWT auth, bootstrap-only registration (works once, then locks).
- Dashboard: portfolio slots used/available, holdings w/ live unrealized
  P&L (from Alpaca), realized P&L (FIFO-matched from `trades`), watchlist
  (last-run snapshot, not live), run history with expandable logs, manual
  "Run Bot Now".
- Config tab: edit `symbols`/`candle_interval`/windows/`max_investment`/
  `max_slots` with a live "≈ $X per slot" preview.
- Schedule tab: set two daily run times (Mon–Fri); "Apply" saves to the DB
  and shows the computed next run time. No OS cron involved — see below.
- Settings tab: change password.

## Deployment: Docker + EC2 — built and locally verified

**Single Docker container running `uvicorn`, with the twice-daily schedule
handled by an in-process asyncio scheduler** (`web/api/scheduler.py`), not
OS cron. First attempt used a `cron` daemon inside the container (matching
`tasty_trade`'s general container-per-app pattern), but the target EC2
host's Docker daemon has a restrictive default seccomp profile that blocks
something Debian trixie's `cron`/`tzdata` postinst scripts need — confirmed
via direct diagnosis (`docker run --security-opt seccomp=unconfined` fixed
it, but `docker build` on this Docker version doesn't support
`--security-opt` at all, and BuildKit hits an unrelated `runc` bug on this
same host). Rather than touch the shared Docker daemon's config (would
affect `tasty_trade`'s running container too) or hand-roll a custom base
image, we dropped OS cron entirely: the scheduler is a background task in
the FastAPI process itself, polling the `schedule` table every 30s and
spawning the exact same `trading_bot.py` subprocess "Run Bot Now" does when
the clock (in the configured timezone, Mon–Fri only) matches. This also
removed a whole class of complexity that's no longer needed: no apt-get in
the Dockerfile, no cron-environment-propagation hack (`/etc/environment`) —
the scheduled subprocess just inherits `uvicorn`'s own environment.

Files: `Dockerfile`, `docker-entrypoint.sh`, `.dockerignore`, `deploy.sh`.

**Persistence**: `config.json`/`state.json`/`trades.db` live under
`MYTRADEBOT_DATA_DIR` (`/data` in the container, bind-mounted from
`/opt/mytradebot/data` on the host) — separate from the synced code tree,
so redeploys never clobber live config edits or trade history. The image
ships `config.default.json` purely as a one-time seed for a brand-new
`/data` volume.

**Verified locally** (Docker Desktop, image built and run on this
machine): image builds cleanly with no `apt-get` step at all, `/docs`
responds, config seeds into `/data` on first start, registration/login/JWT
work, `PUT /api/schedule` saves and returns a correct next-run timestamp
(including rolling weekend candidates to the next Monday), the match-and-
fire condition was unit-verified to correctly trigger a run, and a manual
end-to-end bot run completed successfully with a real order placed on
Alpaca paper trading. Also caught and fixed a startup-ordering bug: the
scheduler's background task can poll before any HTTP request has
initialized the `users`/`schedule` tables, so it now ensures those tables
itself too.

### One-time EC2 setup (before the first `deploy.sh` run)

```bash
ssh -i strack.pem ec2-user@34.192.71.198
sudo mkdir -p /opt/mytradebot/data && sudo chown -R ec2-user:ec2-user /opt/mytradebot
exit

# From the local machine — copy real credentials (never synced by deploy.sh):
scp -i "C:/Users/balap/.ssh/strack.pem" .env ec2-user@34.192.71.198:/opt/mytradebot/.env
```

Docker is already installed on that box (set up for `tasty_trade`), so no
Docker install step is needed here.

Before deploying for real: rotate the dashboard password off any
placeholder value, and confirm `JWT_SECRET` in `.env` is a real random
value (not blank, not the `change-me-in-production` code default) — these
matter once the port is reachable from a public IP.

## Deployed — fully confirmed in production

`./deploy.sh` ran against the real EC2 instance successfully. Security
group needed a dedicated inbound rule for :8081 (a rule for :8000 or :8001
doesn't cover it — each port needs its own rule); once added, the full
flow was confirmed live at `http://34.192.71.198:8081`:

- App loads in a browser, fresh `/api/auth/register` (this deployment has
  its own empty `users` table — local dev's account doesn't carry over,
  by design, since `trades.db` is deliberately excluded from `deploy.sh`'s
  sync).
- Logged in, dashboard loaded (config/holdings/watchlist/P&L/runs/schedule
  all 200).
- Clicked "Run Bot Now" → completed in ~2.3s, `status: success`, recorded
  correctly in the `runs` table, all 5 symbols evaluated via TastyTrade.

**Known side effect, not a bug**: that run re-triggered the AAPL cold-start
buy — a third real paper order, since this deployment's `state.json` is
its own fresh file, separate from local dev and the earlier local Docker
test, all three pointing at the same Alpaca paper account. Worth checking
the Alpaca dashboard directly to see what's actually sitting there now.

**Rotation A/B comparison (bot2)** (new)
- User proposed running a second strategy variant side-by-side for a couple
  weeks: identical bot, except a full portfolio never sells a held position
  to make room for a new signal — a slot only frees up via a real bearish
  crossover. Initially framed as a separate `trading_bot2.py` file; I
  recommended against literal duplication (two copies of the EMA/cold-start/
  re-arm/rotation logic drift apart the moment one gets a bug fix the other
  doesn't) and proposed a single shared codebase with a `rotation_enabled`
  config flag instead, deployed as two independent containers. User agreed.
- `process_symbol`/`main_async` gained a `rotation_enabled` param
  (`config.get("rotation_enabled", True)` — defaults to today's behavior
  unchanged). When `False` and the portfolio is full, the buy is skipped
  immediately (no weak-candidate evaluation at all, no selling) with the
  same existing retry-next-run fallback. `ConfigModel`/`types.ts` gained the
  field (default `true`); the Config tab got a checkbox plus explanatory
  text that changes based on the toggle state.
- `deploy.sh`'s build/sync/run logic was extracted into `deploy_common.sh`
  (a `deploy_instance()` function parameterized by remote dir/image/
  container name/port) so production and the new `deploy-bot2.sh` can't
  silently diverge — a deploy-path fix now automatically applies to both.
  `deploy-bot2.sh` targets `/opt/mytradebot2`, container `mytradebot2`,
  port `:8082`.
- Per the local-account-isolation incident above, this needs a **third**
  dedicated Alpaca paper account (not production's, not the local-dev
  "testing" account) so the two live strategies never collide. User is
  creating it; bot2's `/opt/mytradebot2/data/config.json` has been
  pre-seeded on EC2 (mirrors production's current 26-symbol / $30,000 /
  10-slot config, `rotation_enabled: false`) so deployment is a single
  `./deploy-bot2.sh` run once the `.env` with the new account's keys lands
  at `/opt/mytradebot2/.env` and `:8082` is opened in the security group.
  Verified via 2 offline scenarios (rotation disabled never sells even an
  unambiguously-weak position; rotation enabled still sells on confirmed
  weakness, proving the toggle didn't regress the existing path) — full
  10-scenario suite across all 4 test files re-run clean. Production
  redeployed first with the refactored `deploy.sh` and confirmed via direct
  config inspection: `rotation_enabled: true` (default, unchanged), 26
  symbols intact.

**Rotation weakness confirmation (2 runs)** (new)
- User flagged a real production trade: at 3:00 PM CST on 2026-10-27, SNOW's
  bullish crossover rotated out ZETA. User suspected ZETA was still a good
  uptrending position and asked whether rotation should wait ~1 day (2x 4h
  bars) to confirm a replacement before acting.
- Root-caused: at the moment of the rotation decision, ZETA's own snapshot
  was close=33.35, short MA=33.64, long MA=33.41, distance=+0.94%. It
  satisfied both weak conditions, but only barely — close/short/long were
  all bunched within a ~0.3-point band, i.e. a trend genuinely consolidating
  rather than clearly reversing (short EMA was still above long EMA; no
  bearish crossover had actually happened). One noisy bar was enough to
  trip the existing single-bar weak check. Same underlying category as the
  original LIFE/HNGE problem, one level more subtle — hiding inside the
  weakness filter itself instead of the raw P&L sort this time.
- Considered delaying every new signal (buy/rotation alike) by a day, but
  that would also slow genuine bearish-crossover exits (already gated on a
  real EMA flip, no noise problem there) and fresh buys into open slots (no
  existing winner at risk) — unnecessary blast radius for a rotation-only
  problem. User agreed to the narrower fix.
- Implemented: a held position's technical weakness must now be observed on
  **two separate evaluations** (a new bar must have formed in between)
  before it's eligible to be sold in a rotation. The first run that finds a
  candidate weak just flags it (`state[symbol]["weak_flagged_bar_ts"]`) and
  moves on — same existing fallback (skip the new buy, retry next run) if
  no other already-confirmed-weak holding exists. Only a second, later-bar
  weak observation makes it eligible. If a flagged symbol stops looking
  weak before confirmation, the flag clears (no stale carry-forward to a
  much later, unrelated bar). The flag is also cleared the moment a
  position actually gets rotated out (streak is moot once sold).
- Verified via 3 offline scenarios: a first weak bar flags but doesn't sell;
  a second confirmed weak bar (later bar_ts, still weak) actually sells;
  and recovering (no longer weak) before confirmation clears the flag
  instead of selling later on a stale flag. Full existing re-arm and tz-fix
  suites re-run clean alongside it — no regressions.
- Per the local-account-isolation incident above, this was verified with
  mocked tests only — no live local CLI run — before deploying straight to
  EC2.

**Re-arm after sell** (new)
- User asked: does selling a symbol put it back into cold-start eligibility?
  Answer was no — cold-start is a one-time-ever flag keyed on `symbol not in
  state`, and once a symbol is first evaluated `state[symbol]` is set
  permanently, so a sold symbol could previously only get back in via a
  *real* crossover flip, never via the "already in an uptrend" shortcut.
  That meant a symbol resuming the same uptrend it was sold out of (no
  fresh cross, e.g. rotated out mid-trend, or a brief dip-and-recover) could
  sit locked out indefinitely.
- Added a re-arm rule: every sell (bearish-crossover sell, or a rotation
  sell of a different symbol) stamps `state[symbol]["sold_bar_ts"]` with the
  timestamp of the bar the sale happened on. On later runs, if the symbol
  still has no fresh crossover but is back in an uptrend (short EMA > long
  EMA) and **2 bars have closed** since that timestamp, it's re-armed as a
  bullish entry signal (reason `rearm_after_sell`) — same slot/rotation
  treatment as a cold-start buy. `evaluate_symbol()` gained an optional
  `since_ts` param that returns `bars_since` (counts actual closed bars in
  the fetched series past that timestamp, not a hard-coded time delta — so
  it's correct across market closures/weekends without guessing a bar
  duration).
- The "mark initialized" line changed from replacing `state[symbol]`
  wholesale to merging (`state.setdefault(symbol, {})["initialized"] = True`)
  so `sold_bar_ts` survives across runs instead of being wiped every time a
  symbol gets re-evaluated.
- If a re-arm candidate loses out purely for lack of a free slot, it stays
  eligible (nothing is deleted) — `sold_bar_ts` just keeps aging until a
  slot opens, same spirit as the cold-start retry fix. Consumed (cleared)
  only once the re-arm buy actually executes, so a later sell starts a
  fresh 2-bar wait.
- Verified via 5 offline scenarios (bars_since>=2 fires and clears the
  flag; bars_since<2 doesn't fire; true first-run cold-start still fires
  unaffected by the refactor; a real bearish-crossover sell stamps
  `sold_bar_ts`; a re-arm candidate blocked by full slots stays eligible
  rather than being reset) before a real local CLI run to confirm no
  regression.

**Sync Fills (on-demand reconciliation)**
- Root cause of "Realized P&L shows $0.00" (seen twice in production): `sync_fills()`
  only ran at the *start* of a bot run, so orders placed *during* that same run
  (e.g. a rotation sell+buy) stayed `status='pending_new'` until the *next*
  scheduled run synced them — and the FIFO realized-P&L query only counts
  `status='filled'` rows, so a sell sitting unsynced for hours showed as if it
  never happened.
- Fix: added `POST /api/bot/sync` (calls `trading_bot.sync_fills()` directly,
  no strategy run) + a "Sync Fills" button on the dashboard next to "Run Bot
  Now", so the gap between a fill happening and `trades.db` knowing about it
  is one click instead of "wait for the next scheduled run."
- Verified against the real stuck orders: 10 pending rows (AAPL/ANF/LIFE/
  FIVN/GTLB/HNGE/NTRA/PLTR/SN/CRWD/DDOG/NTRA/ZETA/ZS — rotation sells+buys
  from 2026-10-26) synced correctly — most resolved to `filled`, the original
  stale test orders resolved to `canceled` (correctly still excluded from
  P&L). Realized P&L went from a flat $0.00 to the real **-$70.73** total
  (AAPL +$26.63, GTLB +$12.18, HNGE -$19.46, NTRA -$31.06, LIFE -$59.02, rest
  still open positions with no matched sell yet) — confirms the FIFO logic
  itself was always correct, it just had nothing filled to match against.

## Incident: local run executed a real unwanted trade (2026-10-27)

While verifying the re-arm timezone fix (below) wouldn't regress anything,
`trading_bot.py` was run directly from the local CLI as a "quick sanity
check." This was a mistake: local `.env` points at the **same live Alpaca
paper account** EC2 trades on, but local `config.json`/`state.json` are
stale dev artifacts (`max_slots: 5` / `$10,000` vs EC2's real `10 slots` /
`$30,000`, and no memory of EC2's cold-start/trade history). The bot
correctly used live Alpaca data for positions/orders, but its *own*
slot-capacity math and cold-start state were wrong — so it treated several
already-correctly-held EC2 positions as fresh cold-start candidates,
decided its (too-small) portfolio was full, and attempted rotations against
real positions. One attempt (ZETA, for DDOG) was rejected by Alpaca because
those shares were already locked under EC2's own legitimate pending order —
no harm done. A second attempt went through: **sold PCTY, bought LIFE**,
both landing as unfilled `accepted` orders (market was effectively closed
for the session). Caught before either filled by checking Alpaca directly;
both orders were cancelled with the user's explicit go-ahead, restoring the
account to exactly what EC2's real strategy intended. A third attempt
(GTLB, rotating out MSFT) hit a network timeout and — confirmed via the
open-orders list afterward — never actually placed an order.

**Rule going forward**: never run `trading_bot.py`'s live-trading path
(the real CLI, hitting real Alpaca/TastyTrade) from local dev for
verification. Local `.env` currently shares the production Alpaca paper
account — the user is creating a dedicated second paper account (separate
signup, no funding needed) so local and EC2 are fully isolated; once that's
done, update local `.env`'s `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` to the new
account and never point it at EC2's account again. Until then, and even
after, any "does this still work" check should use the offline mocked test
pattern (see `evaluate_symbol`/`process_symbol` stubbed-out tests used to
verify the re-arm and rotation logic) — never a live CLI invocation.

## Open items

- Reconcile/clean up the Alpaca paper account if the stacked AAPL test
  orders from multiple environments are confusing (check Alpaca directly).
- **Deliberate soak period**: running live on paper trading for a few weeks
  before any further changes, to let the slot-counting/rotation/cold-start
  fixes prove out against real market conditions rather than just tests.
- **Next planned feature (on hold until the soak period above)**:
  stop-loss logic — no per-position or portfolio-level risk control exists
  yet (flagged as a real gap in the "going live" discussion, alongside no
  alerting and no live-vs-paper UI indicator). User will scope this further
  in a day or two.
- Live-money switch: `ALPACA_*` env vars are the only code change needed,
  but deliberately *not* making them dashboard-configurable — keeping them
  .env-only (edited via SSH, same as today) is an intentional safeguard so
  switching real money on can never happen from a stray UI click. Before
  going live: user plans to start the real-money account at **`max_investment:
  6000`, `max_slots: 3`** ($2,000/slot — vs. $24K/8 slots in the current
  paper config), then scale up from there once proven. Also still needed: stop-loss/risk
  controls and alerting (neither exists yet).
- Further improvement ideas from the user, not yet scoped.

## Environment notes

Windows Smart App Control was deliberately disabled on this dev machine
early on (it was blocking pandas/pyarrow's compiled extensions). That's a
one-way change — if a similar "DLL blocked" error ever resurfaces, it's
not SAC (it's off for good on this machine); look at antivirus real-time
scanning or a corrupted wheel instead.

## How to run things today

See `README.md` for setup and day-to-day usage.
