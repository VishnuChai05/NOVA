import os
from pathlib import Path


_TEST_DB_PATH = Path(__file__).resolve().parent / ".pytest_ohsou.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"


def pytest_sessionstart(session):
    if _TEST_DB_PATH.exists():
        try:
            _TEST_DB_PATH.unlink()
        except PermissionError:
            pass


def pytest_sessionfinish(session, exitstatus):
    if _TEST_DB_PATH.exists():
        try:
            _TEST_DB_PATH.unlink()
        except PermissionError:
            pass
