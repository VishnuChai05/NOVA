from pathlib import Path

from app.core.settings import Settings


def test_relative_sqlite_url_resolves_to_backend_db() -> None:
    settings = Settings(database_url="sqlite:///./ohsou.db")
    expected_path = (Path(__file__).resolve().parents[1] / "ohsou.db").resolve().as_posix()
    assert settings.database_url == f"sqlite:///{expected_path}"
