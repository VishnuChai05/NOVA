from __future__ import annotations

import logging
import threading
import time

from app.core.settings import settings
from app.db.session import SessionLocal
from app.services.scraper import run_scrape

logger = logging.getLogger(__name__)

_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _scrape_loop() -> None:
    interval_seconds = max(300, int(settings.continuous_scrape_interval_minutes) * 60)
    logger.info("Continuous scraper started. interval_seconds=%s", interval_seconds)

    while not _stop_event.is_set():
        started_at = time.monotonic()
        db = SessionLocal()
        try:
            result = run_scrape(db)
            logger.info(
                "Continuous scrape complete. run_id=%s fetched=%s created=%s status=%s",
                result.run_id,
                result.fetched,
                result.created,
                result.status,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Continuous scrape run failed")
        finally:
            db.close()

        elapsed = time.monotonic() - started_at
        wait_seconds = max(0.0, interval_seconds - elapsed)
        _stop_event.wait(wait_seconds)

    logger.info("Continuous scraper stopped")


def start_continuous_scraper() -> None:
    global _scheduler_thread

    if not settings.continuous_scrape_enabled:
        logger.info("Continuous scraper disabled by configuration")
        return

    if _scheduler_thread and _scheduler_thread.is_alive():
        return

    _stop_event.clear()
    _scheduler_thread = threading.Thread(target=_scrape_loop, name="continuous-scrape", daemon=True)
    _scheduler_thread.start()


def stop_continuous_scraper() -> None:
    global _scheduler_thread

    _stop_event.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=5)
    _scheduler_thread = None
