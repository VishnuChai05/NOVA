from __future__ import annotations

import logging
import os

from redis import Redis
from rq import Connection, SimpleWorker, Worker
from rq.timeouts import TimerDeathPenalty

from app.core.settings import settings

logger = logging.getLogger(__name__)


def main() -> None:
    """Start an RQ worker for scrape jobs."""
    redis_conn = Redis.from_url(settings.redis_url)
    queue_name = settings.scrape_job_queue_name

    logger.info("Starting RQ worker. queue=%s redis=%s", queue_name, settings.redis_url)
    with Connection(redis_conn):
        if os.name == "nt":
            # Windows has no os.fork; SimpleWorker keeps execution in-process.
            worker = SimpleWorker([queue_name])
            worker.death_penalty_class = TimerDeathPenalty
            worker.work(with_scheduler=False)
        else:
            worker = Worker([queue_name])
            worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
