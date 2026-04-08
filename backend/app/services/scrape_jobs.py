from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.scrape_job import ScrapeJob
from app.services.scraper import ConcurrentScrapeError, generate_insights_for_posts, run_scrape


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _set_job_state(
    db: Session,
    job: ScrapeJob,
    *,
    status: str | None = None,
    progress_pct: int | None = None,
    message: str | None = None,
    result_json: str | None = None,
    finished: bool = False,
) -> None:
    if status is not None:
        job.status = status
    if progress_pct is not None:
        job.progress_pct = max(0, min(100, int(progress_pct)))
    if message is not None:
        job.message = message
    if result_json is not None:
        job.result_json = result_json
    if finished:
        job.finished_at = _utc_now()
    db.commit()


def run_scrape_job(job_id: str) -> None:
    """RQ worker entrypoint for a scrape job id."""
    db = SessionLocal()
    try:
        job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
        if job is None:
            return

        _set_job_state(db, job, status="running", progress_pct=1, message="Job started")

        def progress_callback(progress: int, message: str) -> None:
            _set_job_state(db, job, status="running", progress_pct=progress, message=message)

        result = run_scrape(db, progress_callback=progress_callback, generate_insights=False, source_type=job.source_type)

        progress_callback(95, "Generating insights...")
        insight_failures = generate_insights_for_posts(result.created_post_ids or [], db)

        result_payload = {
            "run_id": result.run_id,
            "created": result.created,
            "fetched": result.fetched,
            "status": result.status,
            "message": result.message,
            "insight_failures": insight_failures,
        }
        _set_job_state(
            db,
            job,
            status="done",
            progress_pct=100,
            message="Done",
            result_json=json.dumps(result_payload),
            finished=True,
        )
    except ConcurrentScrapeError as exc:
        job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
        if job is not None:
            _set_job_state(
                db,
                job,
                status="failed",
                progress_pct=100,
                message=str(exc),
                finished=True,
            )
    except Exception as exc:  # noqa: BLE001
        job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
        if job is not None:
            _set_job_state(
                db,
                job,
                status="failed",
                progress_pct=100,
                message=f"Job failed: {exc}",
                finished=True,
            )
    finally:
        db.close()


def enqueue_scrape_job(job_id: str) -> str:
    """Enqueue scrape job id on RQ queue and return queue job id."""
    try:
        from redis import Redis
        from rq import Queue
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Missing redis/rq dependency") from exc

    connection = Redis.from_url(settings.redis_url)
    queue = Queue(settings.scrape_job_queue_name, connection=connection)
    rq_job = queue.enqueue(
        run_scrape_job,
        job_id,
        job_timeout=max(60, int(settings.scrape_job_timeout_seconds)),
    )
    return str(rq_job.id)


def reconcile_orphaned_scrape_jobs(db: Session) -> int:
    """Reconcile pending/running DB jobs with Redis queue state.

    A job can be left in pending/running when worker-level failures happen
    before run_scrape_job starts (e.g., platform timeout implementation errors).
    """
    try:
        from redis import Redis
        from rq import Queue
        from rq.job import Job
    except ImportError:
        return 0

    try:
        connection = Redis.from_url(settings.redis_url)
        queue = Queue(settings.scrape_job_queue_name, connection=connection)

        queued_ids = set(queue.job_ids)
        started_ids = set(queue.started_job_registry.get_job_ids())
        failed_ids = set(queue.failed_job_registry.get_job_ids())
    except Exception:  # noqa: BLE001
        return 0

    active_jobs = (
        db.query(ScrapeJob)
        .filter(ScrapeJob.status.in_(["pending", "running"]))
        .order_by(ScrapeJob.created_at.desc())
        .all()
    )

    if not active_jobs:
        return 0

    now = _utc_now()
    updated = 0

    def _as_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    for db_job in active_jobs:
        matched_failure: str | None = None
        matched_started_stale: str | None = None
        for rq_id in failed_ids:
            try:
                rq_job = Job.fetch(rq_id, connection=connection)
            except Exception:  # noqa: BLE001
                continue

            args = tuple(rq_job.args or ())
            if args and str(args[0]) == str(db_job.id):
                exc_info = rq_job.exc_info or ""
                first_line = exc_info.splitlines()[0].strip() if exc_info else "Worker execution failed"
                matched_failure = first_line or "Worker execution failed"
                break

        if not matched_failure:
            for rq_id in started_ids:
                try:
                    rq_job = Job.fetch(rq_id, connection=connection)
                except Exception:  # noqa: BLE001
                    continue

                args = tuple(rq_job.args or ())
                if not args or str(args[0]) != str(db_job.id):
                    continue

                # If a started job has not heartbeated for a while, the worker likely died.
                # Avoid leaving DB jobs forever in pending/running due stale Redis registry state.
                heartbeat = _as_utc(getattr(rq_job, "last_heartbeat", None))
                started_at = _as_utc(getattr(rq_job, "started_at", None))
                reference = heartbeat or started_at
                
                # Windows SimpleWorker executes synchronously and blocks heartbeats.
                # Use the configured job timeout plus a small buffer rather than 3 minutes.
                timeout_sec = int(settings.scrape_job_timeout_seconds)
                if reference and (now - reference) > timedelta(seconds=timeout_sec + 60):
                    matched_started_stale = "Queue stale: worker heartbeat expired"
                break

        if matched_failure:
            _set_job_state(
                db,
                db_job,
                status="failed",
                progress_pct=100,
                message=f"Queue failure: {matched_failure}",
                finished=True,
            )
            updated += 1
            continue

        if matched_started_stale:
            _set_job_state(
                db,
                db_job,
                status="failed",
                progress_pct=100,
                message=matched_started_stale,
                finished=True,
            )
            updated += 1
            continue

        # If no queued/started mapping exists after a grace period, mark stale.
        created_at = _as_utc(db_job.created_at)

        is_recent = bool(created_at and (now - created_at) <= timedelta(minutes=2))
        if not is_recent and not queued_ids and not started_ids:
            _set_job_state(
                db,
                db_job,
                status="failed",
                progress_pct=100,
                message="Queue stale: no matching queued/started worker job found",
                finished=True,
            )
            updated += 1

    return updated
