"""
Integration tests for MCP store server tools.

Tests _impl functions with real Store (TestStoreContext fixture).
Creates actual packs/blobs and verifies tool output.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.helpers.fixtures import (
    TestStoreContext,
    FakeCivitaiClient,
    build_test_model,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def store_ctx():
    """Create an isolated test store with a sample pack."""
    fake_civitai = FakeCivitaiClient()
    model = build_test_model(
        model_id=1001,
        version_id=2001,
        file_id=3001,
        name="TestCheckpoint",
        model_type="Checkpoint",
        file_name="test_checkpoint_v1.safetensors",
    )
    fake_civitai.add_model(model)

    with TestStoreContext(civitai_client=fake_civitai) as ctx:
        ctx.store.init()
        yield ctx


def _import_pack(ctx, model_id=1001, pack_name=None):
    """Import a pack from the fake civitai client, mocking HTTP downloads."""
    with patch("src.store.blob_store.BlobStore._download_http") as mock_dl:
        # Simulate successful download
        def fake_download(url, expected_sha256=None, on_progress=None):
            if expected_sha256:
                blob_path = ctx.store.blob_store.blob_path(expected_sha256)
                blob_path.parent.mkdir(parents=True, exist_ok=True)
                blob_path.write_bytes(b"fake model content " + expected_sha256.encode()[:20])
            return expected_sha256

        mock_dl.side_effect = fake_download
        pack = ctx.store.import_civitai(
            url=f"https://civitai.com/models/{model_id}",
            download_previews=False,
            pack_name=pack_name,
        )
    return pack


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
class TestListPacksWithRealStore:
    """Test list_packs with real store and imported pack."""

    def test_list_packs_shows_imported(self, store_ctx):
        from src.avatar.mcp.store_server import _list_packs_impl

        _import_pack(store_ctx)

        result = _list_packs_impl(store=store_ctx.store)
        assert "Found 1 pack" in result
        assert "TestCheckpoint" in result

    def test_list_packs_empty_store(self, store_ctx):
        from src.avatar.mcp.store_server import _list_packs_impl

        result = _list_packs_impl(store=store_ctx.store)
        assert "No packs in the store" in result


@pytest.mark.integration
class TestGetPackDetailsWithRealStore:
    """Test get_pack_details with real store."""

    def test_details_of_imported_pack(self, store_ctx):
        from src.avatar.mcp.store_server import _get_pack_details_impl

        pack = _import_pack(store_ctx)

        result = _get_pack_details_impl(store=store_ctx.store, pack_name=pack.name)
        assert f"Pack: {pack.name}" in result
        assert "Source: civitai" in result

    def test_not_found(self, store_ctx):
        from src.avatar.mcp.store_server import _get_pack_details_impl

        result = _get_pack_details_impl(store=store_ctx.store, pack_name="NoSuchPack")
        assert "not found" in result.lower()


@pytest.mark.integration
class TestInventorySummaryWithBlobs:
    """Test inventory summary with real blobs."""

    def test_summary_after_import(self, store_ctx):
        from src.avatar.mcp.store_server import _get_inventory_summary_impl

        _import_pack(store_ctx)

        result = _get_inventory_summary_impl(store=store_ctx.store)
        assert "Inventory Summary" in result
        assert "Total blobs:" in result

    def test_summary_empty_store(self, store_ctx):
        from src.avatar.mcp.store_server import _get_inventory_summary_impl

        result = _get_inventory_summary_impl(store=store_ctx.store)
        assert "Total blobs: 0" in result


@pytest.mark.integration
class TestOrphanDetection:
    """Test orphan blob detection with real store."""

    def test_orphan_blob_detected(self, store_ctx):
        from src.avatar.mcp.store_server import _find_orphan_blobs_impl

        # Create an orphan blob (not referenced by any pack)
        store_ctx.create_blob("orphan content 12345")

        result = _find_orphan_blobs_impl(store=store_ctx.store)
        assert "orphan" in result.lower()


@pytest.mark.integration
class TestBackupStatusDefault:
    """Test backup status in default (not connected) state."""

    def test_backup_not_enabled(self, store_ctx):
        from src.avatar.mcp.store_server import _get_backup_status_impl

        result = _get_backup_status_impl(store=store_ctx.store)
        # Default store has no backup configured
        assert "not enabled" in result.lower() or "not connected" in result.lower()


@pytest.mark.integration
class TestStorageStatsWithData:
    """Test storage stats with real data."""

    def test_stats_with_pack(self, store_ctx):
        from src.avatar.mcp.store_server import _get_storage_stats_impl

        _import_pack(store_ctx)

        result = _get_storage_stats_impl(store=store_ctx.store)
        assert "Storage Statistics" in result
        assert "Total blobs:" in result

    def test_stats_empty(self, store_ctx):
        from src.avatar.mcp.store_server import _get_storage_stats_impl

        result = _get_storage_stats_impl(store=store_ctx.store)
        assert "Storage Statistics" in result
        assert "Total blobs: 0" in result


@pytest.mark.integration
class TestSearchWithRealStore:
    """Test search against real store."""

    def test_search_finds_pack(self, store_ctx):
        from src.avatar.mcp.store_server import _search_packs_impl

        _import_pack(store_ctx)

        result = _search_packs_impl(store=store_ctx.store, query="Test")
        assert "Found" in result
        assert "TestCheckpoint" in result

    def test_search_no_results(self, store_ctx):
        from src.avatar.mcp.store_server import _search_packs_impl

        _import_pack(store_ctx)

        result = _search_packs_impl(store=store_ctx.store, query="zzzznonexistent")
        assert "No packs found" in result
