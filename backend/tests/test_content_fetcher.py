"""
Unit tests for ContentFetcher retry logic fix (Bug #2).

Verifies that _retry_with_backoff catches network errors in addition to RuntimeError.
"""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.content_fetcher import ContentFetcher


class TestContentFetcherRetry:
    """Test ContentFetcher retry_with_backoff method."""

    def test_retry_with_backoff_catches_runtime_error(self):
        """Test that RuntimeError is caught and retried."""
        fetcher = ContentFetcher(retry_attempts=2, backoff_base_seconds=0.01)
        call_count = 0

        def failing_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Test error")
            return "success"

        result = fetcher.retry_with_backoff(failing_fn, "test")
        assert result == "success"
        assert call_count == 2

    def test_retry_with_backoff_catches_http_status_error(self):
        """
        Test that httpx.HTTPStatusError is caught and retried.
        
        BUG FIX #2: Previously not caught - network errors would bypass retry.
        """
        fetcher = ContentFetcher(retry_attempts=2, backoff_base_seconds=0.01)
        call_count = 0

        def failing_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                response = MagicMock()
                response.status_code = 500
                raise httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)
            return "success"

        result = fetcher.retry_with_backoff(failing_fn, "test")
        assert result == "success"
        assert call_count == 2

    def test_retry_with_backoff_catches_timeout_exception(self):
        """
        Test that httpx.TimeoutException is caught and retried.
        
        BUG FIX #2: Previously not caught - timeouts would bypass retry.
        """
        fetcher = ContentFetcher(retry_attempts=2, backoff_base_seconds=0.01)
        call_count = 0

        def failing_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Timeout")
            return "success"

        result = fetcher.retry_with_backoff(failing_fn, "test")
        assert result == "success"
        assert call_count == 2

    def test_retry_with_backoff_exhausts_retries(self):
        """Test that RuntimeError is raised after max retries exhausted."""
        fetcher = ContentFetcher(retry_attempts=2, backoff_base_seconds=0.01)

        def always_failing_fn():
            raise httpx.TimeoutException("Always fails")

        with pytest.raises(RuntimeError, match="failed after 2 attempts"):
            fetcher.retry_with_backoff(always_failing_fn, "failing test")

    def test_retry_with_backoff_exponential_backoff(self):
        """Test that backoff time increases exponentially."""
        fetcher = ContentFetcher(retry_attempts=3, backoff_base_seconds=0.01)
        call_times = []

        def failing_fn():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise RuntimeError("Retry")
            return "success"

        start = time.time()
        fetcher.retry_with_backoff(failing_fn, "backoff test")

        # Verify delays increase: ~0.01s, then ~0.02s
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            assert delay1 > 0.005  # At least some delay
            assert delay2 >= delay1  # Second delay >= first delay

    def test_fetch_with_retry_success(self):
        """Test fetch_with_retry succeeds on first try."""
        fetcher = ContentFetcher()

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.get = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = fetcher.fetch_with_retry("http://example.com")
            assert response == mock_response

    def test_fetch_page_content_fallback_on_short_body(self):
        """Test fetch_page_content falls back to default_snippet if content too short."""
        fetcher = ContentFetcher()
        short_content = "Brief"
        default_snippet = "This is a longer default snippet that should be used instead"

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.text = f"<html>{short_content}</html>"
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.get = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = fetcher.fetch_page_content("http://example.com", default_snippet=default_snippet)
            assert result == default_snippet

    def test_fetch_page_content_returns_content_when_longer(self):
        """Test fetch_page_content returns extracted content when longer than snippet."""
        fetcher = ContentFetcher()
        long_content = "This is a much longer content " * 10

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.text = f"<html><p>{long_content}</p></html>"
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            mock_client.get = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = fetcher.fetch_page_content("http://example.com", default_snippet="short")
            assert long_content.split()[0] in result  # Content contains expected words
