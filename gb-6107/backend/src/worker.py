import logging
import time

from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.config.resources import cache, engine
from src.services import retention
from src.services.execution import JobFailure, fail, service_one

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")


def check():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    heartbeat = cache.get("workbench:heartbeat")
    return heartbeat is not None and time.time() - float(heartbeat) < 90


def work():
    while True:
        try:
            cache.set("workbench:heartbeat", time.time(), ex=90)
            # Start clearing expired warranty batches even when no run is queued,
            # so no new inspection can be accepted after the deadline.
            retention.sweep()
            try:
                if service_one():
                    continue
            except JobFailure as exc:
                logger.exception("Execution %s failed", exc.run_id)
                fail(exc)
                continue
            cache.blpop("workbench:wake", timeout=1)
        except (RedisError, SQLAlchemyError):
            logger.exception("Worker connection unavailable")
            time.sleep(2)


if __name__ == "__main__":
    work()
