"""
Data processing for scraped content.

Responsibilities:
- Deduplicate by URL
- Classify topics from content
- Filter low-quality posts
"""

import re

logger = None  # Import logging if needed


_CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "bra": {
        "bra",
        "bras",
        "bralette",
        "bralettes",
        "sports bra",
        "nursing bra",
        "strapless bra",
    },
    "shapewear": {
        "shapewear",
        "body shaper",
        "waist trainer",
        "tummy tucker",
        "corset",
    },
    "panty": {
        "panty",
        "panties",
        "underwear",
        "briefs",
        "thong",
        "boyshorts",
        "hipster",
    },
    "fashion": {
        "fashion",
        "outfit",
        "outfits",
        "styling",
        "wardrobe",
        "ootd",
        "dress",
    },
    "skincare": {
        "skincare",
        "skin care",
        "moisturizer",
        "sunscreen",
        "serum",
        "cleanser",
        "acne",
    },
    "hygiene": {
        "hygiene",
        "intimate wash",
        "vaginal health",
        "uti",
        "infection",
        "ph balance",
    },
    "period-care": {
        "period",
        "periods",
        "menstrual",
        "menstruation",
        "sanitary pad",
        "sanitary pads",
        "tampon",
        "tampons",
        "menstrual cup",
        "period panty",
        "period panties",
        "cramps",
    },
}


class ScrapedDataProcessor:
    """Processes scraped content data."""

    @staticmethod
    def classify_topic(text: str) -> str:
        """
        Classify text into categories based on keyword matching.
        
        Args:
            text: Combined title + body text
            
        Returns:
            Category name or "other"
        """
        words = text.lower()
        best_category = "other"
        best_hits = 0

        for category, keywords in _CATEGORY_KEYWORDS.items():
            hits = sum(1 for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", words))
            if hits > best_hits:
                best_hits = hits
                best_category = category

        return best_category

    @staticmethod
    def dedupe_by_url(rows: list[dict]) -> list[dict]:
        """
        Deduplicate rows by URL, keeping first occurrence.
        
        Args:
            rows: List of row dicts with 'url' key
            
        Returns:
            Deduplicated list
        """
        seen: set[str] = set()
        deduped: list[dict] = []
        for row in rows:
            url = str(row.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            deduped.append(row)
        return deduped

    @staticmethod
    def is_quality_post(post: dict, min_title_length: int = 10, min_body_length: int = 150) -> bool:
        """
        Check if post meets quality thresholds.
        
        Args:
            post: Post dict with title, body, etc.
            min_title_length: Minimum title character length
            min_body_length: Minimum body character length
            
        Returns:
            True if post passes quality checks
        """
        title = (post.get("title") or "").strip()
        body = (post.get("body") or "").strip()

        if len(title) < min_title_length:
            return False
        if len(body) < min_body_length:
            return False

        return True

    @staticmethod
    def seed_posts() -> list[dict]:
        """Return fallback seed data for testing/demo."""
        return [
            {
                "source": "reddit",
                "title": "Need a comfortable bra for long office days",
                "body": "My straps dig in by evening. Looking for seamless options.",
                "score": 41,
                "url": "https://reddit.com/r/ABraThatFits/sample-1",
            },
            {
                "source": "quora",
                "title": "What shapewear works under saree for weddings?",
                "body": "Seeking breathable support for long ceremonies.",
                "score": 27,
                "url": "https://quora.com/sample-1",
            },
        ]
