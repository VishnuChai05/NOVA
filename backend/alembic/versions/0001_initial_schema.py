"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-04-06 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blog_post_index",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_blog_post_index_slug", "blog_post_index", ["slug"])
    op.create_index("ix_blog_post_index_category", "blog_post_index", ["category"])
    op.create_index("ix_blog_post_index_published_at", "blog_post_index", ["published_at"])
    op.create_index("ix_blog_post_index_source_id", "blog_post_index", ["source_id"])

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("template_type", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_prompt_templates_template_type", "prompt_templates", ["template_type"])
    op.create_index("ix_prompt_templates_version", "prompt_templates", ["version"])

    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_fetched", sa.Integer(), nullable=False),
        sa.Column("total_created", sa.Integer(), nullable=False),
        sa.Column("source_stats_json", sa.Text(), nullable=False),
        sa.Column("failures_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_scrape_runs_started_at", "scrape_runs", ["started_at"])

    op.create_table(
        "scraped_posts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("category_tag", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("url", name="uq_scraped_posts_url"),
    )
    op.create_index("ix_scraped_posts_published_at", "scraped_posts", ["published_at"])
    op.create_index("ix_scraped_posts_scraped_at", "scraped_posts", ["scraped_at"])
    op.create_index("ix_scraped_posts_source", "scraped_posts", ["source"])
    op.create_index("ix_scraped_posts_processed", "scraped_posts", ["processed"])
    op.create_index("ix_scraped_posts_category_tag", "scraped_posts", ["category_tag"])

    op.create_table(
        "generated_outputs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("output_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["scraped_posts.id"]),
    )
    op.create_index("ix_generated_outputs_post_id", "generated_outputs", ["post_id"])
    op.create_index("ix_generated_outputs_output_type", "generated_outputs", ["output_type"])
    op.create_index("ix_generated_outputs_status", "generated_outputs", ["status"])
    op.create_index("ix_generated_outputs_generated_at", "generated_outputs", ["generated_at"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("output_id", sa.String(length=36), nullable=False),
        sa.Column("evaluator_model", sa.String(length=128), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rubric_json", sa.Text(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["output_id"], ["generated_outputs.id"]),
    )
    op.create_index("ix_evaluation_results_output_id", "evaluation_results", ["output_id"])

    op.create_table(
        "scraped_insights",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("provider_used", sa.String(length=32), nullable=False),
        sa.Column("model_used", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("primary_topic", sa.String(length=120), nullable=False),
        sa.Column("suggestions_json", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["scraped_posts.id"]),
    )
    op.create_index("ix_scraped_insights_post_id", "scraped_insights", ["post_id"])
    op.create_index("ix_scraped_insights_primary_topic", "scraped_insights", ["primary_topic"])
    op.create_index("ix_scraped_insights_created_at", "scraped_insights", ["created_at"])

    op.create_table(
        "scrape_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress_pct", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_scrape_jobs_status", "scrape_jobs", ["status"])
    op.create_index("ix_scrape_jobs_created_at", "scrape_jobs", ["created_at"])
    op.create_index("ix_scrape_jobs_finished_at", "scrape_jobs", ["finished_at"])


def downgrade() -> None:
    op.drop_table("scraped_insights")
    op.drop_table("evaluation_results")
    op.drop_table("generated_outputs")
    op.drop_table("scraped_posts")
    op.drop_table("scrape_runs")
    op.drop_table("prompt_templates")
    op.drop_table("scrape_jobs")
    op.drop_table("blog_post_index")