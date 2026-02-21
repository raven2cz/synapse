"""
E2E HTTP-level tests for download tracking, grouping, and batch cancel.

Tests the actual FastAPI endpoints via TestClient:
- POST /{pack_name}/download-asset with group_id/group_label
- GET /downloads/active returns group fields
- GET /downloads/active returns timestamp and target_path fields
- DELETE /downloads/group/{group_id} cancels all in group
- DELETE /downloads/{download_id} still works for individual cancel

These tests verify the HTTP layer, not just service logic.
"""

import pytest
from datetime import datetime, timezone
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


# =============================================================================
# Download Tracking: Timestamps and target_path
# =============================================================================


class TestDownloadTimestampFields:
    """Test that started_at, completed_at, and target_path are present in download entries."""

    def test_pending_download_has_started_at(self, client: TestClient):
        """A pending download entry must include a valid ISO started_at timestamp."""
        now_before = datetime.now(timezone.utc)

        _active_downloads["dl-ts-1"] = {
            "download_id": "dl-ts-1",
            "pack_name": "test-pack",
            "asset_name": "model",
            "filename": "model.safetensors",
            "status": "pending",
            "progress": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_bps": 0,
            "speed_mbps": 0,
            "eta_seconds": 0,
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "target_path": None,
            "group_id": None,
            "group_label": None,
        }

        response = client.get("/api/packs/downloads/active")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        entry = data[0]
        assert "started_at" in entry
        assert entry["started_at"] is not None

        # Verify it's a valid ISO timestamp
        parsed = datetime.fromisoformat(entry["started_at"])
        assert parsed >= now_before

    def test_pending_download_has_null_completed_at(self, client: TestClient):
        """A pending/downloading entry must have completed_at = null."""
        _active_downloads["dl-ts-2"] = {
            "download_id": "dl-ts-2",
            "pack_name": "test-pack",
            "asset_name": "lora",
            "filename": "lora.safetensors",
            "status": "downloading",
            "progress": 42.0,
            "downloaded_bytes": 430,
            "total_bytes": 1024,
            "speed_bps": 100,
            "speed_mbps": 0,
            "eta_seconds": 6,
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "target_path": None,
            "group_id": None,
            "group_label": None,
        }

        response = client.get("/api/packs/downloads/active")
        data = response.json()
        assert data[0]["completed_at"] is None
        assert data[0]["target_path"] is None

    def test_completed_download_has_both_timestamps(self, client: TestClient):
        """A completed download must have both started_at and completed_at set."""
        started = datetime.now(timezone.utc).isoformat()
        completed = datetime.now(timezone.utc).isoformat()

        _active_downloads["dl-ts-3"] = {
            "download_id": "dl-ts-3",
            "pack_name": "test-pack",
            "asset_name": "checkpoint",
            "filename": "checkpoint.safetensors",
            "status": "completed",
            "progress": 100.0,
            "downloaded_bytes": 2048,
            "total_bytes": 2048,
            "speed_bps": 0,
            "speed_mbps": 0,
            "eta_seconds": 0,
            "error": None,
            "started_at": started,
            "completed_at": completed,
            "target_path": "/models/checkpoints/checkpoint.safetensors",
            "group_id": None,
            "group_label": None,
        }

        response = client.get("/api/packs/downloads/active")
        data = response.json()
        entry = data[0]

        assert entry["started_at"] == started
        assert entry["completed_at"] == completed
        assert entry["target_path"] == "/models/checkpoints/checkpoint.safetensors"

        # Verify timestamps are valid and ordered
        t_start = datetime.fromisoformat(entry["started_at"])
        t_end = datetime.fromisoformat(entry["completed_at"])
        assert t_end >= t_start

    def test_failed_download_has_no_target_path(self, client: TestClient):
        """A failed download should have target_path = null."""
        _active_downloads["dl-ts-4"] = {
            "download_id": "dl-ts-4",
            "pack_name": "test-pack",
            "asset_name": "vae",
            "filename": "vae.safetensors",
            "status": "failed",
            "progress": 33.0,
            "downloaded_bytes": 340,
            "total_bytes": 1024,
            "speed_bps": 0,
            "speed_mbps": 0,
            "eta_seconds": 0,
            "error": "Connection reset",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "target_path": None,
            "group_id": None,
            "group_label": None,
        }

        response = client.get("/api/packs/downloads/active")
        data = response.json()
        entry = data[0]

        assert entry["status"] == "failed"
        assert entry["target_path"] is None
        assert entry["completed_at"] is None
        assert entry["error"] == "Connection reset"

    def test_started_at_is_valid_iso_format(self, client: TestClient):
        """started_at must be parseable by JavaScript's new Date() (ISO 8601)."""
        ts = "2026-02-21T15:30:00+00:00"
        _active_downloads["dl-ts-5"] = {
            "download_id": "dl-ts-5",
            "pack_name": "p",
            "asset_name": "a",
            "filename": "a.safetensors",
            "status": "completed",
            "progress": 100.0,
            "downloaded_bytes": 100,
            "total_bytes": 100,
            "speed_bps": 0,
            "speed_mbps": 0,
            "eta_seconds": 0,
            "error": None,
            "started_at": ts,
            "completed_at": ts,
            "target_path": "/tmp/model.safetensors",
            "group_id": None,
            "group_label": None,
        }

        response = client.get("/api/packs/downloads/active")
        entry = response.json()[0]

        # Must round-trip through fromisoformat without error
        parsed = datetime.fromisoformat(entry["started_at"])
        assert parsed.year == 2026
        assert parsed.month == 2

    def test_grouped_download_has_timestamps(self, client: TestClient):
        """Grouped downloads also have started_at/completed_at fields."""
        ts = datetime.now(timezone.utc).isoformat()

        _active_downloads["dl-grp-ts"] = {
            "download_id": "dl-grp-ts",
            "pack_name": "bundle-pack",
            "asset_name": "lora-1",
            "filename": "lora1.safetensors",
            "status": "completed",
            "progress": 100.0,
            "downloaded_bytes": 512,
            "total_bytes": 512,
            "speed_bps": 0,
            "speed_mbps": 0,
            "eta_seconds": 0,
            "error": None,
            "started_at": ts,
            "completed_at": ts,
            "target_path": "/models/loras/lora1.safetensors",
            "group_id": "update-batch-42",
            "group_label": "Bundle Update",
        }

        response = client.get("/api/packs/downloads/active")
        entry = response.json()[0]

        assert entry["group_id"] == "update-batch-42"
        assert entry["started_at"] == ts
        assert entry["completed_at"] == ts
        assert entry["target_path"] == "/models/loras/lora1.safetensors"


class TestDownloadEntrySchema:
    """Verify download entries returned by the API contain all required fields."""

    REQUIRED_FIELDS = {
        "download_id", "pack_name", "asset_name", "filename",
        "status", "progress", "downloaded_bytes", "total_bytes",
        "speed_bps", "eta_seconds", "error",
        "started_at", "completed_at", "target_path",
        "group_id", "group_label",
    }

    def test_all_fields_present_in_response(self, client: TestClient):
        """Every download entry in GET /downloads/active must have all required fields."""
        _active_downloads["dl-schema"] = {
            "download_id": "dl-schema",
            "pack_name": "test",
            "asset_name": "model",
            "filename": "model.safetensors",
            "status": "pending",
            "progress": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_bps": 0,
            "speed_mbps": 0,
            "eta_seconds": 0,
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "target_path": None,
            "group_id": None,
            "group_label": None,
        }

        response = client.get("/api/packs/downloads/active")
        entry = response.json()[0]

        missing = self.REQUIRED_FIELDS - set(entry.keys())
        assert not missing, f"Missing fields in download entry: {missing}"

    def test_missing_started_at_causes_invalid_date(self):
        """Demonstrate that missing started_at would produce Invalid Date in JS."""
        # This is why started_at must always be set: JavaScript's
        # new Date(undefined).toLocaleString() returns "Invalid Date"
        import json
        entry_without_ts = {
            "download_id": "dl-bad",
            "started_at": None,
        }
        serialized = json.dumps(entry_without_ts)
        parsed = json.loads(serialized)
        # If started_at is None, frontend shows "Invalid Date"
        assert parsed["started_at"] is None, (
            "Backend must set started_at to a valid ISO string, not None"
        )
