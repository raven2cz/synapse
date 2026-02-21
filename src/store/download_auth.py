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
    """Civitai download authentication via API key."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("CIVITAI_API_KEY")

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    def matches(self, url: str) -> bool:
        return "civitai.com" in url

    def get_auth_headers(self, url: str) -> dict[str, str]:
        if not self._api_key:
            logger.warning("[CivitaiAuth] No API key configured, download may fail")
            return {}
        logger.debug("[CivitaiAuth] Using API key in Authorization header")
        return {"Authorization": f"Bearer {self._api_key}"}

    def authenticate_url(self, url: str) -> str:
        # Modern auth uses headers, but legacy lockfiles might still have 'token=' baked in.
        # We must strip it out to prevent Civitai from rejecting the request due to duplicate auth.
        from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse
        parsed = urlparse(url)
        if parsed.query:
            # Parse query params, filter out 'token', and rebuild
            qs = parse_qsl(parsed.query, keep_blank_values=True)
            new_qs = [(k, v) for k, v in qs if k != 'token']
            parsed = parsed._replace(query=urlencode(new_qs))
            return urlunparse(parsed)
        return url

    def auth_error_message(self) -> str:
        return (
            "Download failed: server returned HTML error page instead of file. "
            "This usually means authentication is required. "
            "Please configure your Civitai API key in Settings."
        )
