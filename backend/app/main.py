from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.blog import router as blog_router
from app.api.routes.generate import router as generate_router
from app.api.routes.health import router as health_router
from app.api.routes.scrape import router as scrape_router
from app.core.settings import settings
from app.db.init_db import init_db
from app.services.scrape_scheduler import start_continuous_scraper, stop_continuous_scraper


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    start_continuous_scraper()
    yield
    stop_continuous_scraper()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(blog_router, prefix="/api")
app.include_router(scrape_router, prefix="/api")
app.include_router(generate_router, prefix="/api")
