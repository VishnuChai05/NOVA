from __future__ import annotations

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.blog_post_index import BlogPostIndex
from app.services import blog_counter
from app.services.blog_counter import get_blog_count_summary, refresh_blog_index


class _FakeResponse:
    def __init__(self, payload: list[dict], total_pages: int = 1) -> None:
        self._payload = payload
        self.headers = {"X-WP-TotalPages": str(total_pages)}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict]:
        return self._payload


class _FakeClient:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        if url.endswith("/categories"):
            return _FakeResponse(
                [
                    {"id": 101, "slug": "bra", "name": "Bra"},
                    {"id": 202, "slug": "shapewear", "name": "Shapewear"},
                    {"id": 303, "slug": "misc", "name": "Misc"},
                ]
            )

        if url.endswith("/posts"):
            return _FakeResponse(
                [
                    {"id": 1, "slug": "bra-fit", "title": {"rendered": "Bra fit"}, "categories": [101]},
                    {"id": 2, "slug": "shape-fit", "title": {"rendered": "Shape fit"}, "categories": [202]},
                    {"id": 3, "slug": "other-fit", "title": {"rendered": "Other fit"}, "categories": [999]},
                ]
            )

        raise AssertionError(f"Unexpected URL requested: {url}")


def test_refresh_blog_index_maps_category_ids_to_summary_buckets(monkeypatch) -> None:
    init_db()
    blog_counter._load_wordpress_category_lookup.cache_clear()
    monkeypatch.setattr(blog_counter.httpx, "Client", lambda timeout=20: _FakeClient(timeout=timeout))

    db = SessionLocal()
    try:
        db.query(BlogPostIndex).delete(synchronize_session=False)
        db.commit()

        refresh_blog_index(db)
        summary = get_blog_count_summary(db)

        assert summary["total"] == 3
        assert summary["categories"]["bra"] == 1
        assert summary["categories"]["shapewear"] == 1
        assert summary["categories"]["other"] == 1
    finally:
        db.close()
