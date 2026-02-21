"""
Tests for async image proxy (Fix 3).

Verifies that the image proxy endpoint uses async httpx
instead of synchronous requests.get(), which would block the event loop.
"""

import pytest
import inspect


class TestImageProxyAsync:
    """Image proxy should use async httpx, not sync requests."""

    def test_proxy_image_is_async(self):
        """The proxy_image handler must be an async function."""
        from apps.api.src.routers.browse import proxy_image

        assert inspect.iscoroutinefunction(proxy_image), (
            "proxy_image must be async to avoid blocking the event loop"
        )

    def test_proxy_image_accepts_request_param(self):
        """The proxy_image handler must accept a Request parameter for app.state access."""
        from apps.api.src.routers.browse import proxy_image

        sig = inspect.signature(proxy_image)
        param_names = list(sig.parameters.keys())
        assert "request" in param_names, (
            "proxy_image must accept 'request' parameter for httpx client access"
        )

    def test_browse_imports_httpx_not_requests_for_proxy(self):
        """The proxy function should reference httpx, not requests for image fetching."""
        from apps.api.src.routers.browse import proxy_image

        source = inspect.getsource(proxy_image)
        # Should use httpx client
        assert "http_client" in source or "httpx" in source, (
            "proxy_image should use httpx async client"
        )
        # Should NOT use synchronous requests.get
        assert "req_lib.get" not in source, (
            "proxy_image should not use synchronous requests.get()"
        )


class TestMainAppLifespan:
    """Main app should create httpx.AsyncClient via lifespan."""

    def test_lifespan_source_creates_http_client(self):
        """The lifespan function should create an httpx.AsyncClient on app.state."""
        from apps.api.src.main import lifespan

        source = inspect.getsource(lifespan)
        assert "http_client" in source, (
            "lifespan must create http_client on app.state"
        )
        assert "httpx.AsyncClient" in source, (
            "lifespan must use httpx.AsyncClient"
        )
        assert "aclose" in source, (
            "lifespan must close the client on shutdown"
        )

    def test_app_has_lifespan(self):
        """FastAPI app should be configured with lifespan."""
        from apps.api.src.main import app
        assert app.router.lifespan_context is not None, (
            "App must have lifespan configured for httpx client lifecycle"
        )
