"""add source_type to scrape_jobs

Revision ID: 0002_add_source_type
Revises: 0001_initial_schema
Create Date: 2026-04-07 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_add_source_type"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scrape_jobs",
        sa.Column("source_type", sa.String(length=16), nullable=False, server_default="all"),
    )


def downgrade() -> None:
    op.drop_column("scrape_jobs", "source_type")
