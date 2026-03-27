from collections import Counter
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models.blog_post_index import BlogPostIndex

WP_POSTS_URL = "https://blog.ohsou.com/wp-json/wp/v2/posts"

CATEGORY_MAP = {
    "bra": "bra",
    "shapewear": "shapewear",
    "panty": "panty",
    "fashion": "fashion",
}


def _normalize_category(raw: str) -> str:
    value = (raw or "").strip().lower()
    return CATEGORY_MAP.get(value, "other")


def refresh_blog_index(db: Session) -> None:
    params = {"per_page": 100, "page": 1}
    posts: list[dict] = []

    with httpx.Client(timeout=20) as client:
        while True:
            response = client.get(WP_POSTS_URL, params=params)
            response.raise_for_status()
            batch = response.json()
            if not batch:
                break
            posts.extend(batch)
            total_pages = int(response.headers.get("X-WP-TotalPages", "1"))
            if params["page"] >= total_pages:
                break
            params["page"] += 1

    db.query(BlogPostIndex).delete()

    for post in posts:
        slug = post.get("slug", "")
        title = (post.get("title") or {}).get("rendered", "")
        categories = post.get("categories") or []
        category = _normalize_category(str(categories[0]) if categories else "")

        db.add(
            BlogPostIndex(
                title=title,
                slug=slug,
                category=category,
                published_at=datetime.now(timezone.utc),
                source_id=str(post.get("id", "")),
            )
        )

    db.commit()


def get_blog_count_summary(db: Session) -> dict:
    posts = db.query(BlogPostIndex).all()
    counts = Counter((p.category for p in posts))

    categories = {
        "bra": counts.get("bra", 0),
        "shapewear": counts.get("shapewear", 0),
        "panty": counts.get("panty", 0),
        "fashion": counts.get("fashion", 0),
        "other": counts.get("other", 0),
    }

    topic_gap_flags = [name for name, value in categories.items() if name != "other" and value < 5]

    return {
        "total": len(posts),
        "categories": categories,
        "last_updated": datetime.now(timezone.utc).date().isoformat(),
        "topic_gap_flags": topic_gap_flags,
    }
