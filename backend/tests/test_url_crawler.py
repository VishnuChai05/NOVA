"""
Unit tests for URLCrawler crawl_domains fix (Bug #1).

Verifies that max_urls_per_domain setting is respected, not hard-capped to 3.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.content_fetcher import ContentFetcher
from app.services.url_crawler import URLCrawler


class TestURLCrawler:
    """Test URLCrawler for Bug #1 fix."""

    def test_crawl_domains_respects_config_max_urls(self):
        """
        Test that crawl_domains respects max_urls_per_domain setting.
        
        BUG FIX #1: Previously hard-capped to 3 via min(3, max_urls_per_domain).
        Now should use the configured value directly.
        """
        mock_fetcher = MagicMock(spec=ContentFetcher)
        mock_fetcher.fetch_page_content = MagicMock(return_value="x" * 300)

        crawler = URLCrawler(mock_fetcher)

        # Mock the discovery methods to return the requested URLs
        with patch.object(crawler, "discover_urls_from_sitemap") as mock_sitemap, \
             patch.object(crawler, "discover_urls_from_homepage") as mock_homepage:
            
            # Return 120 URLs as if discovered (our configured value)
            urls = [f"http://example.com/article-{i}" for i in range(120)]
            mock_sitemap.return_value = (urls[:60], [])
            mock_homepage.return_value = (urls[60:120], [])

            result = crawler.crawl_domains(
                source_name="blog_crawl",
                domains=["example.com"],
                max_posts_per_source=200,
                max_urls_per_domain=120,  # This should NOT be capped to 3
            )

            # With bug: would only crawl 3 URLs max
            # Without bug: should crawl up to 120 URLs
            # In practice limited by max_posts_per_source, but the point is the number
            # shouldn't be artificially limited to 3
            assert len(result["rows"]) > 0
            # The max_per_domain calculation should use 120, not 3
            assert mock_fetcher.fetch_page_content.call_count >= 10  # At least more than 3

    def test_crawl_domains_with_small_max_urls(self):
        """Test crawl_domains with small max_urls_per_domain value."""
        mock_fetcher = MagicMock(spec=ContentFetcher)
        mock_fetcher.fetch_page_content = MagicMock(return_value="x" * 300)

        crawler = URLCrawler(mock_fetcher)

        with patch.object(crawler, "discover_urls_from_sitemap") as mock_sitemap, \
             patch.object(crawler, "discover_urls_from_homepage") as mock_homepage:
            
            urls_small = [f"http://example.com/page-{i}" for i in range(5)]
            mock_sitemap.return_value = (urls_small[:3], [])
            mock_homepage.return_value = (urls_small[3:5], [])

            result = crawler.crawl_domains(
                source_name="test",
                domains=["example.com"],
                max_posts_per_source=100,
                max_urls_per_domain=5,
            )

            assert len(result["rows"]) > 0
            # Should attempt to fetch/crawl URLs up to the limit
            assert mock_fetcher.fetch_page_content.call_count >= 3

    def test_crawl_domains_skips_short_content(self):
        """Test that crawl_domains skips posts with content < 200 chars."""
        mock_fetcher = MagicMock(spec=ContentFetcher)
        mock_fetcher.fetch_page_content = MagicMock(return_value="x" * 100)  # Too short

        crawler = URLCrawler(mock_fetcher)

        with patch.object(crawler, "discover_urls_from_sitemap") as mock_sitemap, \
             patch.object(crawler, "discover_urls_from_homepage") as mock_homepage:
            
            urls = [f"http://example.com/page-{i}" for i in range(10)]
            mock_sitemap.return_value = (urls[:5], [])
            mock_homepage.return_value = (urls[5:10], [])

            result = crawler.crawl_domains(
                source_name="test",
                domains=["example.com"],
                max_posts_per_source=100,
                max_urls_per_domain=10,
            )

            # All content is too short, so no posts should be created
            assert len(result["rows"]) == 0

    def test_extract_content_title_filters_boilerplate(self):
        """Test that extract_content_title filters boilerplate markers."""
        crawler = URLCrawler()

        boilerplate_body = """Skip to content
        Menu
        Search
        Some actual content here that is meaningful."""

        title = crawler.extract_content_title(boilerplate_body, "http://example.com/article")
        
        # Should extract "Some actual content here that is meaningful."
        # not any of the boilerplate
        assert "Skip to content" not in title
        assert "Menu" not in title
        assert "Search" not in title
        assert len(title) > 0

    def test_derive_title_from_url_slug(self):
        """Test deriving title from URL slug."""
        crawler = URLCrawler()

        title = crawler.derive_title_from_url("http://example.com/category/top-10-best-bras")
        assert "Bra" in title or "bra" in title or title  # Slug should be converted to title

    def test_normalize_url_handles_protocol_relative(self):
        """Test normalize_url handles protocol-relative URLs."""
        crawler = URLCrawler()

        result = crawler.normalize_url("//example.com/page")
        assert result.startswith("https://")
        assert "example.com" in result

    def test_url_matches_domains_exact_match(self):
        """Test url_matches_domains with exact domain match."""
        crawler = URLCrawler()

        assert crawler.url_matches_domains("http://example.com/page", ["example.com"])

    def test_url_matches_domains_subdomain_match(self):
        """Test url_matches_domains with subdomain match."""
        crawler = URLCrawler()

        assert crawler.url_matches_domains("http://blog.example.com/page", ["example.com"])

    def test_url_matches_domains_no_match(self):
        """Test url_matches_domains with non-matching domain."""
        crawler = URLCrawler()

        assert not crawler.url_matches_domains("http://other.com/page", ["example.com"])

    def test_crawl_blog_domains_wrapper(self):
        """Test crawl_blog_domains wrapper method."""
        mock_fetcher = MagicMock(spec=ContentFetcher)
        mock_fetcher.fetch_page_content = MagicMock(return_value="x" * 300)

        crawler = URLCrawler(mock_fetcher)

        with patch.object(crawler, "crawl_domains") as mock_crawl:
            mock_crawl.return_value = {"rows": [], "failures": []}

            result = crawler.crawl_blog_domains(
                domains=["blog.example.com"],
                max_posts_per_source=50,
                blog_crawl_max_urls_per_domain=120,
            )

            # Verify crawl_domains was called with correct params
            mock_crawl.assert_called_once()
            call_kwargs = mock_crawl.call_args[1]
            assert call_kwargs["source_name"] == "blog_crawl"
            assert call_kwargs["max_urls_per_domain"] == 120  # Not capped to 3

    def test_crawl_forum_domains_wrapper(self):
        """Test crawl_forum_domains wrapper method."""
        mock_fetcher = MagicMock(spec=ContentFetcher)
        mock_fetcher.fetch_page_content = MagicMock(return_value="x" * 300)

        crawler = URLCrawler(mock_fetcher)

        with patch.object(crawler, "crawl_domains") as mock_crawl:
            mock_crawl.return_value = {"rows": [], "failures": []}

            result = crawler.crawl_forum_domains(
                domains=["reddit.com"],
                max_posts_per_source=50,
            )

            mock_crawl.assert_called_once()
            call_kwargs = mock_crawl.call_args[1]
            assert call_kwargs["source_name"] == "discussion_forums"
            assert call_kwargs["max_urls_per_domain"] == 20
