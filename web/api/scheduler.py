"""In-process scheduler — replaces OS cron entirely. A background asyncio
task polls the `schedule` table and, when the current time (in the
configured timezone) matches time1/time2, spawns the exact same
trading_bot.py subprocess the dashboard's "Run Bot Now" button does.

Why not OS cron: cron needs its own daemon process + package install inside
the container, its own environment-propagation handling (cron doesn't
inherit the parent process's env), and ran into a host-specific Docker
seccomp restriction that blocked installing it at all on one EC2 target.
A subprocess spawned from this already-running process inherits its full
environment for free and needs nothing installed."""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import trading_bot
from web.api.db import init_web_tables
from web.api.paths import bot_python_executable, repo_root

logger = logging.getLogger(__name__)

POLL_SECONDS = 30

# {(date_str, "HH:MM"): True} — which scheduled slots have already fired
# today, so a slot doesn't re-fire every poll interval while the clock
# matches that minute.
_fired_today = {}


def get_schedule_row():
    # trading_bot.init_db() only creates its own tables (trades/watchlist/
    # runs); users/schedule are web-layer tables normally created lazily by
    # the first HTTP request via get_db(). The scheduler loop starts at app
    # boot and may poll before any request has landed, so it must ensure
    # these tables itself too.
    conn = trading_bot.init_db()
    try:
        init_web_tables(conn)
        row = conn.execute(
            "SELECT time1, time2, timezone, enabled FROM schedule WHERE id=1"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return {"time1": "10:00", "time2": "15:00", "timezone": "America/Chicago", "enabled": False}
    return {"time1": row[0], "time2": row[1], "timezone": row[2], "enabled": bool(row[3])}


def compute_next_run(sched):
    """Next upcoming weekday datetime among time1/time2, in the configured
    timezone — None if disabled. Used purely for UI display."""
    if not sched["enabled"]:
        return None
    try:
        tz = ZoneInfo(sched["timezone"])
    except Exception:
        tz = ZoneInfo("UTC")
    now = datetime.now(tz)
    candidates = []
    for t in (sched["time1"], sched["time2"]):
        hour, minute = (int(x) for x in t.split(":"))
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        while candidate.weekday() >= 5:  # roll Sat/Sun forward to Monday
            candidate += timedelta(days=1)
        candidates.append(candidate)
    return min(candidates).isoformat()


async def _run_bot_once():
    """Spawn trading_bot.py as a subprocess — identical invocation to the
    dashboard's manual Run Bot Now, so every run (scheduled or manual) logs
    to trades.db the same way."""
    root = repo_root()
    try:
        proc = await asyncio.create_subprocess_exec(
            bot_python_executable(), os.path.join(root, "trading_bot.py"),
            cwd=root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        logger.info(
            "Scheduled run finished (exit %s): %s",
            proc.returncode, stdout.decode("utf-8", errors="replace")[-500:],
        )
    except Exception:
        logger.exception("Scheduled run failed to launch")


async def scheduler_loop():
    while True:
        try:
            sched = get_schedule_row()
            if sched["enabled"]:
                tz = ZoneInfo(sched["timezone"])
                now = datetime.now(tz)
                is_weekday = now.weekday() < 5  # Mon=0 .. Fri=4; markets are closed Sat/Sun
                today = now.strftime("%Y-%m-%d")
                current_hm = now.strftime("%H:%M")
                for t in (sched["time1"], sched["time2"]):
                    key = (today, t)
                    if is_weekday and current_hm == t and key not in _fired_today:
                        _fired_today[key] = True
                        logger.info("Scheduled run triggered for %s %s", today, t)
                        asyncio.create_task(_run_bot_once())
                # Drop stale entries so the dict doesn't grow forever.
                for key in list(_fired_today):
                    if key[0] != today:
                        del _fired_today[key]
        except Exception:
            logger.exception("Scheduler loop error")
        await asyncio.sleep(POLL_SECONDS)
