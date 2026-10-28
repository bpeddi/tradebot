from fastapi import APIRouter, Depends

from web.api.db import get_db
from web.api.scheduler import compute_next_run
from web.api.schemas import ScheduleModel

router = APIRouter()


@router.get("")
async def get_schedule(conn=Depends(get_db)):
    row = conn.execute("SELECT time1, time2, timezone, enabled FROM schedule WHERE id=1").fetchone()
    sched = (
        {"time1": row[0], "time2": row[1], "timezone": row[2], "enabled": bool(row[3])}
        if row else ScheduleModel().model_dump()
    )
    sched["next_run"] = compute_next_run(sched)
    return sched


@router.put("")
async def update_schedule(sched: ScheduleModel, conn=Depends(get_db)):
    conn.execute(
        """
        INSERT INTO schedule (id, time1, time2, timezone, enabled, updated_at)
        VALUES (1, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            time1=excluded.time1, time2=excluded.time2,
            timezone=excluded.timezone, enabled=excluded.enabled,
            updated_at=excluded.updated_at
        """,
        (sched.time1, sched.time2, sched.timezone, int(sched.enabled)),
    )
    conn.commit()

    result = sched.model_dump()
    result["saved"] = True
    result["next_run"] = compute_next_run(result)
    return result
