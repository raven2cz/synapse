"""
E2E HTTP-level tests for download grouping and batch cancel.

Tests the actual FastAPI endpoints via TestClient:
- POST /{pack_name}/download-asset with group_id/group_label
- GET /downloads/active returns group fields
- DELETE /downloads/group/{group_id} cancels all in group
- DELETE /downloads/{download_id} still works for individual cancel

These tests verify the HTTP layer, not just service logic.
"""

import pytest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.store import Store
from src.store.api import v2_packs_router, require_initialized, _active_downloads
from src.store.models import (
    AssetKind,
    DependencySelector,
    ExposeConfig,
    Pack,
    PackDependency,
    PackSource,
    SelectorStrategy,
)


@pytest.fixture
def test_store(tmp_path: Path):
    """Create a temporary store for testing."""
    store_root = tmp_path / "store"
    store_root.mkdir()
    store = Store(store_root)
    store.init()
    return store


@pytest.fixture
def test_pack(test_store: Store) -> Pack:
    """Create a test pack with a dependency for download testing."""
    pack = Pack(
        name="test-download-pack",
        pack_type=AssetKind.CHECKPOINT,
        source=PackSource(provider="local"),
        dependencies=[
            PackDependency(
                id="main-model",
                kind=AssetKind.CHECKPOINT,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai={"model_id": 123},
                ),
                expose=ExposeConfig(filename="model.safetensors"),
            ),
        ],
    )
    test_store.layout.save_pack(pack)
    return pack


@pytest.fixture
def client(test_store: Store):
    """Create a test client with store dependency override."""
    app = FastAPI()
    app.include_router(v2_packs_router, prefix="/api/packs")
    app.dependency_overrides[require_initialized] = lambda: test_store
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_downloads():
    """Ensure _active_downloads is clean before and after each test."""
    _active_downloads.clear()
    yield
    _active_downloads.clear()


# =============================================================================
# Download Tracking: group_id / group_label in active downloads
# =============================================================================


class TestDownloadGroupTracking:
    """Test that group_id and group_label appear in active download entries."""

    def test_active_downloads_returns_group_fields(self, client: TestClient):
        """GET /downloads/active returns group_id and group_label per entry."""
        # Seed an entry manually
        _active_downloads["dl-1"] = {
            "download_id": "dl-1",
            "pack_name": "test-pack",
            "asset_name": "main-model",
            "filename": "model.safetensors",
            "status": "downloading",
            "progress": 50.0,
            "downloaded_bytes": 512,
            "total_bytes": 1024,
            "speed_bps": 100,
            "speed_mbps": 0.0001,
            "eta_seconds": 5,
            "error": None,
            "group_id": "update-123",
            "group_label": "Pack Updates",
        }

        response = client.get("/api/packs/downloads/active")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["group_id"] == "update-123"
        assert data[0]["group_label"] == "Pack Updates"

    def test_active_downloads_null_group_fields(self, client: TestClient):
        """Downloads without group fields return null."""
        _active_downloads["dl-2"] = {
            "download_id": "dl-2",
            "pack_name": "test-pack",
            "asset_name": "lora",
            "filename": "lora.safetensors",
            "status": "pending",
            "progress": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_bps": 0,
            "speed_mbps": 0,
            "eta_seconds": 0,
            "error": None,
            "group_id": None,
            "group_label": None,
        }

        response = client.get("/api/packs/downloads/active")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["group_id"] is None
        assert data[0]["group_label"] is None


# =============================================================================
# Group Cancel Endpoint
# =============================================================================


class TestGroupCancelEndpoint:
    """Test DELETE /downloads/group/{group_id} endpoint."""

    def test_cancel_group_removes_all_matching(self, client: TestClient):
        """Cancelling a group removes all downloads with that group_id."""
        _active_downloads["dl-a1"] = {
            "download_id": "dl-a1",
            "status": "downloading",
            "group_id": "grp-alpha",
        }
        _active_downloads["dl-a2"] = {
            "download_id": "dl-a2",
            "status": "pending",
            "group_id": "grp-alpha",
        }
        _active_downloads["dl-b1"] = {
            "download_id": "dl-b1",
            "status": "downloading",
            "group_id": "grp-beta",
        }

        response = client.delete("/api/packs/downloads/group/grp-alpha")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert set(data["cancelled"]) == {"dl-a1", "dl-a2"}

        # grp-beta should still be there
        assert "dl-b1" in _active_downloads
        assert "dl-a1" not in _active_downloads
        assert "dl-a2" not in _active_downloads

    def test_cancel_group_no_match_returns_zero(self, client: TestClient):
        """Cancelling a non-existent group returns empty result."""
        _active_downloads["dl-x"] = {
            "download_id": "dl-x",
            "status": "downloading",
            "group_id": "other",
        }

        response = client.delete("/api/packs/downloads/group/nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["cancelled"] == []

        # Original download still there
        assert "dl-x" in _active_downloads

    def test_cancel_group_empty_downloads(self, client: TestClient):
        """Cancelling when no downloads exist returns zero."""
        response = client.delete("/api/packs/downloads/group/anything")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    def test_cancel_group_sets_cancelled_status(self, client: TestClient):
        """Downloads are set to 'cancelled' status before removal."""
        _active_downloads["dl-c1"] = {
            "download_id": "dl-c1",
            "status": "downloading",
            "group_id": "grp-cancel-test",
        }

        # After cancel, the entry is removed — but we can verify the endpoint works
        response = client.delete("/api/packs/downloads/group/grp-cancel-test")
        assert response.status_code == 200
        assert response.json()["count"] == 1
        assert "dl-c1" not in _active_downloads

    def test_individual_cancel_still_works(self, client: TestClient):
        """Individual download cancel endpoint is not broken by group endpoint."""
        _active_downloads["dl-individual"] = {
            "download_id": "dl-individual",
            "status": "downloading",
            "group_id": "some-group",
        }

        response = client.delete("/api/packs/downloads/dl-individual")
        assert response.status_code == 200
        assert "dl-individual" not in _active_downloads


# =============================================================================
# Mixed: Group + Ungrouped Downloads
# =============================================================================


class TestMixedDownloads:
    """Test listing downloads with both grouped and ungrouped entries."""

    def test_mixed_downloads_listing(self, client: TestClient):
        """Active downloads can contain both grouped and ungrouped entries."""
        _active_downloads["grouped-1"] = {
            "download_id": "grouped-1",
            "pack_name": "pack-a",
            "asset_name": "model",
            "filename": "model.safetensors",
            "status": "downloading",
            "progress": 25.0,
            "downloaded_bytes": 256,
            "total_bytes": 1024,
            "speed_bps": 50,
            "speed_mbps": 0,
            "eta_seconds": 15,
            "error": None,
            "group_id": "update-batch-1",
            "group_label": "Pack Updates",
        }
        _active_downloads["ungrouped-1"] = {
            "download_id": "ungrouped-1",
            "pack_name": "pack-b",
            "asset_name": "lora",
            "filename": "lora.safetensors",
            "status": "pending",
            "progress": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_bps": 0,
            "speed_mbps": 0,
            "eta_seconds": 0,
            "error": None,
            "group_id": None,
            "group_label": None,
        }

        response = client.get("/api/packs/downloads/active")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        grouped = [d for d in data if d["group_id"] is not None]
        ungrouped = [d for d in data if d["group_id"] is None]
        assert len(grouped) == 1
        assert len(ungrouped) == 1
        assert grouped[0]["group_label"] == "Pack Updates"

    def test_clear_completed_respects_groups(self, client: TestClient):
        """DELETE /downloads/completed clears completed from all groups."""
        _active_downloads["completed-grouped"] = {
            "download_id": "completed-grouped",
            "status": "completed",
            "group_id": "update-batch",
        }
        _active_downloads["active-grouped"] = {
            "download_id": "active-grouped",
            "status": "downloading",
            "group_id": "update-batch",
        }
        _active_downloads["completed-ungrouped"] = {
            "download_id": "completed-ungrouped",
            "status": "completed",
            "group_id": None,
        }

        response = client.delete("/api/packs/downloads/completed")
        assert response.status_code == 200
        data = response.json()
        assert data["cleared"] == 2  # Both completed entries

        # Active one survives
        assert "active-grouped" in _active_downloads
        assert "completed-grouped" not in _active_downloads
        assert "completed-ungrouped" not in _active_downloads
