import asyncio
import os
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

import trading_bot
from web.api.db import get_db
from web.api.paths import bot_python_executable, repo_root

router = APIRouter()


@router.post("/run")
async def run_bot():
    """Run trading_bot.py as a subprocess — the web app never re-implements
    trading logic, it always triggers the same CLI script a scheduled cron
    run would."""
    root = repo_root()
    proc = await asyncio.create_subprocess_exec(
        bot_python_executable(), os.path.join(root, "trading_bot.py"),
        cwd=root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode("utf-8", errors="replace")
    return {"output": output, "returncode": proc.returncode}


@router.post("/sync")
async def sync_fills_now(conn=Depends(get_db)):
    """Reconcile locally-logged orders against Alpaca's real fill status,
    without running the trading strategy. sync_fills() otherwise only runs
    at the start of a bot run — so orders placed *during* a run (e.g. a
    rotation sell+buy) sit unsynced until the next run happens, leaving
    Realized P&L looking wrong (zero) in the meantime since it only counts
    status='filled' rows. This lets the dashboard be refreshed on demand."""
    try:
        updated = trading_bot.sync_fills(conn)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))
    return {"synced": updated}


@router.get("/watchlist")
async def get_watchlist(conn=Depends(get_db)):
    """Last-run EMA crossover snapshot for every configured symbol. This is a
    DB read, not a live TastyTrade call — the snapshot is written by
    trading_bot.py's log_evaluation() every time the bot actually runs
    (scheduled or via Run Bot Now), so this always reflects 'as of the last
    run' rather than hammering TastyTrade on every dashboard load."""
    config = trading_bot.load_config()
    symbols = config["symbols"]

    conn.row_factory = sqlite3.Row
    rows = {r["symbol"]: dict(r) for r in conn.execute("SELECT * FROM watchlist").fetchall()}

    return [
        rows.get(symbol, {"symbol": symbol, "evaluated_at": None})
        for symbol in symbols
    ]


@router.get("/holdings")
async def get_holdings():
    try:
        return trading_bot.get_all_positions()
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.get("/runs")
async def get_runs(limit: int = 10, conn=Depends(get_db)):
    """Recent run history (success/partial/error + full captured output),
    written by trading_bot.py's log_run() on every run regardless of trigger
    (cron, Run Bot Now, or a direct CLI invocation) — so this reflects
    scheduled runs too, not just ones made through this web app."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]
