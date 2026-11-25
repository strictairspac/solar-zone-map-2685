from time import time

from fastapi import HTTPException
from sqlalchemy import case as sql_case
from sqlalchemy import func, or_, select, update

from src.config.resources import engine
from src.constants.job_state import JobState
from src.constants.purge_state import PurgeState
from src.models.cases import cases
from src.models.reviews import reviews
from src.models.runs import runs
from src.services.audit import record


def now():
    return int(time())


def summarise(db, rows):
    """Attach purge progress to case rows using one statistics query."""
    rows = list(rows)
    if not rows:
        return {}
    identifiers = [row["id"] for row in rows]
    statistics = {}
    for entry in db.execute(
        select(
            runs.c.case_id,
            func.count().label("accepted"),
            func.sum(sql_case((runs.c.status == JobState.QUEUED, 1), else_=0)).label("pending"),
            func.sum(sql_case((runs.c.source.is_not(None), 1), else_=0)).label("copies"),
        ).where(runs.c.case_id.in_(identifiers)).group_by(runs.c.case_id)
    ).mappings():
        statistics[entry["case_id"]] = entry
    moment = now()
    return {row["id"]: progress_for(row, statistics.get(row["id"]), moment) for row in rows}


def progress_for(row, statistics, moment):
    accepted = int(statistics["accepted"]) if statistics else 0
    pending = int(statistics["pending"] or 0) if statistics else 0
    copies = int(statistics["copies"] or 0) if statistics else 0
    expires_at = row["expires_at"]
    state = row["purge_state"]
    return {
        "state": state,
        "expired": expires_at is not None and expires_at <= moment,
        "expires_at": expires_at,
        "started_at": row["purge_started_at"],
        "purged_at": row["purged_at"],
        "accepted_runs": accepted,
        "pending_runs": pending,
        "readings_retained": state == PurgeState.ACTIVE,
        "copies_retained": copies > 0,
    }


def begin(db, case_id, actor):
    """Clear a warranty batch's raw readings once its retention has run out."""
    moment = now()
    # The row lock is shared with acceptance, so once clearance starts no new
    # inspection can be accepted for this batch.
    row = db.execute(select(cases).where(cases.c.id == case_id).with_for_update()).mappings().first()
    if row is None:
        raise HTTPException(404, "资料不存在")
    if row["purge_state"] == PurgeState.PURGED:
        return row
    if row["expires_at"] is None or row["expires_at"] > moment:
        raise HTTPException(409, "质保批尚未到期，不能清退原始读数")
    start_locked(db, row, actor, moment)
    return db.execute(select(cases).where(cases.c.id == case_id)).mappings().first()


def start_locked(db, row, actor, moment):
    if row["purge_state"] == PurgeState.ACTIVE:
        # Raw readings go at once. Inspections accepted before expiry keep the
        # snapshot taken at acceptance; the batch stays purging until they end.
        db.execute(update(cases).where(cases.c.id == row["id"]).values(
            purge_state=PurgeState.PURGING, purge_started_at=moment, payload=None,
        ))
        record(db, "purge_start", actor, "case", row["id"])
    settle_locked(db, row["id"], actor, moment)


def settle(case_id, actor, moment=None):
    """Finish clearance in its own transaction.

    The case row is always taken before the run rows so this cannot deadlock
    against acceptance or a manual clearance, which both lock in that order.
    """
    with engine.begin() as db:
        return settle_locked(db, case_id, actor, moment or now())


def settle_locked(db, case_id, actor, moment):
    """Remove execution copies once no accepted inspection is still waiting."""
    state = db.scalar(
        select(cases.c.purge_state).where(cases.c.id == case_id).with_for_update()
    )
    if state != PurgeState.PURGING:
        # Nothing is being cleared for this batch; keep results and snapshots.
        return False
    pending = db.scalar(
        select(func.count()).select_from(runs).where(
            runs.c.case_id == case_id, runs.c.status == JobState.QUEUED
        )
    )
    if pending:
        return False
    freeze_receipts(db, case_id)
    db.execute(
        update(runs)
        .where(runs.c.case_id == case_id, or_(runs.c.source.is_not(None), runs.c.result.is_not(None)))
        .values(source=None, result=None, purged_at=moment)
    )
    cleared = db.execute(
        update(cases)
        .where(cases.c.id == case_id, cases.c.purge_state == PurgeState.PURGING)
        .values(purge_state=PurgeState.PURGED, purged_at=moment)
    )
    if cleared.rowcount:
        record(db, "purge_done", actor, "case", case_id)
    return bool(cleared.rowcount)


def freeze_receipts(db, case_id):
    """Copy each signed receipt's evidence before its run copies are cleared.

    Receipts signed before evidence capture existed have none frozen yet; take
    it now, while the run result is still present, so they survive the purge.
    """
    signed = db.execute(
        select(reviews.c.run_id).where(
            reviews.c.run_id.in_(select(runs.c.id).where(runs.c.case_id == case_id)),
            reviews.c.evidence.is_(None),
        )
    ).scalars().all()
    for run_id in signed:
        run = db.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
        if run is None or run["result"] is None:
            continue
        db.execute(update(reviews).where(reviews.c.run_id == run_id).values(evidence={
            "summary": run["result"]["summary"],
            "digest": run["digest"],
            "metrics": run["result"]["metrics"],
            "rows": run["result"]["rows"],
        }))


def sweep():
    """Expire due warranty batches and settle batches already being cleared."""
    with engine.begin() as db:
        moment = now()
        # Acceptance already stops at the deadline in the schedule endpoint;
        # this starts the actual clearance as soon as the deadline passes.
        due = db.execute(
            select(cases.c.id).where(
                cases.c.purge_state == PurgeState.ACTIVE,
                cases.c.expires_at.is_not(None),
                cases.c.expires_at <= moment,
            ).with_for_update(skip_locked=True)
        ).scalars().all()
        for case_id in due:
            row = db.execute(select(cases).where(cases.c.id == case_id)).mappings().first()
            if row is None or row["purge_state"] != PurgeState.ACTIVE:
                continue
            start_locked(db, row, "worker", moment)
        purging = db.execute(
            select(cases.c.id).where(cases.c.purge_state == PurgeState.PURGING)
        ).scalars().all()
        for case_id in purging:
            db.execute(select(cases.c.id).where(cases.c.id == case_id).with_for_update())
            settle_locked(db, case_id, "worker", moment)
