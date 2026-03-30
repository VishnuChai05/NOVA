from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from app.core.settings import settings
from app.db.session import SessionLocal
from app.services.scraper import run_scrape

logger = logging.getLogger(__name__)

_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()
_wake_event = threading.Event()
_state_lock = threading.Lock()
_interval_minutes = max(5, int(settings.continuous_scrape_interval_minutes))
_last_run_started_at: datetime | None = None
_last_run_finished_at: datetime | None = None
_last_run_status: str | None = None


def _get_interval_seconds() -> int:
    with _state_lock:
        return max(300, _interval_minutes * 60)


def _scrape_loop() -> None:
    logger.info("Continuous scraper started. interval_seconds=%s", _get_interval_seconds())

    while not _stop_event.is_set():
        with _state_lock:
            global _last_run_started_at
            _last_run_started_at = datetime.now(timezone.utc)

        started_at = time.monotonic()
        db = SessionLocal()
        try:
            result = run_scrape(db)
            with _state_lock:
                global _last_run_status
                _last_run_status = result.status
            logger.info(
                "Continuous scrape complete. run_id=%s fetched=%s created=%s status=%s",
                result.run_id,
                result.fetched,
                result.created,
                result.status,
            )
        except Exception:  # noqa: BLE001
            with _state_lock:
                _last_run_status = "failed"
            logger.exception("Continuous scrape run failed")
        finally:
            with _state_lock:
                global _last_run_finished_at
                _last_run_finished_at = datetime.now(timezone.utc)
            db.close()

        elapsed = time.monotonic() - started_at
        interval_seconds = _get_interval_seconds()
        wait_seconds = max(0.0, interval_seconds - elapsed)
        _wake_event.wait(wait_seconds)
        _wake_event.clear()

    logger.info("Continuous scraper stopped")


def start_continuous_scraper(respect_config: bool = False) -> bool:
    global _scheduler_thread

    if respect_config and not settings.continuous_scrape_enabled:
        logger.info("Continuous scraper disabled by configuration")
        return False

    if _scheduler_thread and _scheduler_thread.is_alive():
        return False

    _stop_event.clear()
    _wake_event.clear()
    _scheduler_thread = threading.Thread(target=_scrape_loop, name="continuous-scrape", daemon=True)
    _scheduler_thread.start()
    return True


def stop_continuous_scraper() -> bool:
    global _scheduler_thread

    if not _scheduler_thread or not _scheduler_thread.is_alive():
        return False

    _stop_event.set()
    _wake_event.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=5)
    _scheduler_thread = None
    return True


def set_scrape_interval_minutes(interval_minutes: int) -> int:
    global _interval_minutes

    with _state_lock:
        _interval_minutes = max(5, int(interval_minutes))

    _wake_event.set()
    return _interval_minutes


def get_scrape_scheduler_status() -> dict:
    running = bool(_scheduler_thread and _scheduler_thread.is_alive())
    with _state_lock:
        return {
            "running": running,
            "interval_minutes": _interval_minutes,
            "last_run_started_at": _last_run_started_at,
            "last_run_finished_at": _last_run_finished_at,
            "last_run_status": _last_run_status,
        }
