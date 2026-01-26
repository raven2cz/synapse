"""Tests for backup storage service."""

import pytest
from pathlib import Path

from src.store import Store
from src.store.backup_service import (
    BackupService,
    BackupError,
    BackupNotEnabledError,
    BackupNotConnectedError,
    BlobNotFoundError,
    InsufficientSpaceError,
)
from src.store.models import (
    AssetKind,
    BackupConfig,
    BlobLocation,
    BlobStatus,
    Pack,
    PackDependency,
    PackLock,
    PackSource,
    ProviderName,
    DependencySelector,
    SelectorStrategy,
    ExposeConfig,
    ResolvedDependency,
    ResolvedArtifact,
    ArtifactProvider,
)


class TestBackupStatus:
    """Test backup status checking."""

    def test_is_enabled_method_exists(self, tmp_path):
        """Verify is_enabled() method exists and works (regression test for bug #19)."""
        store = Store(tmp_path)
        store.init()

        # Default: not enabled
        assert store.backup_service.is_enabled() is False

        # After enabling
        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        assert store.backup_service.is_enabled() is True

    def test_status_disabled(self, tmp_path):
        """Status shows disabled when backup not enabled."""
        store = Store(tmp_path)
        store.init()

        status = store.get_backup_status()

        assert status.enabled is False
        assert status.connected is False

    def test_status_enabled_no_path(self, tmp_path):
        """Status shows error when enabled but no path configured."""
        store = Store(tmp_path)
        store.init()

        config = BackupConfig(enabled=True, path=None)
        store.configure_backup(config)

        status = store.get_backup_status()

        assert status.enabled is True
        assert status.connected is False
        assert status.error is not None

    def test_status_enabled_invalid_path(self, tmp_path):
        """Status shows error when path doesn't exist."""
        store = Store(tmp_path)
        store.init()

        config = BackupConfig(enabled=True, path="/nonexistent/path/12345")
        store.configure_backup(config)

        status = store.get_backup_status()

        assert status.enabled is True
        assert status.connected is False
        assert "not accessible" in status.error.lower()

    def test_status_enabled_valid_path(self, tmp_path):
        """Status shows connected when path is valid."""
        store = Store(tmp_path)
        store.init()

        # Create backup directory
        backup_path = tmp_path / "backup"
        backup_path.mkdir()

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        status = store.get_backup_status()

        assert status.enabled is True
        assert status.connected is True
        assert status.path == str(backup_path)
        assert status.total_blobs == 0
        assert status.total_bytes == 0

    def test_status_counts_backup_blobs(self, tmp_path):
        """Status correctly counts blobs on backup."""
        store = Store(tmp_path)
        store.init()

        # Create backup directory with some blobs
        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / "ab"
        blobs_dir.mkdir(parents=True)
        (blobs_dir / "abc123").write_bytes(b"test content")
        (blobs_dir / "abd456").write_bytes(b"more content")

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        status = store.get_backup_status()

        assert status.total_blobs == 2
        assert status.total_bytes == len(b"test content") + len(b"more content")


class TestBackupBlob:
    """Test backing up blobs to backup storage."""

    def test_backup_blob_not_enabled(self, tmp_path):
        """Backup fails when not enabled."""
        store = Store(tmp_path)
        store.init()

        result = store.backup_blob("abc123")

        assert result.success is False
        assert "not enabled" in result.error.lower()

    def test_backup_blob_not_connected(self, tmp_path):
        """Backup fails when not connected."""
        store = Store(tmp_path)
        store.init()

        config = BackupConfig(enabled=True, path="/nonexistent/path")
        store.configure_backup(config)

        result = store.backup_blob("abc123")

        assert result.success is False
        assert "not accessible" in result.error.lower()

    def test_backup_blob_not_found_locally(self, tmp_path):
        """Backup fails when blob doesn't exist locally."""
        store = Store(tmp_path)
        store.init()

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.backup_blob("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_backup_blob_success(self, tmp_path):
        """Successfully backup a blob."""
        store = Store(tmp_path)
        store.init()

        # Create a local blob
        content = b"test blob content for backup"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        # Setup backup
        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.backup_blob(sha256)

        assert result.success is True
        assert result.sha256 == sha256
        assert result.bytes_copied == len(content)
        assert result.verified is True

        # Verify blob exists on backup
        assert store.blob_exists_on_backup(sha256)

    def test_backup_blob_already_exists(self, tmp_path):
        """Backup succeeds quickly if blob already on backup."""
        store = Store(tmp_path)
        store.init()

        # Create a local blob
        content = b"already backed up content"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        # Setup backup with blob already there
        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.backup_blob(sha256)

        assert result.success is True
        assert result.bytes_copied == 0  # No copy needed


class TestRestoreBlob:
    """Test restoring blobs from backup storage."""

    def test_restore_blob_not_enabled(self, tmp_path):
        """Restore fails when not enabled."""
        store = Store(tmp_path)
        store.init()

        result = store.restore_blob("abc123")

        assert result.success is False
        assert "not enabled" in result.error.lower()

    def test_restore_blob_not_on_backup(self, tmp_path):
        """Restore fails when blob not on backup."""
        store = Store(tmp_path)
        store.init()

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.restore_blob("nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_restore_blob_already_local(self, tmp_path):
        """Restore succeeds quickly if blob already local."""
        store = Store(tmp_path)
        store.init()

        # Create a local blob
        content = b"already local content"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.restore_blob(sha256)

        assert result.success is True
        assert result.bytes_copied == 0  # No copy needed

    def test_restore_blob_success(self, tmp_path):
        """Successfully restore a blob from backup."""
        store = Store(tmp_path)
        store.init()

        # Create blob only on backup
        content = b"backup only content for restore"
        import hashlib
        sha256 = hashlib.sha256(content).hexdigest()

        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.restore_blob(sha256)

        assert result.success is True
        assert result.sha256 == sha256
        assert result.bytes_copied == len(content)
        assert result.verified is True

        # Verify blob now exists locally
        assert store.blob_store.blob_exists(sha256)


class TestDeleteFromBackup:
    """Test deleting blobs from backup storage."""

    def test_delete_requires_confirm(self, tmp_path):
        """Delete fails without confirm=True."""
        store = Store(tmp_path)
        store.init()

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.delete_from_backup("abc123", confirm=False)

        assert result.success is False
        assert "not confirmed" in result.error.lower()

    def test_delete_blob_not_on_backup(self, tmp_path):
        """Delete fails when blob not on backup."""
        store = Store(tmp_path)
        store.init()

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.delete_from_backup("nonexistent", confirm=True)

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_delete_from_backup_success(self, tmp_path):
        """Successfully delete a blob from backup."""
        store = Store(tmp_path)
        store.init()

        # Create blob on backup and local
        content = b"blob to delete from backup"
        import hashlib
        sha256 = hashlib.sha256(content).hexdigest()

        # Local copy
        store.blob_store.adopt(_create_temp_file(tmp_path, content))

        # Backup copy
        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.delete_from_backup(sha256, confirm=True)

        assert result.success is True
        assert result.bytes_freed == len(content)
        assert result.still_on_local is True

        # Verify blob is gone from backup but still local
        assert not store.blob_exists_on_backup(sha256)
        assert store.blob_store.blob_exists(sha256)


class TestSyncBackup:
    """Test sync operations."""

    def test_sync_dry_run(self, tmp_path):
        """Dry run shows what would be synced."""
        store = Store(tmp_path)
        store.init()

        # Create local blobs
        content1 = b"local blob 1"
        content2 = b"local blob 2"
        sha1 = store.blob_store.adopt(_create_temp_file(tmp_path, content1))
        sha2 = store.blob_store.adopt(_create_temp_file(tmp_path, content2))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.sync_backup(direction="to_backup", dry_run=True)

        assert result.dry_run is True
        assert result.blobs_to_sync == 2
        assert result.blobs_synced == 0
        assert len(result.items) == 2

    def test_sync_to_backup(self, tmp_path):
        """Sync copies local blobs to backup."""
        store = Store(tmp_path)
        store.init()

        # Create local blobs
        content1 = b"sync blob 1"
        content2 = b"sync blob 2"
        sha1 = store.blob_store.adopt(_create_temp_file(tmp_path, content1))
        sha2 = store.blob_store.adopt(_create_temp_file(tmp_path, content2))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.sync_backup(direction="to_backup", dry_run=False)

        assert result.dry_run is False
        assert result.blobs_synced == 2
        assert store.blob_exists_on_backup(sha1)
        assert store.blob_exists_on_backup(sha2)

    def test_sync_from_backup(self, tmp_path):
        """Sync copies backup blobs to local."""
        store = Store(tmp_path)
        store.init()

        # Create blobs only on backup
        import hashlib
        content1 = b"backup only 1"
        content2 = b"backup only 2"
        sha1 = hashlib.sha256(content1).hexdigest()
        sha2 = hashlib.sha256(content2).hexdigest()

        backup_path = tmp_path / "backup"
        for sha, content in [(sha1, content1), (sha2, content2)]:
            blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha[:2]
            blobs_dir.mkdir(parents=True, exist_ok=True)
            (blobs_dir / sha).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.sync_backup(direction="from_backup", dry_run=False)

        assert result.blobs_synced == 2
        assert store.blob_store.blob_exists(sha1)
        assert store.blob_store.blob_exists(sha2)


class TestBackupLocationDetection:
    """Test that inventory correctly detects blob locations."""

    def test_inventory_local_only(self, tmp_path):
        """Blob only on local shows LOCAL_ONLY."""
        store = Store(tmp_path)
        store.init()

        # Create local blob
        content = b"local only blob"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        # Enable backup but don't put blob there
        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        inventory = store.get_inventory()

        item = next((i for i in inventory.items if i.sha256 == sha256), None)
        assert item is not None
        assert item.location == BlobLocation.LOCAL_ONLY
        assert item.on_local is True
        assert item.on_backup is False

    def test_inventory_backup_only(self, tmp_path):
        """Blob only on backup shows BACKUP_ONLY status."""
        store = Store(tmp_path)
        store.init()

        # Create blob only on backup (with pack reference)
        import hashlib
        content = b"backup only blob"
        sha256 = hashlib.sha256(content).hexdigest()

        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        # Create pack that references this blob
        _create_pack_with_blob(store, "BackupOnlyPack", sha256, len(content))

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        inventory = store.get_inventory()

        item = next((i for i in inventory.items if i.sha256 == sha256), None)
        assert item is not None
        assert item.status == BlobStatus.BACKUP_ONLY
        assert item.location == BlobLocation.BACKUP_ONLY
        assert item.on_local is False
        assert item.on_backup is True

    def test_inventory_both_locations(self, tmp_path):
        """Blob on both locations shows BOTH."""
        store = Store(tmp_path)
        store.init()

        # Create local blob
        content = b"synced blob content"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        # Also put on backup
        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        inventory = store.get_inventory()

        item = next((i for i in inventory.items if i.sha256 == sha256), None)
        assert item is not None
        assert item.location == BlobLocation.BOTH
        assert item.on_local is True
        assert item.on_backup is True


class TestGuardRails:
    """Test safety guard rails."""

    def test_is_last_copy_local_only(self, tmp_path):
        """Blob only local is last copy."""
        store = Store(tmp_path)
        store.init()

        content = b"local only for last copy test"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        assert store.backup_service.is_last_copy(sha256) is True

    def test_is_last_copy_both(self, tmp_path):
        """Blob on both locations is not last copy."""
        store = Store(tmp_path)
        store.init()

        content = b"synced blob"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        assert store.backup_service.is_last_copy(sha256) is False

    def test_delete_warning_last_copy(self, tmp_path):
        """Warning when deleting last copy."""
        store = Store(tmp_path)
        store.init()

        content = b"last copy blob"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        warning = store.backup_service.get_delete_warning(sha256, "local")

        assert warning is not None
        assert "not backed up" in warning.lower()

    def test_no_warning_when_backed_up(self, tmp_path):
        """No warning when deleting local copy of backed up blob."""
        store = Store(tmp_path)
        store.init()

        content = b"backed up blob"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        warning = store.backup_service.get_delete_warning(sha256, "local")

        assert warning is None


class TestBackupVerification:
    """Test backup blob verification."""

    def test_verify_valid_backup_blob(self, tmp_path):
        """Valid backup blob passes verification."""
        store = Store(tmp_path)
        store.init()

        import hashlib
        content = b"valid backup blob"
        sha256 = hashlib.sha256(content).hexdigest()

        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        assert store.backup_service.verify_backup_blob(sha256) is True

    def test_verify_corrupted_backup_blob(self, tmp_path):
        """Corrupted backup blob fails verification."""
        store = Store(tmp_path)
        store.init()

        import hashlib
        content = b"original content"
        sha256 = hashlib.sha256(content).hexdigest()

        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        # Write wrong content with the expected hash name
        (blobs_dir / sha256).write_bytes(b"corrupted content")

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        assert store.backup_service.verify_backup_blob(sha256) is False


class TestAutoRestoreOnUse:
    """Test auto-restore from backup when using a pack."""

    def test_use_restores_missing_blob_from_backup(self, tmp_path):
        """When using a pack, missing blobs are auto-restored from backup."""
        import hashlib

        store = Store(tmp_path)
        store.init()

        # Create blob content and hash
        content = b"model blob for auto-restore test"
        sha256 = hashlib.sha256(content).hexdigest()

        # Put blob ONLY on backup (simulates: user deleted local to save space)
        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        # Create pack that references this blob
        _create_pack_with_blob(store, "AutoRestorePack", sha256, len(content))

        # Add pack to global profile
        store.profile_service.add_pack_to_global("AutoRestorePack")

        # Verify blob is NOT local yet
        assert not store.blob_store.blob_exists(sha256)
        assert store.blob_exists_on_backup(sha256)

        # Use the pack - this should auto-restore
        result = store.use("AutoRestorePack", sync=True)

        # Verify blob is now local
        assert store.blob_store.blob_exists(sha256)
        assert "restored" in str(result.notes)

    def test_use_falls_back_to_download_if_not_on_backup(self, tmp_path):
        """If blob not on backup, use falls back to download (no crash)."""
        import hashlib

        store = Store(tmp_path)
        store.init()

        content = b"missing blob content"
        sha256 = hashlib.sha256(content).hexdigest()

        # Setup backup without the blob
        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        # Create pack referencing non-existent blob (no download URLs either)
        _create_pack_with_blob(store, "MissingBlobPack", sha256, len(content))
        store.profile_service.add_pack_to_global("MissingBlobPack")

        # Use should not crash even if blob is nowhere
        result = store.use("MissingBlobPack", sync=True)

        # Blob still doesn't exist (no source to get it from)
        assert not store.blob_store.blob_exists(sha256)

    def test_use_without_backup_service_works(self, tmp_path):
        """Use works when backup is disabled."""
        store = Store(tmp_path)
        store.init()

        # Create pack with local blob
        content = b"local blob for no-backup test"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        _create_pack_with_blob(store, "LocalPack", sha256, len(content))
        store.profile_service.add_pack_to_global("LocalPack")

        # Backup NOT configured
        assert store.get_backup_status().enabled is False

        # Use should work
        result = store.use("LocalPack", sync=True)

        assert result.synced is True


class TestSyncEdgeCases:
    """Test sync edge cases and error handling."""

    def test_sync_is_idempotent(self, tmp_path):
        """Running sync twice has same result."""
        store = Store(tmp_path)
        store.init()

        content = b"idempotent sync test"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        # First sync
        result1 = store.sync_backup(direction="to_backup", dry_run=False)
        assert result1.blobs_synced == 1

        # Second sync - should sync 0 (already there)
        result2 = store.sync_backup(direction="to_backup", dry_run=False)
        assert result2.blobs_synced == 0
        assert result2.blobs_to_sync == 0

    def test_sync_only_missing_blobs(self, tmp_path):
        """Sync only copies blobs not on target."""
        import hashlib

        store = Store(tmp_path)
        store.init()

        # Create 2 local blobs
        content1 = b"blob 1 for selective sync"
        content2 = b"blob 2 for selective sync"
        sha1 = store.blob_store.adopt(_create_temp_file(tmp_path, content1))
        sha2 = store.blob_store.adopt(_create_temp_file(tmp_path, content2))

        # Put blob1 already on backup
        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha1[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha1).write_bytes(content1)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        # Sync should only sync blob2
        result = store.sync_backup(direction="to_backup", dry_run=False)

        assert result.blobs_to_sync == 1  # Only blob2 was missing on backup
        assert result.blobs_synced == 1

    def test_sync_verifies_copied_blobs(self, tmp_path):
        """Sync verifies hash after copy."""
        store = Store(tmp_path)
        store.init()

        content = b"verification test content"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        result = store.sync_backup(direction="to_backup", dry_run=False)

        assert result.blobs_synced == 1
        # Verify the backup blob is valid
        assert store.backup_service.verify_backup_blob(sha256)

    def test_restore_corrupted_blob_fails(self, tmp_path):
        """Restoring a corrupted backup blob fails verification."""
        import hashlib

        store = Store(tmp_path)
        store.init()

        content = b"original restore content"
        sha256 = hashlib.sha256(content).hexdigest()

        # Put CORRUPTED blob on backup
        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(b"CORRUPTED DATA")

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        # Restore should fail due to verification
        result = store.restore_blob(sha256)

        assert result.success is False
        assert "verification" in result.error.lower() or "failed" in result.error.lower()
        # Local blob should NOT exist (restore was rejected)
        assert not store.blob_store.blob_exists(sha256)


class TestSyncDirectionSymmetry:
    """Test that sync works correctly in both directions."""

    def test_round_trip_sync(self, tmp_path):
        """Blob can be synced to backup and back."""
        store = Store(tmp_path)
        store.init()

        # Create and backup blob
        content = b"round trip test content"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        # Sync to backup
        store.sync_backup(direction="to_backup", dry_run=False)
        assert store.blob_exists_on_backup(sha256)

        # Delete local
        store.blob_store.remove_blob(sha256)
        assert not store.blob_store.blob_exists(sha256)

        # Sync from backup
        result = store.sync_backup(direction="from_backup", dry_run=False)

        assert result.blobs_synced == 1
        assert store.blob_store.blob_exists(sha256)

        # Verify content is intact
        local_path = store.layout.blob_path(sha256)
        assert local_path.read_bytes() == content


# =============================================================================
# Pack-Level Pull/Push Tests
# =============================================================================

class TestBackupPullPack:
    """Test backup pull <pack> command."""

    def test_pull_pack_restores_from_backup(self, tmp_path):
        """Pull restores all pack blobs from backup."""
        import hashlib

        store = Store(tmp_path)
        store.init()

        # Create blob content
        content = b"model for pull test"
        sha256 = hashlib.sha256(content).hexdigest()

        # Put blob ONLY on backup
        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        # Create pack referencing the blob
        _create_pack_with_blob(store, "PullTestPack", sha256, len(content))

        # Verify blob is NOT local
        assert not store.blob_store.blob_exists(sha256)
        assert store.blob_exists_on_backup(sha256)

        # Pull the pack (execute)
        result = store.pull_pack("PullTestPack", dry_run=False)

        assert result.blobs_synced == 1
        assert result.bytes_synced == len(content)
        assert store.blob_store.blob_exists(sha256)

    def test_pull_pack_dry_run_no_changes(self, tmp_path):
        """Dry run doesn't actually restore."""
        import hashlib

        store = Store(tmp_path)
        store.init()

        content = b"model for dry run test"
        sha256 = hashlib.sha256(content).hexdigest()

        # Put blob on backup
        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        _create_pack_with_blob(store, "DryRunPack", sha256, len(content))

        # Dry run
        result = store.pull_pack("DryRunPack", dry_run=True)

        assert result.dry_run is True
        assert result.blobs_to_sync == 1
        assert result.blobs_synced == 0  # Nothing actually restored
        assert not store.blob_store.blob_exists(sha256)  # Still not local

    def test_pull_pack_skips_existing_blobs(self, tmp_path):
        """Pull skips blobs that are already local."""
        store = Store(tmp_path)
        store.init()

        # Create local blob
        content = b"already local model"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        # Setup backup
        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        _create_pack_with_blob(store, "LocalPack", sha256, len(content))

        # Pull - should find nothing to restore
        result = store.pull_pack("LocalPack", dry_run=False)

        assert result.blobs_to_sync == 0
        assert result.blobs_synced == 0

    def test_pull_pack_without_backup_returns_error(self, tmp_path):
        """Pull without connected backup returns error."""
        import hashlib

        store = Store(tmp_path)
        store.init()

        content = b"no backup test"
        sha256 = hashlib.sha256(content).hexdigest()

        _create_pack_with_blob(store, "NoBackupPack", sha256, len(content))

        # No backup configured
        result = store.pull_pack("NoBackupPack", dry_run=False)

        assert "Backup not connected" in result.errors


class TestBackupPushPack:
    """Test backup push <pack> command."""

    def test_push_pack_backs_up_blobs(self, tmp_path):
        """Push backs up all local pack blobs."""
        store = Store(tmp_path)
        store.init()

        # Create local blob
        content = b"model for push test"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        # Setup backup
        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        _create_pack_with_blob(store, "PushTestPack", sha256, len(content))

        # Verify blob is NOT on backup
        assert not store.blob_exists_on_backup(sha256)

        # Push the pack
        result = store.push_pack("PushTestPack", dry_run=False)

        assert result.blobs_synced == 1
        assert result.bytes_synced == len(content)
        assert store.blob_exists_on_backup(sha256)
        # Local copy still exists
        assert store.blob_store.blob_exists(sha256)

    def test_push_pack_with_cleanup_deletes_local(self, tmp_path):
        """Push with cleanup deletes local copies after backup."""
        store = Store(tmp_path)
        store.init()

        content = b"model for cleanup test"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        _create_pack_with_blob(store, "CleanupPack", sha256, len(content))

        # Push with cleanup
        result = store.push_pack("CleanupPack", dry_run=False, cleanup=True)

        assert result.blobs_synced == 1
        assert store.blob_exists_on_backup(sha256)  # On backup
        assert not store.blob_store.blob_exists(sha256)  # Deleted locally
        assert "cleaned_up" in str(result.errors)  # Note in errors

    def test_push_pack_dry_run_no_changes(self, tmp_path):
        """Dry run doesn't actually backup."""
        store = Store(tmp_path)
        store.init()

        content = b"dry run push test"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        _create_pack_with_blob(store, "DryPushPack", sha256, len(content))

        # Dry run
        result = store.push_pack("DryPushPack", dry_run=True)

        assert result.dry_run is True
        assert result.blobs_to_sync == 1
        assert result.blobs_synced == 0
        assert not store.blob_exists_on_backup(sha256)

    def test_push_pack_skips_already_backed_up(self, tmp_path):
        """Push skips blobs already on backup."""
        store = Store(tmp_path)
        store.init()

        content = b"already backed up model"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        # Put blob on backup too
        backup_path = tmp_path / "backup"
        blobs_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / sha256[:2]
        blobs_dir.mkdir(parents=True)
        (blobs_dir / sha256).write_bytes(content)

        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        _create_pack_with_blob(store, "AlreadyBackedPack", sha256, len(content))

        # Push - should find nothing to backup
        result = store.push_pack("AlreadyBackedPack", dry_run=False)

        assert result.blobs_to_sync == 0
        assert result.blobs_synced == 0


class TestPullPushRoundTrip:
    """Test full round-trip workflow: push, delete local, pull."""

    def test_full_round_trip(self, tmp_path):
        """Full workflow: push to backup, delete local, pull back."""
        store = Store(tmp_path)
        store.init()

        # Create local blob
        content = b"round trip model content"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        _create_pack_with_blob(store, "RoundTripPack", sha256, len(content))
        store.profile_service.add_pack_to_global("RoundTripPack")

        # Step 1: Push to backup with cleanup
        push_result = store.push_pack("RoundTripPack", dry_run=False, cleanup=True)
        assert push_result.blobs_synced == 1
        assert not store.blob_store.blob_exists(sha256)
        assert store.blob_exists_on_backup(sha256)

        # Step 2: Pull back from backup
        pull_result = store.pull_pack("RoundTripPack", dry_run=False)
        assert pull_result.blobs_synced == 1
        assert store.blob_store.blob_exists(sha256)

        # Verify content integrity
        local_path = store.layout.blob_path(sha256)
        assert local_path.read_bytes() == content


# =============================================================================
# Helper Functions
# =============================================================================

def _create_temp_file(tmp_path: Path, content: bytes) -> Path:
    """Create a temporary file with given content."""
    file_path = tmp_path / f"temp_{hash(content)}.bin"
    file_path.write_bytes(content)
    return file_path


def _create_pack_with_blob(
    store: Store,
    pack_name: str,
    sha256: str,
    size_bytes: int,
    kind: AssetKind = AssetKind.CHECKPOINT,
):
    """Create a pack with a lock file referencing a blob."""
    pack = Pack(
        name=pack_name,
        pack_type=kind,
        source=PackSource(provider=ProviderName.LOCAL),
        dependencies=[
            PackDependency(
                id="main",
                kind=kind,
                selector=DependencySelector(strategy=SelectorStrategy.LOCAL_FILE),
                expose=ExposeConfig(filename=f"{pack_name}_model.safetensors"),
            )
        ],
    )

    lock = PackLock(
        pack=pack_name,
        resolved=[
            ResolvedDependency(
                dependency_id="main",
                artifact=ResolvedArtifact(
                    kind=kind,
                    sha256=sha256,
                    size_bytes=size_bytes,
                    provider=ArtifactProvider(name=ProviderName.LOCAL),
                ),
            )
        ],
    )

    store.layout.save_pack(pack)
    store.layout.save_pack_lock(lock)
