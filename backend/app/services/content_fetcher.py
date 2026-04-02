"""
HTTP content fetching with retry logic and error handling.

Responsibilities:
- Fetch and parse web pages with timeout handling
- Retry failed requests with exponential backoff
- Extract meaningful text content from HTML
"""

import logging
import re
import time
from typing import Callable, TypeVar

import httpx
from bs4 import BeautifulSoup

from app.core.settings import settings

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
        if not url:
            return default_snippet

        try:
            headers = {"User-Agent": getattr(settings, "reddit_user_agent", "nova-scraper/1.0")}
            with httpx.Client(
                timeout=getattr(settings, "blog_crawl_timeout_seconds", 10.0),
                headers=headers,
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove noisy non-content elements
            for element in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "meta"]):
                element.decompose()

            text = soup.get_text(separator="\n", strip=True)
            # Collapse massive whitespace gaps
            text = re.sub(r"\n{3,}", "\n\n", text)

            # If the scraped body is somehow shorter than the google snippet, fall back to snippet
            if len(text) < len(default_snippet):
                return default_snippet
            return text
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Deep fetch failed for {url}: {exc}")
            return default_snippet
