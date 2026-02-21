"""
Download Authentication Providers.

Defines the DownloadAuthProvider protocol for URL-based auth injection
during blob downloads, with provider-specific implementations.

Each provider matches URLs by domain and injects appropriate auth tokens.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class DownloadAuthProvider(Protocol):
    """Protocol for download authentication providers."""

    def matches(self, url: str) -> bool:
        """Return True if this provider handles auth for the given URL."""
        ...

    def get_auth_headers(self, url: str) -> dict[str, str]:
        """Return a dictionary of headers to inject for authentication."""
        ...

    def authenticate_url(self, url: str) -> str:
        """Return the URL with auth credentials injected (or cleaned)."""
        ...

    def auth_error_message(self) -> str:
        """Return a user-friendly error message when auth fails."""
        ...


class CivitaiAuthProvider:
    """Civitai download authentication via API key.

    Uses ?token= query parameter in URL for authentication.
    The Authorization: Bearer header does NOT survive Civitai's
    cross-origin redirects (download API → CDN/S3 pre-signed URL).
    The ?token= parameter is the only reliable method for downloads.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("CIVITAI_API_KEY")
        logger.info(
            "[CivitaiAuth] Initialized: has_key=%s, key_length=%d",
            bool(self._api_key),
            len(self._api_key) if self._api_key else 0,
        )

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    def matches(self, url: str) -> bool:
        return "civitai.com" in url

    def get_auth_headers(self, url: str) -> dict[str, str]:
        # No Authorization header — Civitai download redirects to CDN
        # and requests library strips Authorization on cross-origin redirect.
        # Auth is handled via ?token= in authenticate_url() instead.
        return {}

    def authenticate_url(self, url: str) -> str:
        """Inject ?token= into the URL for Civitai download authentication.

        Civitai's /api/download/ endpoint redirects to a CDN (different host).
        Python's requests library strips Authorization headers on cross-origin
        redirects (RFC 7235). The ?token= query parameter survives redirects
        and is Civitai's recommended approach for wget/curl downloads.
        """
        from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

        if not self._api_key:
            logger.warning("[CivitaiAuth] No API key configured, download may fail")
            return url

        parsed = urlparse(url)
        qs = parse_qsl(parsed.query, keep_blank_values=True)

        # Remove existing token param (prevent duplicates)
        qs = [(k, v) for k, v in qs if k != "token"]

        # Add fresh token
        qs.append(("token", self._api_key))

        parsed = parsed._replace(query=urlencode(qs))
        logger.info(
            "[CivitaiAuth] Injected ?token= into URL: %s → has_token=%s",
            url[:80], "token=" in urlencode(qs),
        )
        return urlunparse(parsed)

    def auth_error_message(self) -> str:
        return (
            "Download failed: server returned HTML error page instead of file. "
            "This usually means authentication is required. "
            "Please configure your Civitai API key in Settings."
        )
