import logging
from time import time

from sqlalchemy import select, update

from src.config.resources import engine
from src.constants.job_state import JobState
from src.domain import scenario
from src.models.cases import cases
from src.models.runs import runs
from src.services import retention
from src.services.audit import record
from src.utils.serial import content_digest

logger = logging.getLogger(__name__)


def service_one():
    with engine.begin() as db:
        statement = (
            select(runs).where(runs.c.status == JobState.QUEUED).order_by(runs.c.id)
            .limit(1).with_for_update(skip_locked=True)
        )
        task = db.execute(statement).mappings().first()
        if task is None:
            return False
        # The source snapshot is what lets an accepted run finish after the
        # batch's readings are cleared; the case payload only serves old rows.
        payload = task["source"]
        if payload is None:
            payload = db.scalar(select(cases.c.payload).where(cases.c.id == task["case_id"]))
        if payload is None:
            # Only runs accepted before clearance carry a snapshot, so a missing
            # one means there is nothing to inspect; fail rather than pass.
            finish(db, task["id"], {
                "status": JobState.FAILED,
                "failure": "质保批原始读数已清退，未能开始本次抽检",
            })
        else:
            # A queued run that still has a snapshot was accepted before the
            # deadline (acceptance and clearance share the batch row lock), so
            # it always runs to completion, even after a restart.
            try:
                result = scenario.run(payload, task["parameter"], db)
                output = {"status": JobState.DONE, "result": result, "digest": content_digest(result)}
            except Exception as exc:
                # Let the failed database transaction roll back before persisting the error.
                raise JobFailure(task["id"], task["case_id"], exc) from exc
            finish(db, task["id"], output)
    # Settle in a separate, case-first transaction so this run's copy is handed
    # over without inverting the lock order of a concurrent purge.
    retention.settle(task["case_id"], "worker")
    return True


class JobFailure(Exception):
    def __init__(self, run_id, case_id, cause):
        super().__init__(str(cause))
        self.run_id = run_id
        self.case_id = case_id
        self.cause = cause


def fail(job_failure):
    with engine.begin() as db:
        run_id = job_failure.run_id
        statement = select(runs.c.status).where(runs.c.id == run_id).with_for_update()
        if db.scalar(statement) != JobState.QUEUED:
            return
        cause = job_failure.cause
        if isinstance(cause, (ValueError, TypeError, KeyError, OverflowError)):
            reason = str(cause) or "输入资料或批次参数不符合要求"
        else:
            reason = "处理失败，请检查 worker 日志"
        finish(db, run_id, {"status": JobState.FAILED, "failure": reason[:320]})
    retention.settle(job_failure.case_id, "worker")


def finish(db, run_id, output):
    db.execute(update(runs).where(runs.c.id == run_id).values(**output, finished_at=int(time())))
    record(db, str(output["status"]), "worker", "run", run_id)
