from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logging_config import setup_logging

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
_LEGACY_DB_PATH = _REPO_ROOT / "ohsou.db"


def _log_database_location() -> None:
    logger.info("SQLite database URL resolved to %s", settings.database_url)
    if _LEGACY_DB_PATH.exists():
        logger.warning(
            "Legacy database file detected at %s; the app now writes to the backend-owned path instead.",
            _LEGACY_DB_PATH,
        )

from app.api.routes.blog import router as blog_router
from app.api.routes.engine import router as engine_router
from app.api.routes.generate import router as generate_router
from app.api.routes.health import router as health_router
from app.api.routes.scrape import router as scrape_router
from app.core.settings import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.compliance import run_compliance_maintenance
from app.services.scrape_scheduler import start_continuous_scraper, stop_continuous_scraper


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    _log_database_location()

    if settings.compliance_purge_enabled:
        with SessionLocal() as db:
            purged_count = run_compliance_maintenance(db)
            if purged_count:
                logger.info("Compliance startup purge removed %s old scraped rows", purged_count)

    start_continuous_scraper(respect_config=True)
    yield
    stop_continuous_scraper()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


def _allowed_origins(frontend_url: str) -> list[str]:
    base = (frontend_url or "").strip().rstrip("/")
    origins = {base} if base else set()

    parsed = urlparse(base)
    if parsed.scheme and parsed.hostname and parsed.port:
        if parsed.hostname == "localhost":
            origins.add(f"{parsed.scheme}://127.0.0.1:{parsed.port}")
        elif parsed.hostname == "127.0.0.1":
            origins.add(f"{parsed.scheme}://localhost:{parsed.port}")

    return sorted(origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(settings.frontend_url),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(blog_router, prefix="/api")
app.include_router(scrape_router, prefix="/api")
app.include_router(engine_router, prefix="/api")
app.include_router(generate_router, prefix="/api")
