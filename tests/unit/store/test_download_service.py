"""
Tests for DownloadService - centralized HTTP download with auth.

Covers:
- Unit tests: initialization, auth matching, download to file/bytes
- Edge cases: resume with hash, 416 responses, session cleanup, chunked data
- Thread safety: per-request session isolation
- Error handling: network errors, hash mismatches, HTML errors
- Bug regression tests for fixed issues
"""

import hashlib
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
import requests

from src.store.download_service import DownloadResult, DownloadError, DownloadService
from src.store.download_auth import CivitaiAuthProvider


# =============================================================================
# Unit Tests: Initialization
# =============================================================================

class TestDownloadServiceInit:
    """Tests for DownloadService initialization."""

    def test_default_init(self):
        svc = DownloadService()
        assert svc._auth_providers == []
        assert svc.chunk_size == 8192

    def test_custom_auth_providers(self):
        provider = CivitaiAuthProvider(api_key="key")
        svc = DownloadService(auth_providers=[provider])
        assert len(svc._auth_providers) == 1
        assert svc._auth_providers[0] is provider

    def test_custom_chunk_size(self):
        svc = DownloadService(chunk_size=4096)
        assert svc.chunk_size == 4096

    def test_empty_auth_providers_list(self):
        svc = DownloadService(auth_providers=[])
        assert svc._auth_providers == []

    def test_multiple_auth_providers(self):
        p1 = CivitaiAuthProvider(api_key="key1")
        p2 = CivitaiAuthProvider(api_key="key2")
        svc = DownloadService(auth_providers=[p1, p2])
        assert len(svc._auth_providers) == 2


# =============================================================================
# Unit Tests: Auth Matching
# =============================================================================

class TestPrepareAuth:
    """Tests for auth provider matching."""

    def test_no_providers(self):
        svc = DownloadService()
        url, headers, matched = svc._prepare_auth("https://example.com/file.bin")
        assert url == "https://example.com/file.bin"
        assert headers == {}
        assert matched is None

    def test_matching_provider(self):
        svc = DownloadService(auth_providers=[CivitaiAuthProvider(api_key="test-key")])
        url, headers, matched = svc._prepare_auth("https://civitai.com/api/download/models/123")
        # Auth via ?token= in URL, not Authorization header (survives cross-origin redirects)
        assert "token=test-key" in url
        assert headers == {}  # No Bearer header for Civitai downloads
        assert matched is not None

    def test_non_matching_provider(self):
        svc = DownloadService(auth_providers=[CivitaiAuthProvider(api_key="test-key")])
        url, headers, matched = svc._prepare_auth("https://huggingface.co/file.bin")
        assert headers == {}
        assert matched is None

    def test_old_token_replaced_in_url(self):
        """Old ?token= is replaced with the fresh API key."""
        svc = DownloadService(auth_providers=[CivitaiAuthProvider(api_key="new-key")])
        url, _, _ = svc._prepare_auth("https://civitai.com/api/download/models/123?token=old-key")
        assert "token=old-key" not in url
        assert "token=new-key" in url

    def test_first_matching_provider_wins(self):
        """When multiple providers match, the first one wins."""
        p1 = CivitaiAuthProvider(api_key="first")
        p2 = CivitaiAuthProvider(api_key="second")
        svc = DownloadService(auth_providers=[p1, p2])
        url, _, matched = svc._prepare_auth("https://civitai.com/api/download/models/1")
        assert "token=first" in url
        assert "token=second" not in url

    def test_no_api_key_still_matches(self):
        """Provider without API key still matches but URL unchanged."""
        svc = DownloadService(auth_providers=[CivitaiAuthProvider(api_key=None)])
        url, headers, matched = svc._prepare_auth("https://civitai.com/api/download/models/1")
        assert matched is not None
        assert headers == {}  # No key → no header
        assert "token=" not in url  # No key → no token in URL

    def test_url_with_multiple_query_params(self):
        """Old token should be replaced while preserving other params."""
        svc = DownloadService(auth_providers=[CivitaiAuthProvider(api_key="new-key")])
        url, _, _ = svc._prepare_auth(
            "https://civitai.com/api/download/models/123?type=Model&token=old&format=SafeTensor"
        )
        assert "token=old" not in url
        assert "token=new-key" in url
        assert "type=Model" in url
        assert "format=SafeTensor" in url


# =============================================================================
# Unit Tests: download_to_file
# =============================================================================

def _make_mock_response(content=b"data", status_code=200, content_type="application/octet-stream"):
    """Helper to create a mock HTTP response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.headers = {
        "content-type": content_type,
        "content-length": str(len(content)),
    }
    mock.iter_content.return_value = [content]
    mock.raise_for_status.return_value = None
    return mock


class TestDownloadToFile:
    """Tests for download_to_file method."""

    def test_basic_download(self, tmp_path):
        """Download a file and verify result."""
        svc = DownloadService()
        dest = tmp_path / "downloaded.bin"
        content = b"hello world"
        expected_sha = hashlib.sha256(content).hexdigest()

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = _make_mock_response(content)
            result = svc.download_to_file("https://example.com/file.bin", dest)

        assert result.sha256 == expected_sha
        assert result.size == len(content)
        assert dest.read_bytes() == content

    def test_hash_verification_pass(self, tmp_path):
        """Download succeeds when hash matches expected."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"
        content = b"test data"
        expected = hashlib.sha256(content).hexdigest()

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = _make_mock_response(content)
            result = svc.download_to_file("https://example.com/file", dest, expected_sha256=expected)

        assert result.sha256 == expected

    def test_hash_verification_fail(self, tmp_path):
        """Download raises DownloadError on hash mismatch."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = _make_mock_response(b"actual data")
            with pytest.raises(DownloadError, match="Hash mismatch"):
                svc.download_to_file("https://example.com/file", dest, expected_sha256="0000dead")

        # File should be deleted on hash mismatch
        assert not dest.exists()

    def test_hash_case_insensitive(self, tmp_path):
        """Hash comparison should be case-insensitive."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"
        content = b"test"
        expected = hashlib.sha256(content).hexdigest().upper()  # UPPERCASE

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = _make_mock_response(content)
            result = svc.download_to_file("https://example.com/file", dest, expected_sha256=expected)

        assert result.sha256 == expected.lower()

    def test_html_content_type_error(self, tmp_path):
        """Download raises DownloadError when server returns HTML."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            with pytest.raises(DownloadError, match="HTML"):
                svc.download_to_file("https://example.com/file", dest)

    def test_html_with_auth_provider_error_message(self, tmp_path):
        """HTML error should use auth provider's error message if matched."""
        provider = CivitaiAuthProvider(api_key="key")
        svc = DownloadService(auth_providers=[provider])
        dest = tmp_path / "file.bin"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            with pytest.raises(DownloadError, match="API key"):
                svc.download_to_file("https://civitai.com/api/download/models/1", dest)

    def test_network_error_preserves_file(self, tmp_path):
        """Network errors should NOT delete partial file (for resume)."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"
        dest.write_bytes(b"partial")

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.side_effect = requests.ConnectionError("timeout")
            with pytest.raises(DownloadError):
                svc.download_to_file("https://example.com/file", dest, resume=False)

        # File should still exist for resume
        assert dest.exists()

    def test_progress_callback(self, tmp_path):
        """Progress callback should be called during download."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"
        content = b"x" * 1024
        calls = []

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = _make_mock_response(content)
            svc.download_to_file(
                "https://example.com/file", dest,
                progress_callback=lambda d, t: calls.append((d, t)),
            )

        assert len(calls) > 0
        assert calls[-1][0] == len(content)

    def test_resume_sends_range_header(self, tmp_path):
        """Resume should send Range header for existing partial file."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"
        dest.write_bytes(b"partial")

        mock_response = MagicMock()
        mock_response.status_code = 206
        mock_response.headers = {"content-type": "application/octet-stream"}
        mock_response.iter_content.return_value = [b" data"]
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            svc.download_to_file("https://example.com/file", dest, resume=True)

            call_args = MockSession.return_value.get.call_args
            headers = call_args[1]["headers"]
            assert "Range" in headers
            assert headers["Range"] == "bytes=7-"

    def test_no_resume_overwrites(self, tmp_path):
        """Without resume, existing file should be overwritten."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"
        dest.write_bytes(b"old content")
        content = b"new content"

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = _make_mock_response(content)
            svc.download_to_file("https://example.com/file", dest, resume=False)

        assert dest.read_bytes() == content

    def test_auth_token_injected_in_url(self, tmp_path):
        """Auth token should be injected as ?token= for Civitai URLs."""
        provider = CivitaiAuthProvider(api_key="my-key")
        svc = DownloadService(auth_providers=[provider])
        dest = tmp_path / "file.bin"

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = _make_mock_response(b"data")
            svc.download_to_file("https://civitai.com/api/download/models/1", dest)

            call_args = MockSession.return_value.get.call_args
            actual_url = call_args[0][0]
            assert "token=my-key" in actual_url

    def test_creates_parent_dirs(self, tmp_path):
        """Download should create parent directories."""
        svc = DownloadService()
        dest = tmp_path / "subdir" / "nested" / "file.bin"

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = _make_mock_response(b"data")
            svc.download_to_file("https://example.com/file", dest)

        assert dest.exists()

    def test_custom_chunk_size_override(self, tmp_path):
        """chunk_size parameter should override default."""
        svc = DownloadService(chunk_size=1024)
        dest = tmp_path / "file.bin"
        content = b"data"

        with patch("src.store.download_service.requests.Session") as MockSession:
            mock_resp = _make_mock_response(content)
            MockSession.return_value.get.return_value = mock_resp
            svc.download_to_file("https://example.com/file", dest, chunk_size=2048)

            # Verify iter_content was called with overridden chunk_size
            mock_resp.iter_content.assert_called_with(chunk_size=2048)

    def test_custom_timeout(self, tmp_path):
        """Custom timeout should be passed to session.get."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = _make_mock_response(b"data")
            svc.download_to_file("https://example.com/file", dest, timeout=(5, 120))

            call_args = MockSession.return_value.get.call_args
            assert call_args[1]["timeout"] == (5, 120)

    def test_empty_content(self, tmp_path):
        """Download empty file should still return valid hash."""
        svc = DownloadService()
        dest = tmp_path / "empty.bin"
        empty_hash = hashlib.sha256(b"").hexdigest()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/octet-stream", "content-length": "0"}
        mock_response.iter_content.return_value = []  # No chunks
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            result = svc.download_to_file("https://example.com/empty", dest)

        assert result.sha256 == empty_hash
        assert result.size == 0

    def test_multi_chunk_download(self, tmp_path):
        """Download with multiple chunks should compute correct hash."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"
        chunk1 = b"hello "
        chunk2 = b"world"
        full = chunk1 + chunk2
        expected_sha = hashlib.sha256(full).hexdigest()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "application/octet-stream",
            "content-length": str(len(full)),
        }
        mock_response.iter_content.return_value = [chunk1, chunk2]
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            result = svc.download_to_file("https://example.com/file", dest)

        assert result.sha256 == expected_sha
        assert dest.read_bytes() == full

    def test_no_content_length_header(self, tmp_path):
        """Download should work even without content-length header."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"
        content = b"data"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/octet-stream"}  # No content-length
        mock_response.iter_content.return_value = [content]
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            result = svc.download_to_file("https://example.com/file", dest)

        assert result.size == len(content)

    def test_http_error_raises(self, tmp_path):
        """HTTP errors (4xx/5xx) should raise DownloadError."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            with pytest.raises(DownloadError, match="403"):
                svc.download_to_file("https://example.com/file", dest)


# =============================================================================
# Regression Tests: Resume + Hash Bug Fix
# =============================================================================

class TestResumeWithHash:
    """Regression tests for the resume + expected_sha256 bug.

    Bug: When resuming (initial_size > 0) with expected_sha256 set,
    the old code skipped hashing existing content. This caused hash
    mismatch because only new chunks were hashed.
    """

    def test_resume_with_expected_hash_passes(self, tmp_path):
        """Resume + expected hash should compute hash of ENTIRE file (old + new)."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"

        # Write partial content
        partial = b"partial_data_"
        dest.write_bytes(partial)

        # Server sends the remaining content
        remaining = b"remaining"
        full_content = partial + remaining
        expected_sha = hashlib.sha256(full_content).hexdigest()

        mock_response = MagicMock()
        mock_response.status_code = 206
        mock_response.headers = {
            "content-type": "application/octet-stream",
            "content-length": str(len(remaining)),
        }
        mock_response.iter_content.return_value = [remaining]
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            result = svc.download_to_file(
                "https://example.com/file", dest,
                expected_sha256=expected_sha,
                resume=True,
            )

        assert result.sha256 == expected_sha
        assert result.resumed is True
        assert dest.read_bytes() == full_content

    def test_resume_with_wrong_expected_hash_fails(self, tmp_path):
        """Resume + wrong expected hash should raise DownloadError."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"
        dest.write_bytes(b"partial_")

        remaining = b"rest"

        mock_response = MagicMock()
        mock_response.status_code = 206
        mock_response.headers = {"content-type": "application/octet-stream"}
        mock_response.iter_content.return_value = [remaining]
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            with pytest.raises(DownloadError, match="Hash mismatch"):
                svc.download_to_file(
                    "https://example.com/file", dest,
                    expected_sha256="0000000000000000000000000000000000000000dead",
                    resume=True,
                )

    def test_resume_without_hash_computes_full_hash(self, tmp_path):
        """Resume without expected hash should still compute correct full file hash."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"

        partial = b"abc"
        dest.write_bytes(partial)
        remaining = b"def"
        full = partial + remaining
        expected_sha = hashlib.sha256(full).hexdigest()

        mock_response = MagicMock()
        mock_response.status_code = 206
        mock_response.headers = {"content-type": "application/octet-stream"}
        mock_response.iter_content.return_value = [remaining]
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            result = svc.download_to_file("https://example.com/file", dest, resume=True)

        assert result.sha256 == expected_sha


# =============================================================================
# Regression Tests: 416 Response Bug Fix
# =============================================================================

class TestResponse416:
    """Regression tests for 416 Range Not Satisfiable handling.

    Bug: When the file was already fully downloaded (416) and no
    expected_sha256 was set, the old code raised DownloadError instead
    of returning the result.
    """

    def test_416_without_expected_hash_succeeds(self, tmp_path):
        """416 with existing file and no expected hash should succeed."""
        svc = DownloadService()
        dest = tmp_path / "complete.bin"
        content = b"full file content"
        dest.write_bytes(content)
        expected_sha = hashlib.sha256(content).hexdigest()

        mock_response = MagicMock()
        mock_response.status_code = 416

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            result = svc.download_to_file("https://example.com/file", dest, resume=True)

        assert result.sha256 == expected_sha
        assert result.resumed is True
        assert result.size == len(content)

    def test_416_with_matching_hash_succeeds(self, tmp_path):
        """416 with matching expected hash should succeed."""
        svc = DownloadService()
        dest = tmp_path / "complete.bin"
        content = b"file data"
        dest.write_bytes(content)
        expected_sha = hashlib.sha256(content).hexdigest()

        mock_response = MagicMock()
        mock_response.status_code = 416

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            result = svc.download_to_file(
                "https://example.com/file", dest,
                expected_sha256=expected_sha,
                resume=True,
            )

        assert result.sha256 == expected_sha

    def test_416_with_wrong_hash_fails(self, tmp_path):
        """416 with wrong expected hash should raise DownloadError."""
        svc = DownloadService()
        dest = tmp_path / "complete.bin"
        dest.write_bytes(b"some data")

        mock_response = MagicMock()
        mock_response.status_code = 416

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            with pytest.raises(DownloadError, match="Hash mismatch"):
                svc.download_to_file(
                    "https://example.com/file", dest,
                    expected_sha256="0" * 64,
                    resume=True,
                )

        # File should be deleted on hash mismatch
        assert not dest.exists()

    def test_416_without_file_raises(self, tmp_path):
        """416 without existing file should raise DownloadError."""
        svc = DownloadService()
        dest = tmp_path / "nonexistent.bin"

        mock_response = MagicMock()
        mock_response.status_code = 416

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            with pytest.raises(DownloadError, match="Range not satisfiable"):
                svc.download_to_file("https://example.com/file", dest, resume=True)


# =============================================================================
# Unit Tests: Session Lifecycle
# =============================================================================

class TestSessionLifecycle:
    """Tests that sessions are properly created and closed."""

    def test_session_closed_on_success(self, tmp_path):
        """Session should be closed after successful download."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"

        with patch("src.store.download_service.requests.Session") as MockSession:
            session = MockSession.return_value
            session.get.return_value = _make_mock_response(b"data")
            svc.download_to_file("https://example.com/file", dest)
            session.close.assert_called_once()

    def test_session_closed_on_error(self, tmp_path):
        """Session should be closed even when download fails."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"

        with patch("src.store.download_service.requests.Session") as MockSession:
            session = MockSession.return_value
            session.get.side_effect = requests.ConnectionError("fail")
            with pytest.raises(DownloadError):
                svc.download_to_file("https://example.com/file", dest)
            session.close.assert_called_once()

    def test_session_closed_on_hash_mismatch(self, tmp_path):
        """Session should be closed on hash mismatch."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"

        with patch("src.store.download_service.requests.Session") as MockSession:
            session = MockSession.return_value
            session.get.return_value = _make_mock_response(b"data")
            with pytest.raises(DownloadError):
                svc.download_to_file("https://example.com/file", dest, expected_sha256="bad")
            session.close.assert_called_once()

    def test_bytes_session_closed_on_success(self):
        """download_to_bytes session should be closed on success."""
        svc = DownloadService()

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.content = b"data"
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            session = MockSession.return_value
            session.get.return_value = mock_response
            svc.download_to_bytes("https://example.com/img.jpg")
            session.close.assert_called_once()

    def test_bytes_session_closed_on_error(self):
        """download_to_bytes session should be closed on error."""
        svc = DownloadService()

        with patch("src.store.download_service.requests.Session") as MockSession:
            session = MockSession.return_value
            session.get.side_effect = requests.ConnectionError("fail")
            with pytest.raises(DownloadError):
                svc.download_to_bytes("https://example.com/file")
            session.close.assert_called_once()

    def test_user_agent_set(self, tmp_path):
        """User-Agent header should be set on session."""
        svc = DownloadService()
        dest = tmp_path / "file.bin"

        with patch("src.store.download_service.requests.Session") as MockSession:
            session = MockSession.return_value
            session.get.return_value = _make_mock_response(b"data")
            svc.download_to_file("https://example.com/file", dest)
            session.headers.update.assert_called_with({"User-Agent": "Mozilla/5.0 (compatible; Synapse/2.0)"})


# =============================================================================
# Unit Tests: Thread Safety
# =============================================================================

class TestThreadSafety:
    """Tests for per-request session isolation (thread safety)."""

    def test_concurrent_downloads_use_separate_sessions(self, tmp_path):
        """Each download call should create its own session."""
        svc = DownloadService()
        sessions_created = []

        def mock_session_factory():
            session = MagicMock()
            session.get.return_value = _make_mock_response(b"data")
            sessions_created.append(session)
            return session

        with patch("src.store.download_service.requests.Session", side_effect=mock_session_factory):
            # Two sequential downloads
            svc.download_to_file("https://example.com/a", tmp_path / "a.bin")
            svc.download_to_file("https://example.com/b", tmp_path / "b.bin")

        # Should have created 2 separate sessions
        assert len(sessions_created) == 2
        assert sessions_created[0] is not sessions_created[1]

    def test_parallel_downloads_thread_safe(self, tmp_path):
        """Parallel downloads in threads should not interfere."""
        svc = DownloadService()
        results = {}
        errors = []

        def download_file(name, content):
            try:
                dest = tmp_path / name
                mock_resp = _make_mock_response(content)

                with patch("src.store.download_service.requests.Session") as MockSession:
                    MockSession.return_value.get.return_value = mock_resp
                    result = svc.download_to_file(f"https://example.com/{name}", dest)
                    results[name] = result.sha256
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=download_file, args=("file1.bin", b"content1")),
            threading.Thread(target=download_file, args=("file2.bin", b"content2")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 2
        assert results["file1.bin"] == hashlib.sha256(b"content1").hexdigest()
        assert results["file2.bin"] == hashlib.sha256(b"content2").hexdigest()


# =============================================================================
# Unit Tests: download_to_bytes
# =============================================================================

class TestDownloadToBytes:
    """Tests for download_to_bytes method."""

    def test_basic_download(self):
        svc = DownloadService()

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/octet-stream"}
        mock_response.content = b"image data"
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            result = svc.download_to_bytes("https://example.com/image.jpg")

        assert result == b"image data"

    def test_html_error_detection(self):
        svc = DownloadService()

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            with pytest.raises(DownloadError, match="HTML"):
                svc.download_to_bytes("https://example.com/image.jpg")

    def test_auth_injected(self):
        provider = CivitaiAuthProvider(api_key="key")
        svc = DownloadService(auth_providers=[provider])

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.content = b"data"
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            svc.download_to_bytes("https://civitai.com/images/123.jpg")

            call_args = MockSession.return_value.get.call_args
            actual_url = call_args[0][0]
            assert "token=key" in actual_url

    def test_network_error(self):
        svc = DownloadService()

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.side_effect = requests.ConnectionError("fail")
            with pytest.raises(DownloadError, match="fail"):
                svc.download_to_bytes("https://example.com/file")

    def test_custom_timeout(self):
        """Custom timeout should be passed through."""
        svc = DownloadService()

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "image/png"}
        mock_response.content = b"data"
        mock_response.raise_for_status.return_value = None

        with patch("src.store.download_service.requests.Session") as MockSession:
            MockSession.return_value.get.return_value = mock_response
            svc.download_to_bytes("https://example.com/img.png", timeout=(5, 10))

            call_args = MockSession.return_value.get.call_args
            assert call_args[1]["timeout"] == (5, 10)

    def test_http_error_raises(self):
        """HTTP errors should raise DownloadError."""
        svc = DownloadService()

        with patch("src.store.download_service.requests.Session") as MockSession:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
            MockSession.return_value.get.return_value = mock_resp
            with pytest.raises(DownloadError, match="404"):
                svc.download_to_bytes("https://example.com/missing.jpg")


# =============================================================================
# Unit Tests: _compute_sha256
# =============================================================================

class TestComputeSha256:
    """Tests for the static hash computation method."""

    def test_compute_sha256(self, tmp_path):
        content = b"test content for hashing"
        path = tmp_path / "file.bin"
        path.write_bytes(content)

        result = DownloadService._compute_sha256(path)
        assert result == hashlib.sha256(content).hexdigest()

    def test_compute_sha256_empty_file(self, tmp_path):
        path = tmp_path / "empty.bin"
        path.write_bytes(b"")

        result = DownloadService._compute_sha256(path)
        assert result == hashlib.sha256(b"").hexdigest()

    def test_compute_sha256_custom_chunk(self, tmp_path):
        content = b"x" * 100
        path = tmp_path / "file.bin"
        path.write_bytes(content)

        result = DownloadService._compute_sha256(path, chunk_size=10)
        assert result == hashlib.sha256(content).hexdigest()


# =============================================================================
# Unit Tests: Model Cache (CivitaiUpdateProvider)
# =============================================================================

class TestModelCache:
    """Tests for CivitaiUpdateProvider model cache."""

    def test_cache_hit(self):
        from src.store.civitai_update_provider import CivitaiUpdateProvider

        mock_client = MagicMock()
        mock_client.get_model.return_value = {"id": 1, "name": "Test"}

        provider = CivitaiUpdateProvider(mock_client)

        # First call should hit API
        result1 = provider.get_model_cached(1)
        assert mock_client.get_model.call_count == 1

        # Second call should hit cache
        result2 = provider.get_model_cached(1)
        assert mock_client.get_model.call_count == 1  # NOT incremented
        assert result1 is result2

    def test_cache_miss(self):
        from src.store.civitai_update_provider import CivitaiUpdateProvider

        mock_client = MagicMock()
        mock_client.get_model.side_effect = lambda mid: {"id": mid}

        provider = CivitaiUpdateProvider(mock_client)
        provider.get_model_cached(1)
        provider.get_model_cached(2)
        assert mock_client.get_model.call_count == 2

    def test_clear_cache(self):
        from src.store.civitai_update_provider import CivitaiUpdateProvider

        mock_client = MagicMock()
        mock_client.get_model.return_value = {"id": 1}

        provider = CivitaiUpdateProvider(mock_client)
        provider.get_model_cached(1)
        assert mock_client.get_model.call_count == 1

        provider.clear_cache()
        provider.get_model_cached(1)
        assert mock_client.get_model.call_count == 2  # Re-fetched after clear

    def test_cache_different_models(self):
        """Cache should store different model IDs independently."""
        from src.store.civitai_update_provider import CivitaiUpdateProvider

        mock_client = MagicMock()
        mock_client.get_model.side_effect = lambda mid: {"id": mid, "name": f"Model{mid}"}

        provider = CivitaiUpdateProvider(mock_client)
        r1 = provider.get_model_cached(100)
        r2 = provider.get_model_cached(200)
        r1_again = provider.get_model_cached(100)

        assert r1["id"] == 100
        assert r2["id"] == 200
        assert r1_again is r1  # Same object from cache
        assert mock_client.get_model.call_count == 2  # Only 2 API calls

    def test_cache_survives_api_error(self):
        """After successful cache, API error on different ID shouldn't clear cache."""
        from src.store.civitai_update_provider import CivitaiUpdateProvider

        mock_client = MagicMock()
        mock_client.get_model.side_effect = [
            {"id": 1, "name": "OK"},
            Exception("API error"),
        ]

        provider = CivitaiUpdateProvider(mock_client)
        provider.get_model_cached(1)  # OK

        with pytest.raises(Exception, match="API error"):
            provider.get_model_cached(2)  # Fails

        # But model 1 should still be cached
        result = provider.get_model_cached(1)
        assert result["id"] == 1
        assert mock_client.get_model.call_count == 2  # Not 3


# =============================================================================
# Integration: BlobStore + DownloadService
# =============================================================================

class TestBlobStoreDownloadServiceIntegration:
    """Tests that BlobStore delegates to DownloadService."""

    def test_blob_store_accepts_download_service(self):
        from src.store.blob_store import BlobStore

        ds = DownloadService()
        store = BlobStore(layout=MagicMock(), download_service=ds)
        assert store._download_service is ds

    def test_blob_store_creates_default_download_service(self):
        from src.store.blob_store import BlobStore

        store = BlobStore(layout=MagicMock(), api_key="key")
        assert store._download_service is not None
        assert isinstance(store._download_service, DownloadService)

    def test_blob_store_uses_correct_timeout(self):
        """BlobStore should pass its timeout to DownloadService."""
        from src.store.blob_store import BlobStore

        ds = DownloadService()
        store = BlobStore(layout=MagicMock(), download_service=ds, timeout=600)
        assert store.timeout == 600
        # The timeout is used in _download_http when calling download_to_file

    def test_blob_store_passes_auth_to_default_service(self):
        """Default DownloadService should have auth providers from BlobStore."""
        from src.store.blob_store import BlobStore

        store = BlobStore(layout=MagicMock(), api_key="test-key")
        assert len(store._download_service._auth_providers) > 0
