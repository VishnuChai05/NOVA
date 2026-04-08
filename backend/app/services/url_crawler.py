"""
URL discovery and domain crawling service.

Responsibilities:
- Discover URLs from sitemaps and homepages
- Crawl blog and forum domains for content
- Extract content titles from HTML
"""

import logging
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from bs4.exceptions import FeatureNotFound

from app.core.settings import settings
from app.services.content_fetcher import ContentFetcher

try:
    import feedparser
except ImportError:  # pragma: no cover - optional dependency
    feedparser = None

logger = logging.getLogger(__name__)


class URLCrawler:
    """Discovers and crawls URLs from domains."""

    def __init__(self, content_fetcher: ContentFetcher | None = None):
        """Initialize crawler with optional content fetcher."""
        self.fetcher = content_fetcher or ContentFetcher()

    def normalize_url(self, url: str) -> str:
        """Normalize URL format."""
        u = (url or "").strip()
        if u.startswith("//"):
            return f"https:{u}"
        return u

    def derive_title_from_url(self, url: str) -> str:
        """Derive readable title from URL slug."""
        path = (urlparse(url).path or "").strip("/")
        if not path:
            host = (urlparse(url).hostname or "article").replace("www.", "")
            return host.title()
        slug = unquote(path.split("/")[-1]).replace("-", " ").replace("_", " ").strip()
        import re
        slug = re.sub(r"\s+", " ", slug)
        return (slug.title() or "Blog content")[:180]

    def extract_content_title(self, body: str, url: str, page_title: str | None = None) -> str:
        """
        Extract meaningful title from HTML body.
        
        Filters boilerplate markers like "Skip to content", "Menu", etc.
        Falls back to URL-derived title if no good candidate found.
        
        Args:
            body: Extracted HTML text
            url: Original URL (for fallback)
            
        Returns:
            Title candidate (max 180 chars)
        """
        noise_markers = {
            "skip to content",
            "menu",
            "search",
            "home",
            "read more",
            "share",
            "table of contents",
        }
        for candidate in [page_title or "", *body.splitlines()]:
            candidate = candidate.strip()
            if len(candidate) < 12:
                continue
            lowered = candidate.lower()
            if lowered in noise_markers:
                continue
            if any(lowered.startswith(marker + " ") for marker in noise_markers):
                continue
            if lowered.startswith("http"):
                continue
            return candidate[:180]
        return self.derive_title_from_url(url)

    def url_matches_domains(self, url: str, domains: list[str]) -> bool:
        """Check if URL belongs to any of the specified domains."""
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return False
        for domain in domains:
            d = domain.strip().lower()
            if not d:
                continue
            if host == d or host.endswith(f".{d}"):
                return True
        return False

    def parse_sitemap_document(self, raw_text: str) -> BeautifulSoup:
        """Parse sitemap content using XML parser when available, else fallback to html.parser."""
        try:
            return BeautifulSoup(raw_text, "xml")
        except FeatureNotFound:
            # Some environments do not have an XML parser backend (e.g., lxml).
            # html.parser can still parse <loc> entries safely for sitemap discovery.
            return BeautifulSoup(raw_text, "html.parser")

    def discover_urls_from_sitemap(self, domain: str, max_urls: int) -> tuple[list[str], list[str]]:
        """
        Discover URLs from sitemap.xml or sitemap_index.xml.
        
        Args:
            domain: Domain to scan
            max_urls: Maximum URLs to return
            
        Returns:
            (urls list, failures list)
        """
        base = domain if domain.startswith("http") else f"https://{domain}"
        base = base.rstrip("/")
        candidates = [f"{base}/sitemap.xml", f"{base}/sitemap_index.xml"]
        found: set[str] = set()
        failures: list[str] = []

        headers = {"User-Agent": settings.reddit_user_agent}
        with httpx.Client(
            timeout=getattr(settings, "blog_crawl_timeout_seconds", 10.0),
            headers=headers,
            follow_redirects=True,
        ) as client:
            visited_sitemaps: set[str] = set()
            queue = candidates[:]
            while queue and len(found) < max_urls:
                sitemap_url = queue.pop(0)
                if sitemap_url in visited_sitemaps:
                    continue
                visited_sitemaps.add(sitemap_url)

                try:
                    response = client.get(sitemap_url)
                    response.raise_for_status()
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"sitemap fetch failed {sitemap_url}: {exc}")
                    continue

                soup = self.parse_sitemap_document(response.text)
                # sitemap index -> nested sitemap URLs
                for loc in soup.find_all("loc"):
                    loc_url = self.normalize_url(loc.get_text(" ", strip=True))
                    if not loc_url:
                        continue
                    if loc_url.endswith(".xml") and loc_url not in visited_sitemaps:
                        queue.append(loc_url)
                    elif self.url_matches_domains(loc_url, [urlparse(base).hostname or domain]):
                        found.add(loc_url)
                        if len(found) >= max_urls:
                            break

        return list(found)[:max_urls], failures

    def discover_urls_from_homepage(self, domain: str, max_urls: int) -> tuple[list[str], list[str]]:
        """
        Discover URLs by crawling homepage.
        
        Extracts links from <a> tags, filters non-content routes, and media files.
        
        Args:
            domain: Domain to crawl
            max_urls: Maximum URLs to return
            
        Returns:
            (urls list, failures list)
        """
        base = domain if domain.startswith("http") else f"https://{domain}"
        base = base.rstrip("/")
        headers = {"User-Agent": settings.reddit_user_agent}
        failures: list[str] = []
        found: set[str] = set()

        try:
            with httpx.Client(
                timeout=getattr(settings, "blog_crawl_timeout_seconds", 10.0),
                headers=headers,
                follow_redirects=True,
            ) as client:
                response = client.get(base)
                response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as exc:  # noqa: BLE001
            return [], [f"homepage fetch failed {base}: {exc}"]

        for a in soup.select("a[href]"):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            url = self.normalize_url(urljoin(base + "/", href))
            if not self.url_matches_domains(url, [urlparse(base).hostname or domain]):
                continue
            # keep likely content pages, skip obvious non-content routes.
            lowered = url.lower()
            if any(token in lowered for token in ["/tag/", "/author/", "/wp-json", "/feed", "?replytocom="]):
                continue
            if lowered.endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js", ".xml", ".pdf")):
                continue
            found.add(url)
            if len(found) >= max_urls:
                break

        return list(found)[:max_urls], failures

    def discover_urls_from_feed(self, domain: str, max_urls: int) -> tuple[list[str], list[str]]:
        """Discover URLs from RSS/Atom feeds before falling back to HTML crawling."""
        if feedparser is None:
            return [], []

        base = domain if domain.startswith("http") else f"https://{domain}"
        base = base.rstrip("/")
        feed_candidates = [
            f"{base}/feed",
            f"{base}/rss",
            f"{base}/rss.xml",
            f"{base}/atom.xml",
        ]

        failures: list[str] = []
        found: list[str] = []
        seen: set[str] = set()

        for feed_url in feed_candidates:
            try:
                parsed = feedparser.parse(feed_url)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"feed fetch failed {feed_url}: {exc}")
                continue

            entries = parsed.entries or []
            for entry in entries:
                link = self.normalize_url(str(getattr(entry, "link", "") or ""))
                if not link or link in seen:
                    continue
                if not self.url_matches_domains(link, [urlparse(base).hostname or domain]):
                    continue
                if link.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js", ".pdf", ".xml")):
                    continue
                seen.add(link)
                found.append(link)
                if len(found) >= max_urls:
                    return found[:max_urls], failures

        return found[:max_urls], failures

    def crawl_domains(
        self,
        source_name: str,
        domains: list[str],
        max_posts_per_source: int,
        max_urls_per_domain: int,
    ) -> dict:
        """
        Crawl domains for content URLs and extract content.
        
        BUG FIX #1: Previously hard-capped to 3 URLs via min(3, ...).
        Now respects max_urls_per_domain setting fully.
        
        Args:
            source_name: Source identifier (e.g., "blog_crawl")
            domains: Domains to crawl
            max_posts_per_source: Total post limit for this source
            max_urls_per_domain: Max URLs per domain (now properly respected)
            
        Returns:
            {"rows": [...], "failures": [...]}
        """
        # BUG FIX #1: Remove hard-cap. Use max_urls_per_domain directly.
        # Previously: max_per_domain = max(1, min(3, int(max_urls_per_domain)))
        # Now: Respect the configured value.
        max_per_domain = max(1, int(max_urls_per_domain))

        rows: list[dict] = []
        failures: list[str] = []

        for domain in domains:
            normalized_domain = domain.strip().lower()
            if not normalized_domain or normalized_domain in {"reddit.com", "quora.com"}:
                continue

            feed_urls, feed_failures = self.discover_urls_from_feed(normalized_domain, max_per_domain)
            sitemap_urls, sitemap_failures = self.discover_urls_from_sitemap(normalized_domain, max_per_domain)
            homepage_urls, homepage_failures = self.discover_urls_from_homepage(normalized_domain, max_per_domain)
            failures.extend(feed_failures)
            failures.extend(sitemap_failures)
            failures.extend(homepage_failures)

            candidate_urls = self._dedupe_urls(
                [{"url": u} for u in (feed_urls + sitemap_urls + homepage_urls)]
            )
            for item in candidate_urls[:max_per_domain]:
                url = item["url"]
                details = self.fetcher.fetch_page_details(url)
                body = str(details.get("body") or "")
                if not body or len(body) < 200:
                    continue
                title = self.extract_content_title(body, url, page_title=str(details.get("title") or ""))
                published_at = details.get("published_at")
                rows.append(
                    {
                        "source": source_name,
                        "title": title,
                        "body": body,
                        "score": 0,
                        "url": url,
                        "published_at": published_at.isoformat() if published_at else None,
                    }
                )
                if len(rows) >= max_posts_per_source:
                    return {"rows": rows, "failures": failures}

        return {"rows": rows, "failures": failures}

    def crawl_blog_domains(
        self,
        domains: list[str],
        max_posts_per_source: int,
        blog_crawl_max_urls_per_domain: int,
    ) -> dict:
        """Crawl blog domains."""
        return self.crawl_domains(
            source_name="blog_crawl",
            domains=domains,
            max_posts_per_source=max_posts_per_source,
            max_urls_per_domain=blog_crawl_max_urls_per_domain,
        )

    def crawl_forum_domains(
        self,
        domains: list[str],
        max_posts_per_source: int,
    ) -> dict:
        """Crawl forum domains (with fixed max URLs)."""
        return self.crawl_domains(
            source_name="discussion_forums",
            domains=domains,
            max_posts_per_source=max_posts_per_source,
            max_urls_per_domain=8,
        )

    @staticmethod
    def _dedupe_urls(rows: list[dict]) -> list[dict]:
        """Deduplicate rows by URL."""
        seen: set[str] = set()
        deduped: list[dict] = []
        for row in rows:
            url = str(row.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            deduped.append(row)
        return deduped
