"""
Tests for GET /api/packs/{pack_name}/preview-analysis endpoint.

Tests:
- Returns previews with hints for packs that have sidecar data
- Returns 404 for non-existent pack
- Returns empty results for pack without previews
- Returns generation params from sidecar
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.store.models import AssetKind


def _make_test_app(mock_store):
    """Create a FastAPI app with the preview-analysis router, injecting a mock store."""
    from fastapi import FastAPI
    from src.store.api import v2_packs_router, require_initialized

    app = FastAPI()
    app.include_router(v2_packs_router, prefix="/api/packs")
    app.dependency_overrides[require_initialized] = lambda: mock_store
    return app


def _make_mock_store(tmp_path, has_pack=True, has_previews=True):
    """Create a mock store with optional pack and previews."""
    mock_store = MagicMock()
    mock_layout = MagicMock()

    previews_path = tmp_path / "resources" / "previews"
    previews_path.mkdir(parents=True, exist_ok=True)
    mock_layout.pack_previews_path.return_value = previews_path
    mock_store.layout = mock_layout

    if not has_pack:
        mock_store.get_pack.return_value = None
        return mock_store

    mock_pack = MagicMock()
    mock_pack.name = "TestPack"

    if has_previews:
        preview1 = MagicMock()
        preview1.filename = "001.jpeg"
        preview1.media_type = "image"
        preview1.width = 832
        preview1.height = 1216
        preview1.nsfw = False
        preview1.url = "https://example.com/001.jpeg"
        preview1.thumbnail_url = None

        preview2 = MagicMock()
        preview2.filename = "002.jpeg"
        preview2.media_type = "image"
        preview2.width = 512
        preview2.height = 768
        preview2.nsfw = False
        preview2.url = "https://example.com/002.jpeg"
        preview2.thumbnail_url = None

        mock_pack.previews = [preview1, preview2]

        sidecar1 = {
            "Model": "Juggernaut_XL",
            "Model hash": "d91d35736d",
            "resources": [
                {"name": "detail_tweaker", "type": "lora", "weight": 0.5},
            ],
            "sampler": "DPM++ 2M",
            "steps": 35,
            "seed": 42,
        }
        (previews_path / "001.jpeg.json").write_text(json.dumps(sidecar1))

        sidecar2 = {"prompt": "beautiful scenery"}
        (previews_path / "002.jpeg.json").write_text(json.dumps(sidecar2))
    else:
        mock_pack.previews = []

    mock_store.get_pack.return_value = mock_pack
    return mock_store


class TestPreviewAnalysisEndpoint:
    """Tests for the preview-analysis API endpoint."""

    def test_returns_previews_with_hints(self, tmp_path):
        """Endpoint returns preview analysis with model hints."""
        from fastapi.testclient import TestClient

        mock_store = _make_mock_store(tmp_path)
        app = _make_test_app(mock_store)
        client = TestClient(app)

        resp = client.get("/api/packs/TestPack/preview-analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pack_name"] == "TestPack"
        assert "previews" in data
        assert "total_hints" in data
        assert len(data["previews"]) == 2

        first = data["previews"][0]
        assert first["filename"] == "001.jpeg"
        assert len(first["hints"]) >= 1
        ckpt_hints = [h for h in first["hints"] if h["kind"] == "checkpoint"]
        assert len(ckpt_hints) == 1
        assert ckpt_hints[0]["hash"] == "d91d35736d"

        assert first["generation_params"] is not None
        assert first["generation_params"]["sampler"] == "DPM++ 2M"

        assert data["total_hints"] >= 2

    def test_pack_not_found(self, tmp_path):
        """Endpoint returns 404 for non-existent pack."""
        from fastapi.testclient import TestClient

        mock_store = _make_mock_store(tmp_path, has_pack=False)
        app = _make_test_app(mock_store)
        client = TestClient(app)

        resp = client.get("/api/packs/NonExistent/preview-analysis")
        assert resp.status_code == 404

    def test_pack_without_previews(self, tmp_path):
        """Endpoint returns empty results for pack without previews."""
        from fastapi.testclient import TestClient

        mock_store = _make_mock_store(tmp_path, has_previews=False)
        app = _make_test_app(mock_store)
        client = TestClient(app)

        resp = client.get("/api/packs/TestPack/preview-analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["previews"] == []
        assert data["total_hints"] == 0

    def test_preview_url_included(self, tmp_path):
        """Endpoint includes preview URL in response."""
        from fastapi.testclient import TestClient

        mock_store = _make_mock_store(tmp_path)
        app = _make_test_app(mock_store)
        client = TestClient(app)

        resp = client.get("/api/packs/TestPack/preview-analysis")
        data = resp.json()
        assert data["previews"][0]["url"] == "https://example.com/001.jpeg"

    def test_hint_includes_weight(self, tmp_path):
        """LoRA hints include weight from resources."""
        from fastapi.testclient import TestClient

        mock_store = _make_mock_store(tmp_path)
        app = _make_test_app(mock_store)
        client = TestClient(app)

        resp = client.get("/api/packs/TestPack/preview-analysis")
        data = resp.json()
        lora_hints = [
            h for p in data["previews"]
            for h in p["hints"]
            if h.get("kind") == "lora"
        ]
        assert len(lora_hints) >= 1
        assert lora_hints[0]["weight"] == 0.5
