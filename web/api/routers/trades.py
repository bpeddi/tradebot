import sqlite3
from collections import deque

from fastapi import APIRouter, Depends

from web.api.db import get_db

router = APIRouter()


@router.get("")
async def list_trades(conn=Depends(get_db)):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM trades ORDER BY submitted_at DESC, id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def _fifo_realized_pnl(rows):
    """FIFO-match filled buy/sell rows per symbol (ascending submitted_at)."""
    by_symbol = {}
    for r in rows:
        by_symbol.setdefault(r["symbol"], []).append(r)

    results = []
    for symbol, txns in by_symbol.items():
        lots = deque()
        realized = 0.0
        matched_qty = 0.0
        for t in txns:
            qty = t["filled_qty"] or 0
            price = t["filled_avg_price"] or 0
            if qty <= 0 or price <= 0:
                continue
            if t["side"] == "buy":
                lots.append({"qty": qty, "price": price})
            else:  # sell — consume oldest buy lots first
                remaining = qty
                while remaining > 1e-9 and lots:
                    lot = lots[0]
                    mq = min(remaining, lot["qty"])
                    realized += (price - lot["price"]) * mq
                    matched_qty += mq
                    lot["qty"] -= mq
                    remaining -= mq
                    if lot["qty"] <= 1e-9:
                        lots.popleft()

        open_qty = sum(l["qty"] for l in lots)
        if matched_qty > 0 or open_qty > 0:
            results.append({
                "symbol": symbol,
                "realized_pnl": round(realized, 2),
                "matched_qty": round(matched_qty, 2),
                "open_qty_unmatched": round(open_qty, 2),
            })
    return sorted(results, key=lambda r: -r["realized_pnl"])


@router.get("/pnl")
async def get_pnl(conn=Depends(get_db)):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT symbol, side, filled_qty, filled_avg_price, submitted_at "
        "FROM trades WHERE status='filled' ORDER BY submitted_at ASC"
    ).fetchall()
    rows = [dict(r) for r in rows]
    realized = _fifo_realized_pnl(rows)
    total_realized = round(sum(r["realized_pnl"] for r in realized), 2)
    return {"realized": realized, "total_realized_pnl": total_realized}
