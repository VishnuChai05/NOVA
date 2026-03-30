from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "oh so u AI Content Engine"
    environment: str = "dev"
    database_url: str = "sqlite:///./ohsou.db"
    frontend_url: str = "http://localhost:5173"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ohsou-content-engine/1.0"
    reddit_source_mode: str = "auto"

    apify_api_token: str = ""
    apify_reddit_actor_id: str = "apify/reddit-post-scraper"
    apify_quora_actor_id: str = "apify/website-content-crawler"
    apify_actor_id: str = "apify/google-search-scraper"
    scraper_config_path: str = "config.yaml"
    allow_fallback_seed_data: bool = True
    scraper_retry_attempts: int = 3
    scraper_backoff_base_seconds: float = 1.0
    reddit_query_delay_seconds: float = 0.35


settings = Settings()
