"""
Social media content scraping (Reddit, Quora).

Responsibilities:
- Fetch content from Reddit (via PRAW API or Apify)
- Fetch content from Quora (via Apify or web search)
"""

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup

from app.core.settings import settings
from app.services.content_fetcher import ContentFetcher

if TYPE_CHECKING:
    from app.services.scraper import ScraperConfig

logger = logging.getLogger(__name__)

try:
    import praw
except ImportError:  # pragma: no cover
    praw = None

try:
    from apify_client import ApifyClient
except ImportError:  # pragma: no cover
    ApifyClient = None


class SocialMediaScraper:
    """Scrapes content from social media platforms."""

    def __init__(self, content_fetcher: ContentFetcher | None = None):
        """Initialize scraper with optional content fetcher."""
        self.fetcher = content_fetcher or ContentFetcher()

    @staticmethod
    def _reddit_queries() -> list[str]:
        """Hardcoded list of search queries for Reddit."""
        return [
            "women entrepreneur",
            "female founder",
            "body positivity",
            "body neutrality",
            "postpartum body",
            "maternity wear",
            "mom guilt",
            "mental load",
            "return to work",
            "women burnout",
            "corporate women",
            "salary negotiation",
            "self care",
            "comfortable workwear",
            "activewear",
            "sleepwear",
            "sustainable fashion",
            "strapless bra",
            "wireless bra",
            "nursing bra",
            "bra fitting",
            "period care",
            "shapewear",
            "sports bra chafing",
            "plus size innerwear",
            "period pain relief tips",
            "postpartum recovery",
        ]

    def _url_matches_domains(self, url: str, domains: list[str]) -> bool:
        """Check if URL belongs to specified domains."""
        from urllib.parse import urlparse
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

    @staticmethod
    def _published_at_value(*values) -> str | None:
        for value in values:
            parsed = ContentFetcher.parse_datetime_value(value)
            if parsed:
                return parsed.isoformat()
        return None

    def fetch_reddit_posts(self, cfg: "ScraperConfig") -> dict:
        """
        Fetch posts from Reddit via PRAW API.
        
        Args:
            cfg: Scraper configuration
            
        Returns:
            {"rows": [...], "failures": [...]}
        """
        if not settings.reddit_client_id or not settings.reddit_client_secret or praw is None:
            return {
                "rows": [],
                "failures": ["Reddit credentials or dependency missing"],
            }

        reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )

        queries = self._reddit_queries()
        results: list[dict] = []
        failures: list[str] = []
        per_subreddit_limit = max(3, cfg.max_posts_per_source // max(1, len(cfg.subreddits)))

        for sub_name in cfg.subreddits:
            subreddit = reddit.subreddit(sub_name)
            for query in queries:
                try:
                    submissions = self.fetcher.retry_with_backoff(
                        lambda q=query, s=subreddit, lim=per_subreddit_limit: list(
                            s.search(q, sort="new", limit=lim)
                        ),
                        f"reddit search {sub_name}:{query}",
                    )
                except (RuntimeError, ValueError) as exc:
                    failures.append(str(exc))
                    continue

                for submission in submissions:
                    if int(getattr(submission, "score", 0)) < cfg.min_score:
                        continue

                    top_comments: list[str] = []
                    try:
                        submission.comments.replace_more(limit=0)
                        top_comments = [c.body for c in submission.comments[:5] if getattr(c, "body", "")]
                    except (AttributeError, TypeError):
                        top_comments = []

                    body = (submission.selftext or "").strip()
                    if top_comments:
                        body = f"{body}\n\nTop comments:\n" + "\n".join(f"- {c}" for c in top_comments)

                    results.append(
                        {
                            "source": "reddit",
                            "title": submission.title,
                            "body": body,
                            "score": int(submission.score or 0),
                            "url": f"https://www.reddit.com{submission.permalink}",
                            "published_at": datetime.fromtimestamp(
                                float(getattr(submission, "created_utc", 0) or 0), tz=timezone.utc
                            ).isoformat(),
                        }
                    )

                    if len(results) >= cfg.max_posts_per_source:
                        return {"rows": results, "failures": failures}

                # Keep request pace predictable even if API wrappers also throttle.
                time.sleep(max(0.0, float(settings.reddit_query_delay_seconds)))

        return {"rows": results, "failures": failures}

    def fetch_reddit_via_apify(self, cfg: "ScraperConfig") -> dict:
        """
        Fetch posts from Reddit via Apify actor.
        
        Args:
            cfg: Scraper configuration
            
        Returns:
            {"rows": [...], "failures": [...]}
        """
        if not settings.apify_api_token or ApifyClient is None:
            return {
                "rows": [],
                "failures": ["Apify token or dependency missing"],
            }

        client = ApifyClient(settings.apify_api_token)
        actor_id = settings.apify_reddit_actor_id

        reddit_query_terms = self._reddit_queries()[:5]
        subreddit_terms = cfg.subreddits[:5]
        scoped_queries: list[str] = []
        for sub in subreddit_terms:
            for term in reddit_query_terms:
                scoped_queries.append(f"site:reddit.com {sub} {term}")

        query_str = " OR ".join(scoped_queries[:10])

        run_input = {
            "queries": query_str,
            "maxPagesPerQuery": 1,
        }

        try:
            run = self.fetcher.retry_with_backoff(
                lambda: client.actor(actor_id).call(run_input=run_input),
                "apify reddit actor run",
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException, RuntimeError) as exc:
            return {"rows": [], "failures": [str(exc)]}

        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return {"rows": [], "failures": ["No dataset id from Apify actor"]}

        results: list[dict] = []
        failures: list[str] = []
        try:
            items_iter = client.dataset(dataset_id).iterate_items()
        except (httpx.HTTPStatusError, httpx.TimeoutException, RuntimeError) as exc:
            return {"rows": [], "failures": [str(exc)]}

        for item in items_iter:
            organic_results = item.get("organicResults") or []
            for result in organic_results:
                url = str(result.get("url") or "")
                title = str(result.get("title") or "").strip()
                description = str(result.get("description") or "").strip()
                if "reddit.com" not in url or not title:
                    continue

                page_details = self.fetcher.fetch_page_details(url, default_snippet=description)
                body = str(page_details.get("body") or description)

                results.append(
                    {
                        "source": "reddit",
                        "title": title,
                        "body": body,
                        "score": 0,
                        "url": url,
                        "published_at": self._published_at_value(
                            result.get("publishedAt"),
                            result.get("published_at"),
                            result.get("date"),
                            result.get("timestamp"),
                            result.get("createdAt"),
                            page_details.get("published_at"),
                        ),
                    }
                )
                if len(results) >= cfg.max_posts_per_source:
                    return {"rows": results, "failures": failures}

        return {"rows": results, "failures": failures}

    def fetch_quora_via_apify(self, cfg: "ScraperConfig") -> dict:
        """
        Fetch posts from Quora via Apify actor.
        
        Args:
            cfg: Scraper configuration
            
        Returns:
            {"rows": [...], "failures": [...]}
        """
        if not settings.apify_api_token or ApifyClient is None:
            return {
                "rows": [],
                "failures": ["Apify token or dependency missing"],
            }

        client = ApifyClient(settings.apify_api_token)
        actor_id = settings.apify_quora_actor_id

        quora_queries = cfg.quora_queries[:6]
        query_str = " OR ".join([f"site:quora.com {q}" for q in quora_queries])

        run_input = {
            "queries": query_str,
            "maxPagesPerQuery": 1,
        }

        try:
            run = self.fetcher.retry_with_backoff(
                lambda: client.actor(actor_id).call(run_input=run_input),
                "apify quora actor run",
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException, RuntimeError) as exc:
            return {"rows": [], "failures": [str(exc)]}

        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return {"rows": [], "failures": ["No dataset id from Apify actor"]}

        results: list[dict] = []
        failures: list[str] = []
        try:
            items_iter = client.dataset(dataset_id).iterate_items()
        except (httpx.HTTPStatusError, httpx.TimeoutException, RuntimeError) as exc:
            return {"rows": [], "failures": [str(exc)]}

        for item in items_iter:
            organic_results = item.get("organicResults") or []
            for result in organic_results:
                url = str(result.get("url") or "")
                title = str(result.get("title") or "").strip()
                description = str(result.get("description") or "").strip()
                if "quora.com" not in url or not title:
                    continue

                page_details = self.fetcher.fetch_page_details(url, default_snippet=description)
                body = str(page_details.get("body") or description)
                published_at = self._published_at_value(
                    result.get("publishedAt"),
                    result.get("published_at"),
                    result.get("date"),
                    result.get("timestamp"),
                    result.get("createdAt"),
                    page_details.get("published_at"),
                )

                results.append(
                    {
                        "source": "quora",
                        "title": title,
                        "body": body,
                        "score": 0,
                        "url": url,
                        "published_at": published_at,
                    }
                )
                if len(results) >= cfg.max_posts_per_source:
                    return {"rows": results, "failures": failures}

        return {"rows": results, "failures": failures}

    def fetch_quora_via_search(self, cfg: "ScraperConfig") -> dict:
        """
        Fetch posts from Quora via DuckDuckGo web search.
        
        Args:
            cfg: Scraper configuration
            
        Returns:
            {"rows": [...], "failures": [...]}
        """
        results: list[dict] = []
        failures: list[str] = []
        headers = {"User-Agent": "Mozilla/5.0 (compatible; nova-content-engine/1.0)"}

        with httpx.Client(timeout=20, headers=headers, follow_redirects=True) as client:
            for query in cfg.quora_queries:
                try:
                    response = self.fetcher.retry_with_backoff(
                        lambda: client.get(
                            "https://duckduckgo.com/html/",
                            params={"q": f"site:quora.com {query}"},
                        ),
                        f"quora search query {query}",
                    )
                except (httpx.HTTPStatusError, httpx.TimeoutException, RuntimeError) as exc:
                    failures.append(str(exc))
                    continue

                if response.status_code != 200:
                    failures.append(f"query '{query}' status={response.status_code}")
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                links = soup.select("a.result__a")
                snippets = soup.select("a.result__snippet")

                for idx, link in enumerate(links):
                    title = link.get_text(" ", strip=True)
                    url = link.get("href") or ""
                    snippet = snippets[idx].get_text(" ", strip=True) if idx < len(snippets) else ""
                    if "quora.com" not in url or not title:
                        continue

                    page_details = self.fetcher.fetch_page_details(url, default_snippet=snippet)
                    body = str(page_details.get("body") or snippet)
                    published_at = self._published_at_value(page_details.get("published_at"))

                    results.append(
                        {
                            "source": "quora",
                            "title": title,
                            "body": body,
                            "score": 0,
                            "url": url,
                            "published_at": published_at,
                        }
                    )
                    if len(results) >= cfg.max_posts_per_source:
                        return {"rows": results, "failures": failures}

                time.sleep(max(0.0, float(settings.reddit_query_delay_seconds)))

        return {"rows": results, "failures": failures}

    def fetch_domain_search_via_apify(
        self,
        source_name: str,
        queries: list[str],
        domains: list[str],
        max_posts: int,
    ) -> dict:
        """
        Fetch search results from Apify for specified domains and queries.
        
        Args:
            source_name: Identifier for this source
            queries: List of search queries
            domains: List of domains to restrict search to
            max_posts: Maximum posts to return
            
        Returns:
            {"rows": [...], "failures": [...]}
        """
        if not settings.apify_api_token or ApifyClient is None:
            return {
                "rows": [],
                "failures": ["Apify token or dependency missing"],
            }

        client = ApifyClient(settings.apify_api_token)
        actor_id = settings.apify_actor_id
        scoped_queries = [f"site:{domain} {query}" for domain in domains[:6] for query in queries[:6]]
        query_str = " OR ".join(scoped_queries[:12])
        if not query_str:
            return {"rows": [], "failures": ["No configured queries/domains"]}

        run_input = {
            "queries": query_str,
            "maxPagesPerQuery": 1,
        }

        try:
            run = self.fetcher.retry_with_backoff(
                lambda: client.actor(actor_id).call(run_input=run_input),
                f"{source_name} apify run",
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException, RuntimeError) as exc:
            return {"rows": [], "failures": [str(exc)]}

        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return {"rows": [], "failures": ["No dataset id from Apify actor"]}

        results: list[dict] = []
        failures: list[str] = []
        try:
            items_iter = client.dataset(dataset_id).iterate_items()
        except (httpx.HTTPStatusError, httpx.TimeoutException, RuntimeError) as exc:
            return {"rows": [], "failures": [str(exc)]}

        for item in items_iter:
            organic_results = item.get("organicResults") or []
            for result in organic_results:
                url = str(result.get("url") or "").strip()
                title = str(result.get("title") or "").strip()
                description = str(result.get("description") or "").strip()
                if not title or not url or not self._url_matches_domains(url, domains):
                    continue

                page_details = self.fetcher.fetch_page_details(url, default_snippet=description)
                body = str(page_details.get("body") or description)
                published_at = self._published_at_value(
                    result.get("publishedAt"),
                    result.get("published_at"),
                    result.get("date"),
                    result.get("timestamp"),
                    result.get("createdAt"),
                    page_details.get("published_at"),
                )

                results.append(
                    {
                        "source": source_name,
                        "title": title,
                        "body": body,
                        "score": 0,
                        "url": url,
                        "published_at": published_at,
                    }
                )
                if len(results) >= max_posts:
                    return {"rows": results, "failures": failures}

        return {"rows": results, "failures": failures}
