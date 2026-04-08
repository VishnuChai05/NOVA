"""
HTTP content fetching with retry logic and error handling.

Responsibilities:
- Fetch and parse web pages with timeout handling
- Retry failed requests with exponential backoff
- Extract meaningful text content from HTML
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, TypeVar

import httpx
from bs4 import BeautifulSoup

from app.core.settings import settings

try:
    import trafilatura
except ImportError:  # pragma: no cover - optional dependency
    trafilatura = None

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ContentFetcher:
    """Fetches and processes web content with configurable retry logic."""

    def __init__(self, retry_attempts: int | None = None, backoff_base_seconds: float | None = None):
        """
        Initialize fetcher with retry configuration.
        
        Args:
            retry_attempts: Number of retry attempts (defaults to settings.scraper_retry_attempts)
            backoff_base_seconds: Base seconds for exponential backoff (defaults to settings.scraper_backoff_base_seconds)
        """
        self.retry_attempts = retry_attempts or max(1, int(settings.scraper_retry_attempts))
        self.backoff_base_seconds = backoff_base_seconds or max(0.1, float(settings.scraper_backoff_base_seconds))

    def retry_with_backoff(self, fn: Callable[[], T], label: str) -> T:
        """
        Execute function with exponential backoff retry.
        
        Retries on RuntimeError, httpx.HTTPStatusError, and httpx.TimeoutException.
        BUG FIX #2: Previously only caught RuntimeError. Now catches all network errors.
        
        Args:
            fn: Callable that returns result or raises exception
            label: Description for logging
            
        Returns:
            Result from fn() on success
            
        Raises:
            RuntimeError: If all retries exhausted
        """
        last_error: Exception | None = None

        for attempt in range(1, self.retry_attempts + 1):
            try:
                return fn()
            except (RuntimeError, httpx.HTTPStatusError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt == self.retry_attempts:
                    break
                wait_time = self.backoff_base_seconds * (2 ** (attempt - 1))
                logger.debug(f"{label} attempt {attempt}/{self.retry_attempts} failed, retrying in {wait_time:.1f}s: {exc}")
                time.sleep(wait_time)

        raise RuntimeError(
            f"{label} failed after {self.retry_attempts} attempts: {last_error}"
        ) from last_error

    def fetch_with_retry(self, url: str, **kwargs) -> httpx.Response:
        """
        Fetch URL with retry logic.
        
        Args:
            url: URL to fetch
            **kwargs: Additional httpx.Client arguments
            
        Returns:
            httpx.Response object
        """
        headers = kwargs.pop("headers", {})
        if not headers.get("User-Agent"):
            headers["User-Agent"] = getattr(settings, "reddit_user_agent", "nova-scraper/1.0")

        timeout = kwargs.pop("timeout", 10.0)

        def _fetch():
            with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True, **kwargs) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp

        return self.retry_with_backoff(_fetch, f"fetch {url}")

    @staticmethod
    def parse_datetime_value(value) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            dt = value
        else:
            text = str(value).strip()
            if not text:
                return None
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"

            dt = None
            try:
                dt = datetime.fromisoformat(text)
            except ValueError:
                try:
                    dt = parsedate_to_datetime(text)
                except (TypeError, ValueError):
                    return None

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _extract_title(soup: BeautifulSoup, default_snippet: str = "") -> str:
        candidates: list[str] = []

        for selector in (
            'meta[property="og:title"]',
            'meta[name="twitter:title"]',
            'meta[name="title"]',
            'meta[property="article:title"]',
        ):
            tag = soup.select_one(selector)
            if tag:
                content = (tag.get("content") or tag.get("value") or "").strip()
                if content:
                    candidates.append(content)

        if soup.title and soup.title.string:
            candidates.append(soup.title.string.strip())

        heading = soup.find("h1")
        if heading:
            heading_text = heading.get_text(" ", strip=True)
            if heading_text:
                candidates.append(heading_text)

        if default_snippet.strip():
            candidates.append(default_snippet.strip())

        for candidate in candidates:
            normalized = " ".join(candidate.split()).lower()
            if not normalized:
                continue
            if normalized in {"table of contents", "contents", "menu", "skip to content", "sitemap"}:
                continue
            if normalized.startswith("table of contents"):
                continue
            return candidate[:180]

        return default_snippet[:180]

    @staticmethod
    def _extract_published_at(soup: BeautifulSoup) -> datetime | None:
        selectors = (
            'meta[property="article:published_time"]',
            'meta[property="article:modified_time"]',
            'meta[property="og:updated_time"]',
            'meta[property="og:published_time"]',
            'meta[name="pubdate"]',
            'meta[name="publishdate"]',
            'meta[name="date"]',
            'meta[name="article:published_time"]',
            'meta[itemprop="datePublished"]',
            'meta[itemprop="dateCreated"]',
            'meta[itemprop="uploadDate"]',
            'time[datetime]',
        )

        for selector in selectors:
            for tag in soup.select(selector):
                candidate = tag.get("content") or tag.get("datetime") or tag.get("value") or tag.get_text(" ", strip=True)
                parsed = ContentFetcher.parse_datetime_value(candidate)
                if parsed:
                    return parsed

        for script in soup.select('script[type="application/ld+json"]'):
            raw = (script.string or script.get_text(strip=True) or "").strip()
            if not raw:
                continue
            try:
                parsed_json = json.loads(raw)
            except json.JSONDecodeError:
                continue

            candidates = parsed_json if isinstance(parsed_json, list) else [parsed_json]
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                for key in ("datePublished", "dateCreated", "uploadDate", "dateModified"):
                    parsed = ContentFetcher.parse_datetime_value(item.get(key))
                    if parsed:
                        return parsed

        return None

    @staticmethod
    def _extract_body_with_trafilatura(html: str, default_snippet: str = "") -> str:
        if trafilatura is None:
            return default_snippet

        try:
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                favor_recall=True,
                output_format="txt",
            )
        except Exception:  # noqa: BLE001
            return default_snippet

        if not extracted:
            return default_snippet

        body = re.sub(r"\n{3,}", "\n\n", str(extracted).strip())
        if len(body) < len(default_snippet):
            return default_snippet
        return body

    def fetch_page_details(self, url: str, default_snippet: str = "") -> dict[str, object]:
        if not url:
            return {"body": default_snippet, "title": "", "published_at": None}

        try:
            headers = {"User-Agent": getattr(settings, "reddit_user_agent", "nova-scraper/1.0")}
            with httpx.Client(
                timeout=getattr(settings, "blog_crawl_timeout_seconds", 10.0),
                headers=headers,
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()

            content_type = (response.headers.get("content-type") or "").lower()
            # Skip media/binary endpoints that can leak image bytes into title/body extraction.
            if content_type and "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return {"body": default_snippet, "title": "", "published_at": None}

            soup = BeautifulSoup(response.text, "html.parser")
            title = self._extract_title(soup, default_snippet)
            published_at = self._extract_published_at(soup)

            body = self._extract_body_with_trafilatura(response.text, default_snippet=default_snippet)
            if body == default_snippet:
                # Keep the existing BeautifulSoup fallback for edge cases trafilatura misses.
                for element in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "meta"]):
                    element.decompose()

                text = soup.get_text(separator="\n", strip=True)
                text = re.sub(r"\n{3,}", "\n\n", text)
                body = default_snippet if len(text) < len(default_snippet) else text

            return {"body": body, "title": title, "published_at": published_at}
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Deep fetch failed for {url}: {exc}")
            return {"body": default_snippet, "title": "", "published_at": None}

    def fetch_page_content(self, url: str, default_snippet: str = "") -> str:
        """
        Fetch URL and extract deep HTML body text.
        
        Removes script, style, nav, header, footer, aside, and noscript elements.
        Collapses excessive whitespace.
        Falls back to default_snippet if extraction fails or content too short.
        
        Args:
            url: URL to fetch
            default_snippet: Fallback text if fetch/extraction fails
            
        Returns:
            Extracted text or default_snippet
        """
        return str(self.fetch_page_details(url, default_snippet=default_snippet)["body"])
