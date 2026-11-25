from time import time

from fastapi import HTTPException
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from src.constants.job_state import JobState
from src.models.reviews import reviews
from . import audit, runs


def get(db, run_id):
    row = db.execute(select(reviews).where(reviews.c.run_id == run_id)).mappings().first()
    if row is None:
        return None
    entry = dict(row)
    # The signed receipt is self-contained: it carries the board items and the
    # page-skip basis captured at signing, even after the run's copies clear.
    if entry.get("evidence") is None and entry.get("created_at"):
        run = runs.get(db, run_id)
        if run["result"] is not None:
            entry["evidence"] = run_evidence(db, run_id)
    return entry


def run_evidence(db, run_id):
    run = runs.get(db, run_id)
    return {
        "summary": run["result"]["summary"],
        "digest": run["digest"],
        "metrics": run["result"]["metrics"],
        "rows": run["result"]["rows"],
    }


def sign(db, run_id, data, actor):
    run = runs.get(db, run_id)
    if run["status"] != JobState.DONE:
        raise HTTPException(409, "批次执行成功后才能签核")
    if run["result"] is None:
        raise HTTPException(409, "该批次的执行副本已随清退移除，不能再签核")
    try:
        db.execute(insert(reviews).values(
            run_id=run_id, note=data.note, actor=actor, created_at=int(time()),
            evidence=run_evidence(db, run_id),
        ))
    except IntegrityError as exc:
        raise HTTPException(409, "该批次已经签核") from exc
    audit.record(db, "review", actor, "run", run_id)
    return get(db, run_id)
