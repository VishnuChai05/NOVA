from pathlib import Path
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_DIR.parent
_ENV_FILES = (str(_REPO_ROOT / ".env"), str(_BACKEND_DIR / ".env"))


def _default_database_url() -> str:
    return f"sqlite:///{(_BACKEND_DIR / 'ohsou.db').resolve().as_posix()}"


def _normalize_sqlite_url(database_url: str) -> str:
    parts = urlsplit(database_url)
    if parts.scheme != "sqlite" or not parts.path:
        return database_url

    raw_path = parts.path
    if raw_path.startswith("//"):
        database_path = Path(raw_path)
    else:
        database_path = Path(raw_path.lstrip("/"))

    if not database_path.is_absolute():
        database_path = (_BACKEND_DIR / database_path).resolve()
    else:
        database_path = database_path.resolve()

    if database_path.drive:
        normalized = f"sqlite:///{database_path.as_posix()}"
    else:
        normalized = f"sqlite:////{database_path.as_posix().lstrip('/')}"

    if parts.query:
        normalized = f"{normalized}?{parts.query}"
    if parts.fragment:
        normalized = f"{normalized}#{parts.fragment}"

    return normalized


def _normalize_postgres_url(database_url: str) -> str:
    # Railway commonly provides postgres:// or postgresql:// URLs.
    # Force SQLAlchemy to use psycopg (v3) instead of defaulting to psycopg2.
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://") :]
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    return database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "NOVA"
    environment: str = "dev"
    database_url: str = _default_database_url()
    frontend_url: str = "http://localhost:5173"
    api_auth_enabled: bool = True
    operational_api_key: str = "change-me"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    engine_default_provider: str = "groq"

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "nova-content-engine/1.0"
    reddit_source_mode: str = "auto"

    apify_api_token: str = ""
    apify_reddit_actor_id: str = "apify/google-search-scraper"
    apify_quora_actor_id: str = "apify/google-search-scraper"
    apify_actor_id: str = "apify/google-search-scraper"
    scraper_config_path: str = "config.yaml"
    allow_fallback_seed_data: bool = True
    scraper_retry_attempts: int = 3
    scraper_backoff_base_seconds: float = 1.0
    reddit_query_delay_seconds: float = 0.35
    blog_crawl_max_urls_per_domain: int = 120
    blog_crawl_timeout_seconds: float = 10.0
    insight_validator_provider: str = "template"
    insight_max_suggestions: int = 5
    compliance_purge_enabled: bool = False
    scraped_data_retention_days: int = 30
    continuous_scrape_enabled: bool = False
    continuous_scrape_interval_minutes: int = 60

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        self.database_url = _normalize_postgres_url(self.database_url)
        self.database_url = _normalize_sqlite_url(self.database_url)
        return self


settings = Settings()
