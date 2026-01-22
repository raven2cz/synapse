"""
Tests for CivArchive pagination support (Phase 5).

These tests verify that the CivArchive search endpoint correctly
handles pagination - ONE page per request, like a normal user.
"""

import pytest
from unittest.mock import patch, MagicMock

# Import the functions we're testing
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apps.api.src.routers.browse import (
    CivArchiveSearchResponse,
    _search_civarchive,
)


def create_mock_response(html_content: str = "<html></html>", status_code: int = 200):
    """Create a mock requests response."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.text = html_content
    mock_response.raise_for_status = MagicMock()
    return mock_response


def create_mock_session(mock_response):
    """Create a mock requests.Session that returns the given response."""
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_session.headers = MagicMock()
    mock_session.headers.update = MagicMock()
    return mock_session


# =============================================================================
# Single Page Fetch Tests
# =============================================================================

class TestCivArchiveSinglePageFetch:
    """Tests for single page fetching in _search_civarchive."""

    @patch("requests.Session")
    def test_page_1_fetches_only_page_1(self, mock_session_class):
        """Page 1 should fetch ONLY CivArchive page 1 - no parallel requests."""
        mock_session = create_mock_session(create_mock_response())
        mock_session_class.return_value = mock_session

        _search_civarchive("test query", limit=10, page=1)

        # Should make exactly ONE request
        assert mock_session.get.call_count == 1, "Should make exactly 1 request"

        call_url = mock_session.get.call_args[0][0]
        assert "page=1" in call_url, "Should fetch page 1"

    @patch("requests.Session")
    def test_page_2_fetches_only_page_2(self, mock_session_class):
        """Page 2 should fetch ONLY CivArchive page 2."""
        mock_session = create_mock_session(create_mock_response())
        mock_session_class.return_value = mock_session

        _search_civarchive("test query", limit=10, page=2)

        assert mock_session.get.call_count == 1, "Should make exactly 1 request"

        call_url = mock_session.get.call_args[0][0]
        assert "page=2" in call_url, "Should fetch page 2"

    @patch("requests.Session")
    def test_page_5_fetches_only_page_5(self, mock_session_class):
        """Page 5 should fetch ONLY CivArchive page 5."""
        mock_session = create_mock_session(create_mock_response())
        mock_session_class.return_value = mock_session

        _search_civarchive("test query", limit=10, page=5)

        assert mock_session.get.call_count == 1, "Should make exactly 1 request"

        call_url = mock_session.get.call_args[0][0]
        assert "page=5" in call_url, "Should fetch page 5"


# =============================================================================
# Has More Detection Tests
# =============================================================================

class TestCivArchiveHasMore:
    """Tests for has_more detection in _search_civarchive."""

    @patch("requests.Session")
    def test_has_more_true_when_results_found(self, mock_session_class):
        """has_more should be True when page returns results."""
        html_with_results = """
        <html>
            <a href="/models/12345">Model 1</a>
            <a href="/models/67890">Model 2</a>
        </html>
        """
        mock_session = create_mock_session(create_mock_response(html_with_results))
        mock_session_class.return_value = mock_session

        urls, has_more = _search_civarchive("test", limit=10, page=1)

        assert has_more is True, "Should have more when results found"
        assert len(urls) > 0, "Should return URLs"

    @patch("requests.Session")
    def test_has_more_false_when_no_results(self, mock_session_class):
        """has_more should be False when no results are found."""
        mock_session = create_mock_session(create_mock_response("<html></html>"))
        mock_session_class.return_value = mock_session

        urls, has_more = _search_civarchive("test", limit=10, page=1)

        assert has_more is False, "Should not have more when no results"
        assert len(urls) == 0, "Should return empty list"

    @patch("requests.Session")
    def test_has_more_false_on_error(self, mock_session_class):
        """has_more should be False when request fails."""
        mock_session = MagicMock()
        mock_session.headers = MagicMock()
        mock_session.headers.update = MagicMock()
        mock_session.get.side_effect = Exception("Network error")
        mock_session_class.return_value = mock_session

        urls, has_more = _search_civarchive("test", limit=10, page=1)

        assert has_more is False, "Should not have more on error"
        assert len(urls) == 0, "Should return empty list on error"


# =============================================================================
# Response Model Tests
# =============================================================================

class TestCivArchiveSearchResponse:
    """Tests for CivArchiveSearchResponse model."""

    def test_response_includes_pagination_fields(self):
        """Response model should include has_more and current_page."""
        response = CivArchiveSearchResponse(
            results=[],
            total_found=0,
            query="test",
            has_more=True,
            current_page=2,
        )

        assert response.has_more is True
        assert response.current_page == 2

    def test_response_defaults(self):
        """Response model should have correct defaults."""
        response = CivArchiveSearchResponse(
            results=[],
            total_found=0,
            query="test",
        )

        assert response.has_more is False
        assert response.current_page == 1

    def test_response_serialization(self):
        """Response should serialize correctly for API."""
        response = CivArchiveSearchResponse(
            results=[],
            total_found=5,
            query="lora",
            has_more=True,
            current_page=3,
        )

        data = response.model_dump()

        assert data["has_more"] is True
        assert data["current_page"] == 3
        assert data["query"] == "lora"
        assert data["total_found"] == 5


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
