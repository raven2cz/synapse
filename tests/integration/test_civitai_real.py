"""
Real Civitai API integration tests.

Two categories:
1. Tests that call real Civitai CDN (public images, no API key needed)
   — marked @pytest.mark.civitai, skipped if network unavailable
2. Tests that require CIVITAI_API_KEY for authenticated model downloads
   — marked @pytest.mark.civitai, skipped if key not set

Run:
    # Public CDN tests (no key needed):
    uv run pytest tests/integration/test_civitai_real.py -v -m civitai -k "not requires_api_key"

    # All tests (key required):
    CIVITAI_API_KEY=your-key uv run pytest tests/integration/test_civitai_real.py -v -m civitai

Why these tests exist:
    The ?token= auth method was chosen because Python's requests library strips
    the Authorization header on cross-origin redirects (RFC 7235). Civitai's
    download endpoint redirects to CDN/S3 (different host), so Bearer auth fails.
    See: plans/civitai-download-auth.md
"""

import os
import pytest
import tempfile
from pathlib import Path

from src.store.download_auth import CivitaiAuthProvider
from src.store.download_service import DownloadService, DownloadError

CIVITAI_API_KEY = os.environ.get("CIVITAI_API_KEY")

# DreamShaper model preview — public, SFW, stable
# Civitai CDN may return PNG even for .jpeg URLs
CIVITAI_PREVIEW_URL = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/c1033497-007c-4a73-b812-915c8e32e8fe/original=true/1777043.jpeg"

# iLustMix — NSFW model that REQUIRES auth (returns HTML login page without token)
# This is the critical test case: without ?token= you get redirected to login
CIVITAI_AUTH_REQUIRED_URL = "https://civitai.com/api/download/models/2706040"

# DreamShaper v8 — public model (works without auth too)
CIVITAI_PUBLIC_DOWNLOAD_URL = "https://civitai.com/api/download/models/128713"

JPEG_MAGIC = b"\xff\xd8"
PNG_MAGIC = b"\x89PNG"

pytestmark = [pytest.mark.civitai, pytest.mark.external]


def _is_image(data: bytes) -> bool:
    return data[:2] == JPEG_MAGIC or data[:4] == PNG_MAGIC


def _is_not_html(data: bytes) -> bool:
    prefix = data[:500].lower()
    return b"<!doctype" not in prefix and b"<html" not in prefix


def _check_network():
    """Check if Civitai CDN is reachable."""
    import requests
    try:
        r = requests.head("https://image.civitai.com", timeout=5)
        return True
    except Exception:
        return False


def _skip_on_cdn_error(func):
    """Decorator: skip test gracefully when Civitai CDN returns server errors (5xx)."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DownloadError as e:
            msg = str(e)
            if any(f"{code} Server Error" in msg for code in (500, 502, 503, 504)):
                pytest.skip(f"Civitai CDN server error: {msg[:120]}")
            raise

    return wrapper


# ============================================================================
# Public CDN tests (no API key needed)
# ============================================================================

@pytest.mark.skipif(not _check_network(), reason="Civitai CDN not reachable")
class TestCivitaiPublicDownload:
    """Test downloading public preview images — no API key needed."""

    @_skip_on_cdn_error
    def test_download_preview_to_bytes(self):
        """DownloadService.download_to_bytes returns image data from Civitai CDN."""
        ds = DownloadService()
        data = ds.download_to_bytes(CIVITAI_PREVIEW_URL, timeout=(10, 15))

        assert len(data) > 5000, f"Too small: {len(data)} bytes"
        assert _is_image(data), f"Not image, first bytes: {data[:10].hex()}"
        assert _is_not_html(data), "Got HTML instead of image"

    @_skip_on_cdn_error
    def test_download_preview_to_file(self, tmp_path):
        """DownloadService.download_to_file saves image with correct SHA256."""
        ds = DownloadService()
        dest = tmp_path / "preview.img"
        result = ds.download_to_file(CIVITAI_PREVIEW_URL, dest, timeout=(10, 15), resume=False)

        assert dest.exists()
        assert result.size > 5000
        assert len(result.sha256) == 64
        assert _is_image(dest.read_bytes())

    @_skip_on_cdn_error
    def test_token_in_url_does_not_break_cdn(self, tmp_path):
        """Adding ?token= to CDN URL should not break the download.

        This verifies the CivitaiAuthProvider's URL injection doesn't cause
        the CDN to reject the request or return HTML errors.
        """
        auth = CivitaiAuthProvider(api_key="fake-test-key-12345")
        ds = DownloadService(auth_providers=[auth])
        dest = tmp_path / "preview_with_token.img"

        result = ds.download_to_file(CIVITAI_PREVIEW_URL, dest, timeout=(10, 15), resume=False)

        assert dest.exists()
        assert result.size > 5000
        content = dest.read_bytes()
        assert _is_image(content), "Token in URL broke CDN download"
        assert _is_not_html(content), "Got HTML — token caused auth redirect"

    @_skip_on_cdn_error
    def test_resume_download(self, tmp_path):
        """Resume should detect complete file and return cached result."""
        ds = DownloadService()
        dest = tmp_path / "resume_test.img"

        r1 = ds.download_to_file(CIVITAI_PREVIEW_URL, dest, timeout=(10, 15), resume=False)
        r2 = ds.download_to_file(CIVITAI_PREVIEW_URL, dest, timeout=(10, 15), resume=True)

        assert r2.sha256 == r1.sha256
        assert r2.resumed is True


# ============================================================================
# Authenticated download tests (API key required)
# ============================================================================

requires_api_key = pytest.mark.skipif(
    not CIVITAI_API_KEY, reason="CIVITAI_API_KEY not set"
)


@requires_api_key
@pytest.mark.skipif(not _check_network(), reason="Civitai CDN not reachable")
class TestCivitaiAuthenticatedDownload:
    """Test authenticated model downloads via ?token= parameter.

    The download endpoint /api/download/models/{id} redirects to CDN (cross-origin).
    Authorization: Bearer gets stripped on redirect. ?token= survives.
    """

    def test_model_download_starts_with_token(self):
        """Model download with ?token= should return binary data, not HTML."""
        import requests

        auth = CivitaiAuthProvider(api_key=CIVITAI_API_KEY)
        authenticated_url = auth.authenticate_url(CIVITAI_DOWNLOAD_URL)

        assert f"token={CIVITAI_API_KEY}" in authenticated_url

        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; Synapse/2.0)"})
        try:
            response = session.get(
                authenticated_url,
                stream=True,
                timeout=(15, 30),
                allow_redirects=True,
            )

            assert response.status_code == 200, \
                f"Expected 200, got {response.status_code}. Final URL: {response.url}"

            content_type = response.headers.get("content-type", "")
            assert "text/html" not in content_type.lower(), \
                f"Got HTML — auth failed. content-type: {content_type}"

            # Read just first chunk to verify binary data
            chunk = next(response.iter_content(chunk_size=1024))
            assert len(chunk) > 0
            assert _is_not_html(chunk), "First chunk is HTML — auth redirect"

        finally:
            response.close()
            session.close()

    def test_bearer_header_behavior_on_redirect(self):
        """Document that Bearer auth gets stripped on cross-origin redirect.

        This test does NOT assert failure — some models are fully public
        and download without any auth. It documents the redirect behavior.
        """
        import requests

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; Synapse/2.0)",
            "Authorization": f"Bearer {CIVITAI_API_KEY}",
        })

        try:
            response = session.get(
                CIVITAI_DOWNLOAD_URL,
                stream=True,
                timeout=(15, 30),
                allow_redirects=True,
            )

            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type.lower():
                # Expected: Bearer stripped on redirect → login page
                pass
            else:
                # Model is public, no auth needed — test is inconclusive
                pass
        finally:
            response.close()
            session.close()

    def test_authenticated_preview_download(self):
        """Preview download with real API key should work."""
        auth = CivitaiAuthProvider(api_key=CIVITAI_API_KEY)
        ds = DownloadService(auth_providers=[auth])

        data = ds.download_to_bytes(CIVITAI_PREVIEW_URL, timeout=(10, 15))
        assert len(data) > 5000
        assert _is_image(data)
        assert _is_not_html(data)


# ============================================================================
# Auth provider unit checks (no network needed, always run)
# ============================================================================

class TestCivitaiAuthProviderUrl:
    """Verify CivitaiAuthProvider URL manipulation — no network needed."""

    def test_injects_token_into_clean_url(self):
        auth = CivitaiAuthProvider(api_key="my-secret")
        result = auth.authenticate_url("https://civitai.com/api/download/models/123")
        assert result == "https://civitai.com/api/download/models/123?token=my-secret"

    def test_replaces_old_token(self):
        auth = CivitaiAuthProvider(api_key="new-key")
        result = auth.authenticate_url("https://civitai.com/api/download/models/123?token=old")
        assert "token=new-key" in result
        assert "old" not in result

    def test_preserves_other_params(self):
        auth = CivitaiAuthProvider(api_key="key")
        result = auth.authenticate_url(
            "https://civitai.com/api/download/models/123?type=Model&format=SafeTensor"
        )
        assert "type=Model" in result
        assert "format=SafeTensor" in result
        assert "token=key" in result

    def test_no_authorization_header(self):
        auth = CivitaiAuthProvider(api_key="key")
        headers = auth.get_auth_headers("https://civitai.com/api/download/models/123")
        assert headers == {}, "Should return no headers — auth is via URL ?token="

    def test_no_key_returns_url_unchanged(self):
        auth = CivitaiAuthProvider(api_key=None)
        url = "https://civitai.com/api/download/models/123"
        assert auth.authenticate_url(url) == url
