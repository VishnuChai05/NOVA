from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.settings import settings


def main() -> int:
    db_url = settings.database_url
    engine = create_engine(db_url, future=True)

    with engine.connect() as connection:
        tables = [row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))]

    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    command = [sys.executable, "-m", "alembic", "-c", str(alembic_ini)]
    db_path = Path(engine.url.database or "")

    if tables:
        command.extend(["stamp", "head"])
    else:
        command.extend(["upgrade", "head"])

    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())