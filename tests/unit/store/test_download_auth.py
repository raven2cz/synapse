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

    def test_injects_token_without_query(self):
        provider = CivitaiAuthProvider(api_key="my-secret-key")
        result = provider.authenticate_url("https://civitai.com/api/download/models/123")
        assert result == "https://civitai.com/api/download/models/123?token=my-secret-key"

    def test_injects_token_with_existing_query(self):
        provider = CivitaiAuthProvider(api_key="my-key")
        result = provider.authenticate_url("https://civitai.com/api/download/models/123?type=Model")
        assert result == "https://civitai.com/api/download/models/123?type=Model&token=my-key"

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
