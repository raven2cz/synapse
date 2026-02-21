"""
Tests for DownloadAuthProvider protocol and implementations.

Verifies:
- CivitaiAuthProvider satisfies the DownloadAuthProvider protocol
- URL matching works correctly
- Auth token injection works correctly
- BlobStore uses auth providers for downloads
"""

import pytest
from unittest.mock import MagicMock, patch

from src.store.download_auth import (
    CivitaiAuthProvider,
    DownloadAuthProvider,
)


class TestDownloadAuthProviderProtocol:
    """Tests for DownloadAuthProvider protocol compliance."""

    def test_civitai_satisfies_protocol(self):
        provider = CivitaiAuthProvider(api_key="test-key")
        assert isinstance(provider, DownloadAuthProvider)

    def test_protocol_has_required_methods(self):
        provider = CivitaiAuthProvider(api_key="test-key")
        assert hasattr(provider, "matches")
        assert hasattr(provider, "authenticate_url")
        assert hasattr(provider, "get_auth_headers")
        assert hasattr(provider, "auth_error_message")


class TestCivitaiAuthProvider:
    """Tests for CivitaiAuthProvider."""

    def test_matches_civitai_urls(self):
        provider = CivitaiAuthProvider(api_key="test")
        assert provider.matches("https://civitai.com/api/download/models/123") is True
        assert provider.matches("https://cdn.civitai.com/file.bin") is True

    def test_does_not_match_other_urls(self):
        provider = CivitaiAuthProvider(api_key="test")
        assert provider.matches("https://huggingface.co/model") is False
        assert provider.matches("https://example.com/file") is False

    def test_authenticate_url_injects_token(self):
        """authenticate_url should inject ?token= into Civitai URLs."""
        provider = CivitaiAuthProvider(api_key="my-secret-key")
        url = "https://civitai.com/api/download/models/123"
        result = provider.authenticate_url(url)
        assert "token=my-secret-key" in result

    def test_authenticate_url_replaces_old_token(self):
        """authenticate_url should replace existing ?token= with fresh key."""
        provider = CivitaiAuthProvider(api_key="my-secret-key")
        url_with_token = "https://civitai.com/api/download/models/123?token=old-key"
        result = provider.authenticate_url(url_with_token)
        assert "token=my-secret-key" in result
        assert "old-key" not in result

    def test_authenticate_url_preserves_other_params(self):
        """authenticate_url should inject token and keep other query params."""
        provider = CivitaiAuthProvider(api_key="my-key")
        url = "https://civitai.com/api/download/models/123?type=Model&token=old&format=SafeTensor"
        result = provider.authenticate_url(url)
        assert "token=my-key" in result
        assert "old" not in result
        assert "type=Model" in result
        assert "format=SafeTensor" in result

    def test_authenticate_url_no_query_injects_token(self):
        """URL without query params should get ?token= appended."""
        provider = CivitaiAuthProvider(api_key="my-key")
        url = "https://civitai.com/api/download/models/123"
        result = provider.authenticate_url(url)
        assert result == "https://civitai.com/api/download/models/123?token=my-key"

    def test_get_auth_headers_returns_empty(self):
        """get_auth_headers should return empty dict (auth is via URL ?token=)."""
        provider = CivitaiAuthProvider(api_key="my-secret-key")
        headers = provider.get_auth_headers("https://civitai.com/api/download/models/123")
        assert headers == {}

    def test_get_auth_headers_without_key(self):
        """get_auth_headers should return empty dict without API key."""
        provider = CivitaiAuthProvider(api_key=None)
        headers = provider.get_auth_headers("https://civitai.com/api/download/models/123")
        assert headers == {}

    def test_returns_url_unchanged_without_key(self):
        provider = CivitaiAuthProvider(api_key=None)
        url = "https://civitai.com/api/download/models/123"
        result = provider.authenticate_url(url)
        assert result == url

    def test_error_message(self):
        provider = CivitaiAuthProvider(api_key="test")
        msg = provider.auth_error_message()
        assert "Civitai" in msg
        assert "API key" in msg

    @patch.dict("os.environ", {"CIVITAI_API_KEY": "env-key"})
    def test_reads_from_env(self):
        provider = CivitaiAuthProvider()
        assert provider.api_key == "env-key"

    def test_explicit_key_takes_precedence(self):
        provider = CivitaiAuthProvider(api_key="explicit-key")
        assert provider.api_key == "explicit-key"


class TestBlobStoreAuthIntegration:
    """Tests for BlobStore auth provider integration."""

    def test_blob_store_default_auth_providers(self):
        """BlobStore should create default Civitai auth provider."""
        from src.store.blob_store import BlobStore

        store = BlobStore(layout=MagicMock(), api_key="test-key")
        assert len(store._auth_providers) == 1
        assert isinstance(store._auth_providers[0], CivitaiAuthProvider)

    def test_blob_store_custom_auth_providers(self):
        """BlobStore should accept custom auth providers."""
        from src.store.blob_store import BlobStore

        custom_provider = MagicMock()
        store = BlobStore(
            layout=MagicMock(),
            auth_providers=[custom_provider],
        )
        assert store._auth_providers == [custom_provider]

    def test_blob_store_multiple_auth_providers(self):
        """BlobStore should support multiple auth providers."""
        from src.store.blob_store import BlobStore

        provider_a = MagicMock()
        provider_b = MagicMock()
        store = BlobStore(
            layout=MagicMock(),
            auth_providers=[provider_a, provider_b],
        )
        assert len(store._auth_providers) == 2
