"""
Data processing for scraped content.

Responsibilities:
- Deduplicate by URL
- Classify topics from content
- Filter low-quality posts
"""

import re

logger = None  # Import logging if needed

_BINARY_SIGNATURES = (
    "jfif",
    "exif",
    "png",
    "gif89a",
    "%pdf",
)

_BOILERPLATE_TITLES = {
    "table of contents",
    "contents",
    "menu",
    "sitemap",
    "skip to content",
}

_RELEVANCE_POSITIVE_KEYWORDS = {
    "bra",
    "bralette",
    "shapewear",
    "panty",
    "underwear",
    "lingerie",
    "innerwear",
    "period",
    "menstrual",
    "pad",
    "tampon",
    "cup",
    "fit",
    "support",
    "comfort",
    "strap",
    "size",
    "seamless",
    "breathable",
    "chafing",
    "rash",
    "hygiene",
}

_RELEVANCE_NEGATIVE_KEYWORDS = {
    "bitcoin",
    "crypto",
    "nft",
    "casino",
    "betting",
    "politics",
    "election",
    "war",
    "stock market",
    "celebrity gossip",
    "movie review",
    "cricket",
    "football",
}


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

        lowered_title = title.lower()
        lowered_body_sample = body[:200].lower()
        normalized_title = " ".join(lowered_title.split())

        if normalized_title in _BOILERPLATE_TITLES or normalized_title.startswith("table of contents"):
            return False
        if any(marker in lowered_body_sample for marker in ("table of contents", "skip to content")):
            return False

        if any(sig in lowered_title for sig in _BINARY_SIGNATURES):
            return False
        if any(sig in lowered_body_sample for sig in _BINARY_SIGNATURES):
            return False

        if "\x00" in title or "\x00" in body[:500]:
            return False

        # Reject rows with too many replacement/garbled characters in title.
        noisy_chars = sum(1 for ch in title if ch in {"�", "ï", "¿"})
        if title and noisy_chars / max(1, len(title)) > 0.08:
            return False

        if len(title) < min_title_length:
            return False
        if len(body) < min_body_length:
            return False

        return True

    @staticmethod
    def relevance_score(post: dict) -> int:
        """Compute lightweight relevance score against comfort/innerwear intent."""
        title = (post.get("title") or "").lower()
        body = (post.get("body") or "").lower()
        text = f"{title} {body[:1200]}"

        positive_hits = sum(1 for keyword in _RELEVANCE_POSITIVE_KEYWORDS if keyword in text)
        negative_hits = sum(1 for keyword in _RELEVANCE_NEGATIVE_KEYWORDS if keyword in text)

        # Bias title hits slightly higher because titles usually encode primary intent.
        title_bonus = sum(1 for keyword in _RELEVANCE_POSITIVE_KEYWORDS if keyword in title)
        return positive_hits + title_bonus - (2 * negative_hits)

    @staticmethod
    def is_relevant_post(post: dict, min_score: int = 2) -> bool:
        """Filter out off-topic rows before expensive processing/classification."""
        return ScrapedDataProcessor.relevance_score(post) >= min_score

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
