"""
Tests for Store CLI commands.

Tests inventory and backup CLI subcommands.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.store.cli import app
from src.store.models import (
    AssetKind,
    BackupConfig,
    BackupOperationResult,
    BackupStatus,
    BlobLocation,
    BlobStatus,
    CleanupResult,
    ImpactAnalysis,
    InventoryItem,
    InventoryResponse,
    InventorySummary,
    SyncItem,
    SyncResult,
)

runner = CliRunner()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_store():
    """Create a mock Store instance."""
    with patch("src.store.cli.get_store") as mock_get_store:
        store = MagicMock()
        store.is_initialized.return_value = True
        mock_get_store.return_value = store
        yield store


@pytest.fixture
def sample_inventory_response():
    """Create a sample inventory response."""
    return InventoryResponse(
        generated_at="2024-01-01T00:00:00",
        summary=InventorySummary(
            blobs_total=10,
            blobs_referenced=7,
            blobs_orphan=2,
            blobs_missing=1,
            blobs_backup_only=0,
            bytes_total=1024 * 1024 * 100,  # 100 MB
            bytes_referenced=1024 * 1024 * 80,
            bytes_orphan=1024 * 1024 * 20,
        ),
        items=[
            InventoryItem(
                sha256="abc123def456" * 5,  # 60 chars
                kind=AssetKind.CHECKPOINT,
                display_name="model.safetensors",
                size_bytes=1024 * 1024 * 50,
                location=BlobLocation.BOTH,
                on_local=True,
                on_backup=True,
                status=BlobStatus.REFERENCED,
                used_by_packs=["pack1"],
                ref_count=1,
            ),
            InventoryItem(
                sha256="orphan123456" * 5,
                kind=AssetKind.LORA,
                display_name="orphan.safetensors",
                size_bytes=1024 * 1024 * 20,
                location=BlobLocation.LOCAL_ONLY,
                on_local=True,
                on_backup=False,
                status=BlobStatus.ORPHAN,
                used_by_packs=[],
                ref_count=0,
            ),
        ],
    )


@pytest.fixture
def sample_backup_status():
    """Create a sample backup status."""
    return BackupStatus(
        enabled=True,
        connected=True,
        path="/backup/path",
        total_blobs=50,
        total_bytes=1024 * 1024 * 500,
        free_space=1024 * 1024 * 1024 * 10,  # 10 GB
        last_sync="2024-01-01T12:00:00",
    )


# =============================================================================
# Inventory List Command Tests
# =============================================================================


class TestInventoryList:
    """Tests for inventory list command."""

    def test_list_basic(self, mock_store, sample_inventory_response):
        """Test basic inventory list."""
        mock_store.inventory_service.build_inventory.return_value = sample_inventory_response

        result = runner.invoke(app, ["inventory", "list"])

        assert result.exit_code == 0
        assert "Blob Inventory" in result.output
        assert "10 blobs" in result.output
        assert "model.safetensors" in result.output

    def test_list_json(self, mock_store, sample_inventory_response):
        """Test inventory list with JSON output."""
        mock_store.inventory_service.build_inventory.return_value = sample_inventory_response

        result = runner.invoke(app, ["inventory", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "summary" in data
        assert "items" in data
        assert data["summary"]["blobs_total"] == 10

    def test_list_with_kind_filter(self, mock_store, sample_inventory_response):
        """Test inventory list with kind filter."""
        mock_store.inventory_service.build_inventory.return_value = sample_inventory_response

        result = runner.invoke(app, ["inventory", "list", "--kind", "checkpoint"])

        assert result.exit_code == 0
        mock_store.inventory_service.build_inventory.assert_called_once()
        call_args = mock_store.inventory_service.build_inventory.call_args
        assert call_args.kwargs.get("kind_filter") == AssetKind.CHECKPOINT

    def test_list_with_status_filter(self, mock_store, sample_inventory_response):
        """Test inventory list with status filter."""
        mock_store.inventory_service.build_inventory.return_value = sample_inventory_response

        result = runner.invoke(app, ["inventory", "list", "--status", "orphan"])

        assert result.exit_code == 0
        call_args = mock_store.inventory_service.build_inventory.call_args
        assert call_args.kwargs.get("status_filter") == BlobStatus.ORPHAN

    def test_list_invalid_kind(self, mock_store):
        """Test inventory list with invalid kind."""
        result = runner.invoke(app, ["inventory", "list", "--kind", "invalid"])

        assert result.exit_code == 1
        assert "Invalid kind" in result.output

    def test_list_invalid_status(self, mock_store):
        """Test inventory list with invalid status."""
        result = runner.invoke(app, ["inventory", "list", "--status", "invalid"])

        assert result.exit_code == 1
        assert "Invalid status" in result.output


class TestInventoryOrphans:
    """Tests for inventory orphans command."""

    def test_orphans_found(self, mock_store, sample_inventory_response):
        """Test orphans command when orphans exist."""
        # Filter to only orphan items
        orphan_response = InventoryResponse(
            generated_at="2024-01-01T00:00:00",
            summary=InventorySummary(
                blobs_total=1,
                blobs_orphan=1,
                bytes_orphan=1024 * 1024 * 20,
            ),
            items=[sample_inventory_response.items[1]],  # orphan item
        )
        mock_store.inventory_service.build_inventory.return_value = orphan_response

        result = runner.invoke(app, ["inventory", "orphans"])

        assert result.exit_code == 0
        assert "Orphan Blobs" in result.output
        assert "orphan.safetensors" in result.output
        assert "can be freed" in result.output

    def test_orphans_none(self, mock_store):
        """Test orphans command when no orphans exist."""
        empty_response = InventoryResponse(
            generated_at="2024-01-01T00:00:00",
            summary=InventorySummary(),
            items=[],
        )
        mock_store.inventory_service.build_inventory.return_value = empty_response

        result = runner.invoke(app, ["inventory", "orphans"])

        assert result.exit_code == 0
        assert "No orphan blobs found" in result.output


class TestInventoryMissing:
    """Tests for inventory missing command."""

    def test_missing_found(self, mock_store):
        """Test missing command when missing blobs exist."""
        missing_response = InventoryResponse(
            generated_at="2024-01-01T00:00:00",
            summary=InventorySummary(blobs_missing=1),
            items=[
                InventoryItem(
                    sha256="missing123456" * 5,
                    kind=AssetKind.CHECKPOINT,
                    display_name="missing.safetensors",
                    size_bytes=0,
                    location=BlobLocation.NOWHERE,
                    on_local=False,
                    on_backup=False,
                    status=BlobStatus.MISSING,
                    used_by_packs=["pack1", "pack2"],
                    ref_count=2,
                ),
            ],
        )
        mock_store.inventory_service.build_inventory.return_value = missing_response
        mock_store.backup_service.is_connected.return_value = False

        result = runner.invoke(app, ["inventory", "missing"])

        assert result.exit_code == 0
        assert "missing blob(s)" in result.output.lower()
        assert "missing.safetensors" in result.output

    def test_missing_none(self, mock_store):
        """Test missing command when no blobs are missing."""
        mock_store.inventory_service.build_inventory.return_value = InventoryResponse(
            generated_at="2024-01-01T00:00:00",
            summary=InventorySummary(),
            items=[],
        )

        result = runner.invoke(app, ["inventory", "missing"])

        assert result.exit_code == 0
        assert "No missing blobs" in result.output


class TestInventoryCleanup:
    """Tests for inventory cleanup command."""

    def test_cleanup_dry_run(self, mock_store, sample_inventory_response):
        """Test cleanup in dry run mode."""
        cleanup_result = CleanupResult(
            dry_run=True,
            orphans_found=2,
            orphans_deleted=0,
            bytes_freed=1024 * 1024 * 20,
            deleted=[sample_inventory_response.items[1]],
        )
        mock_store.inventory_service.cleanup_orphans.return_value = cleanup_result

        result = runner.invoke(app, ["inventory", "cleanup"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Found 2 orphan blob(s)" in result.output
        mock_store.inventory_service.cleanup_orphans.assert_called_with(dry_run=True, max_items=0)

    def test_cleanup_execute(self, mock_store):
        """Test cleanup with --execute flag."""
        cleanup_result = CleanupResult(
            dry_run=False,
            orphans_found=2,
            orphans_deleted=2,
            bytes_freed=1024 * 1024 * 20,
            deleted=[],
        )
        mock_store.inventory_service.cleanup_orphans.return_value = cleanup_result

        result = runner.invoke(app, ["inventory", "cleanup", "--execute"])

        assert result.exit_code == 0
        assert "Deleted 2 orphan blob(s)" in result.output
        mock_store.inventory_service.cleanup_orphans.assert_called_with(dry_run=False, max_items=0)

    def test_cleanup_with_max(self, mock_store):
        """Test cleanup with --max option."""
        cleanup_result = CleanupResult(
            dry_run=True,
            orphans_found=10,
            orphans_deleted=0,
            bytes_freed=1024 * 1024,
            deleted=[],
        )
        mock_store.inventory_service.cleanup_orphans.return_value = cleanup_result

        result = runner.invoke(app, ["inventory", "cleanup", "--max", "5"])

        assert result.exit_code == 0
        mock_store.inventory_service.cleanup_orphans.assert_called_with(dry_run=True, max_items=5)


class TestInventoryImpacts:
    """Tests for inventory impacts command."""

    def test_impacts_safe_to_delete(self, mock_store):
        """Test impacts for blob safe to delete."""
        impacts = ImpactAnalysis(
            sha256="abc123" * 10,
            status=BlobStatus.ORPHAN,
            size_bytes=1024 * 1024,
            used_by_packs=[],
            active_in_uis=[],
            can_delete_safely=True,
        )
        mock_store.inventory_service.get_impacts.return_value = impacts

        result = runner.invoke(app, ["inventory", "impacts", "abc123" * 10])

        assert result.exit_code == 0
        assert "Safe to delete" in result.output

    def test_impacts_not_safe(self, mock_store):
        """Test impacts for blob not safe to delete."""
        impacts = ImpactAnalysis(
            sha256="abc123" * 10,
            status=BlobStatus.REFERENCED,
            size_bytes=1024 * 1024 * 50,
            used_by_packs=["pack1", "pack2"],
            active_in_uis=[],
            can_delete_safely=False,
            warning="This blob is used by 2 pack(s).",
        )
        mock_store.inventory_service.get_impacts.return_value = impacts

        result = runner.invoke(app, ["inventory", "impacts", "abc123" * 10])

        assert result.exit_code == 0
        assert "NOT safe to delete" in result.output
        assert "pack1" in result.output


class TestInventoryVerify:
    """Tests for inventory verify command."""

    def test_verify_all(self, mock_store):
        """Test verify all blobs."""
        mock_store.inventory_service.verify_blobs.return_value = {
            "verified": 10,
            "valid": ["a" * 64, "b" * 64],
            "invalid": [],
            "duration_ms": 1500,
        }

        result = runner.invoke(app, ["inventory", "verify", "--all"])

        assert result.exit_code == 0
        assert "Verified" in result.output
        assert "10" in result.output
        mock_store.inventory_service.verify_blobs.assert_called_with(all_blobs=True)

    def test_verify_specific(self, mock_store):
        """Test verify specific blob."""
        mock_store.inventory_service.verify_blobs.return_value = {
            "verified": 1,
            "valid": ["a" * 64],
            "invalid": [],
            "duration_ms": 100,
        }

        result = runner.invoke(app, ["inventory", "verify", "--sha256", "a" * 64])

        assert result.exit_code == 0
        mock_store.inventory_service.verify_blobs.assert_called_with(sha256_list=["a" * 64])

    def test_verify_no_args(self, mock_store):
        """Test verify without required args."""
        result = runner.invoke(app, ["inventory", "verify"])

        assert result.exit_code == 1
        assert "Specify --all or --sha256" in result.output


# =============================================================================
# Backup Command Tests
# =============================================================================


class TestBackupStatus:
    """Tests for backup status command."""

    def test_status_enabled_connected(self, mock_store, sample_backup_status):
        """Test backup status when enabled and connected."""
        mock_store.get_backup_status.return_value = sample_backup_status

        result = runner.invoke(app, ["backup", "status"])

        assert result.exit_code == 0
        assert "Enabled" in result.output
        assert "Connected" in result.output
        assert "/backup/path" in result.output
        assert "50" in result.output  # blobs count

    def test_status_disabled(self, mock_store):
        """Test backup status when disabled."""
        mock_store.get_backup_status.return_value = BackupStatus(
            enabled=False,
            connected=False,
        )

        result = runner.invoke(app, ["backup", "status"])

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()

    def test_status_json(self, mock_store, sample_backup_status):
        """Test backup status with JSON output."""
        mock_store.get_backup_status.return_value = sample_backup_status

        result = runner.invoke(app, ["backup", "status", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["enabled"] is True
        assert data["connected"] is True


class TestBackupSync:
    """Tests for backup sync command."""

    def test_sync_dry_run(self, mock_store):
        """Test backup sync in dry run mode."""
        sync_result = SyncResult(
            direction="to_backup",
            dry_run=True,
            blobs_to_sync=5,
            bytes_to_sync=1024 * 1024 * 50,
            blobs_synced=5,
            bytes_synced=1024 * 1024 * 50,
            items=[
                SyncItem(sha256="a" * 64, size_bytes=1024 * 1024),
            ],
        )
        mock_store.sync_backup.return_value = sync_result

        result = runner.invoke(app, ["backup", "sync"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        mock_store.sync_backup.assert_called_with(
            direction="to_backup",
            only_missing=True,
            dry_run=True,
        )

    def test_sync_execute(self, mock_store):
        """Test backup sync with --execute."""
        sync_result = SyncResult(
            direction="to_backup",
            dry_run=False,
            blobs_to_sync=5,
            bytes_to_sync=1024 * 1024 * 50,
            blobs_synced=5,
            bytes_synced=1024 * 1024 * 50,
            items=[],
        )
        mock_store.sync_backup.return_value = sync_result

        result = runner.invoke(app, ["backup", "sync", "--execute"])

        assert result.exit_code == 0
        mock_store.sync_backup.assert_called_with(
            direction="to_backup",
            only_missing=True,
            dry_run=False,
        )

    def test_sync_from_backup(self, mock_store):
        """Test backup sync from backup direction."""
        sync_result = SyncResult(
            direction="from_backup",
            dry_run=True,
            blobs_to_sync=0,
            bytes_to_sync=0,
            blobs_synced=0,
            bytes_synced=0,
            items=[],
        )
        mock_store.sync_backup.return_value = sync_result

        result = runner.invoke(app, ["backup", "sync", "--direction", "from_backup"])

        assert result.exit_code == 0
        mock_store.sync_backup.assert_called_with(
            direction="from_backup",
            only_missing=True,
            dry_run=True,
        )

    def test_sync_invalid_direction(self, mock_store):
        """Test backup sync with invalid direction."""
        result = runner.invoke(app, ["backup", "sync", "--direction", "invalid"])

        assert result.exit_code == 1
        assert "Direction must be" in result.output


class TestBackupBlob:
    """Tests for backup blob command."""

    def test_backup_blob_success(self, mock_store):
        """Test successful blob backup."""
        mock_store.backup_blob.return_value = BackupOperationResult(
            sha256="a" * 64,
            success=True,
            bytes_copied=1024 * 1024 * 10,
            verified=True,
        )

        result = runner.invoke(app, ["backup", "blob", "a" * 64])

        assert result.exit_code == 0
        assert "Backed up blob" in result.output
        assert "Verified" in result.output

    def test_backup_blob_failure(self, mock_store):
        """Test failed blob backup."""
        mock_store.backup_blob.return_value = BackupOperationResult(
            sha256="a" * 64,
            success=False,
            bytes_copied=0,
            error="Blob not found",
        )

        result = runner.invoke(app, ["backup", "blob", "a" * 64])

        assert result.exit_code == 1
        assert "Backup failed" in result.output


class TestBackupRestore:
    """Tests for backup restore command."""

    def test_restore_success(self, mock_store):
        """Test successful blob restore."""
        mock_store.restore_blob.return_value = BackupOperationResult(
            sha256="a" * 64,
            success=True,
            bytes_copied=1024 * 1024 * 10,
            verified=True,
        )

        result = runner.invoke(app, ["backup", "restore", "a" * 64])

        assert result.exit_code == 0
        assert "Restored blob" in result.output
        assert "Verified" in result.output

    def test_restore_failure(self, mock_store):
        """Test failed blob restore."""
        mock_store.restore_blob.return_value = BackupOperationResult(
            sha256="a" * 64,
            success=False,
            bytes_copied=0,
            error="Not found in backup",
        )

        result = runner.invoke(app, ["backup", "restore", "a" * 64])

        assert result.exit_code == 1
        assert "Restore failed" in result.output


class TestBackupConfig:
    """Tests for backup config command."""

    def test_config_show(self, mock_store, sample_backup_status):
        """Test showing backup config."""
        mock_store.get_backup_status.return_value = sample_backup_status

        result = runner.invoke(app, ["backup", "config"])

        assert result.exit_code == 0
        assert "Backup Configuration" in result.output
        assert "/backup/path" in result.output

    def test_config_set_path(self, mock_store):
        """Test setting backup path."""
        mock_store.get_backup_status.return_value = BackupStatus(
            enabled=False,
            connected=False,
        )

        result = runner.invoke(app, ["backup", "config", "--path", "/new/path", "--enable"])

        assert result.exit_code == 0
        assert "updated" in result.output.lower()
        mock_store.configure_backup.assert_called_once()
        call_args = mock_store.configure_backup.call_args[0][0]
        assert call_args.path == "/new/path"
        assert call_args.enabled is True

    def test_config_json(self, mock_store, sample_backup_status):
        """Test backup config with JSON output."""
        mock_store.get_backup_status.return_value = sample_backup_status

        result = runner.invoke(app, ["backup", "config", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["enabled"] is True
        assert data["path"] == "/backup/path"


# =============================================================================
# Store Not Initialized Tests
# =============================================================================


class TestStoreNotInitialized:
    """Tests for commands when store is not initialized."""

    def test_inventory_not_initialized(self):
        """Test inventory command when store not initialized."""
        with patch("src.store.cli.get_store") as mock_get_store:
            store = MagicMock()
            store.is_initialized.return_value = False
            mock_get_store.return_value = store

            result = runner.invoke(app, ["inventory", "list"])

            assert result.exit_code == 1
            assert "not initialized" in result.output.lower()

    def test_backup_not_initialized(self):
        """Test backup command when store not initialized."""
        with patch("src.store.cli.get_store") as mock_get_store:
            store = MagicMock()
            store.is_initialized.return_value = False
            mock_get_store.return_value = store

            result = runner.invoke(app, ["backup", "status"])

            assert result.exit_code == 1
            assert "not initialized" in result.output.lower()
