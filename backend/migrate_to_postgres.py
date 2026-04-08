"""
migrate_to_postgres.py
----------------------
One-time script to migrate all data from the local SQLite database (ohsou.db)
to a Supabase Postgres database.

Usage:
    python migrate_to_postgres.py --postgres-url "postgresql://postgres:PASSWORD@db.XXXX.supabase.co:5432/postgres"

The script will:
1. Connect to both databases
2. Run Alembic migrations on Postgres to create the schema
3. Copy all rows from every table (in dependency order) from SQLite to Postgres
4. Print a summary of rows migrated per table
"""

import argparse
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# Tables in insertion order (parents before children)
TABLES_IN_ORDER = [
    "blog_post_index",
    "prompt_templates",
    "scrape_runs",
    "scraped_posts",
    "generated_outputs",
    "evaluation_results",
    "scraped_insights",
    "scrape_jobs",
]


def migrate(postgres_url: str, sqlite_path: str, dry_run: bool) -> None:
    try:
        import sqlalchemy as sa
    except ImportError:
        logger.error("sqlalchemy not installed. Run: pip install sqlalchemy psycopg[binary]")
        sys.exit(1)

    # Normalize postgres URL for psycopg v3
    if postgres_url.startswith("postgresql://"):
        postgres_url = "postgresql+psycopg://" + postgres_url[len("postgresql://"):]
    elif postgres_url.startswith("postgres://"):
        postgres_url = "postgresql+psycopg://" + postgres_url[len("postgres://"):]

    sqlite_url = f"sqlite:///{sqlite_path}"
    logger.info("Source (SQLite): %s", sqlite_path)
    logger.info("Target (Postgres): ...@%s", postgres_url.split("@")[-1])

    sqlite_engine = sa.create_engine(sqlite_url, connect_args={"check_same_thread": False})
    pg_engine = sa.create_engine(postgres_url, future=True)

    # Run alembic migrations on the target postgres DB first
    if not dry_run:
        logger.info("Running alembic upgrade head on Postgres...")
        import subprocess
        import os
        env = os.environ.copy()
        env["DATABASE_URL"] = postgres_url
        result = subprocess.run(
            ["python", "-m", "alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error("Alembic migration failed:\n%s", result.stderr)
            sys.exit(1)
        logger.info("Alembic migrations applied successfully.")

    total_migrated = 0

    with sqlite_engine.connect() as sqlite_conn:
        with pg_engine.begin() as pg_conn:
            for table_name in TABLES_IN_ORDER:
                # Check if table exists in SQLite
                try:
                    rows = sqlite_conn.execute(
                        sa.text(f"SELECT * FROM {table_name}")  # noqa: S608
                    ).mappings().all()
                except Exception:
                    logger.warning("Table '%s' not found in SQLite — skipping.", table_name)
                    continue

                if not rows:
                    logger.info("Table '%s': 0 rows — skipping.", table_name)
                    continue

                logger.info("Table '%s': migrating %d rows...", table_name, len(rows))

                if not dry_run:
                    # Delete existing data in Postgres to allow re-runs safely
                    pg_conn.execute(sa.text(f"DELETE FROM {table_name}"))  # noqa: S608

                    # Insert in chunks of 500
                    chunk_size = 500
                    row_dicts = [dict(r) for r in rows]
                    for i in range(0, len(row_dicts), chunk_size):
                        chunk = row_dicts[i : i + chunk_size]
                        pg_conn.execute(
                            sa.text(
                                f"INSERT INTO {table_name} ({', '.join(chunk[0].keys())}) "  # noqa: S608
                                f"VALUES ({', '.join(':' + k for k in chunk[0].keys())})"
                            ),
                            chunk,
                        )
                    logger.info("Table '%s': ✓ %d rows inserted.", table_name, len(rows))
                else:
                    logger.info("Table '%s': [DRY RUN] would insert %d rows.", table_name, len(rows))

                total_migrated += len(rows)

    logger.info("")
    logger.info("=" * 50)
    if dry_run:
        logger.info("DRY RUN complete. Total rows that would be migrated: %d", total_migrated)
        logger.info("Run without --dry-run to execute the migration.")
    else:
        logger.info("Migration complete! Total rows migrated: %d", total_migrated)
    logger.info("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate NOVA SQLite data to Supabase Postgres")
    parser.add_argument(
        "--postgres-url",
        required=True,
        help="Supabase connection string, e.g. postgresql://postgres:PASSWORD@db.XXX.supabase.co:5432/postgres",
    )
    parser.add_argument(
        "--sqlite-path",
        default="ohsou.db",
        help="Path to the SQLite database file (default: ohsou.db in current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only count rows, do NOT write to Postgres",
    )
    args = parser.parse_args()
    migrate(args.postgres_url, args.sqlite_path, args.dry_run)


if __name__ == "__main__":
    main()
