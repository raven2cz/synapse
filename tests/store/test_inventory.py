"""Tests for inventory service."""

import pytest
from pathlib import Path

from src.store import Store
from src.store.models import (
    AssetKind,
    BlobManifest,
    BlobOrigin,
    BlobStatus,
    BlobLocation,
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


class TestInventoryDetection:
    """Test orphan/referenced/missing detection."""

    def test_empty_store_returns_empty_inventory(self, tmp_path):
        """Empty store has no blobs."""
        store = Store(tmp_path)
        store.init()

        inventory = store.get_inventory()

        assert inventory.summary.blobs_total == 0
        assert inventory.summary.blobs_referenced == 0
        assert inventory.summary.blobs_orphan == 0
        assert inventory.summary.blobs_missing == 0
        assert len(inventory.items) == 0

    def test_detects_orphan_blob(self, tmp_path):
        """Blob without any pack reference is ORPHAN."""
        store = Store(tmp_path)
        store.init()

        # Add blob directly without pack reference
        blob_content = b"orphan blob content for testing"
        sha256 = store.blob_store.adopt(
            _create_temp_file(tmp_path, blob_content)
        )

        inventory = store.get_inventory()

        assert inventory.summary.blobs_orphan == 1
        assert inventory.summary.blobs_total == 1

        orphan = next((i for i in inventory.items if i.sha256 == sha256), None)
        assert orphan is not None
        assert orphan.status == BlobStatus.ORPHAN
        assert orphan.location == BlobLocation.LOCAL_ONLY
        assert len(orphan.used_by_packs) == 0

    def test_detects_referenced_blob(self, tmp_path):
        """Blob referenced by pack is REFERENCED."""
        store = Store(tmp_path)
        store.init()

        # Create blob
        blob_content = b"referenced blob content"
        sha256 = store.blob_store.adopt(
            _create_temp_file(tmp_path, blob_content)
        )

        # Create pack with lock that references the blob
        pack_name = "TestPack"
        _create_pack_with_blob(store, pack_name, sha256, len(blob_content))

        inventory = store.get_inventory()

        assert inventory.summary.blobs_referenced == 1
        assert inventory.summary.blobs_orphan == 0

        item = next((i for i in inventory.items if i.sha256 == sha256), None)
        assert item is not None
        assert item.status == BlobStatus.REFERENCED
        assert pack_name in item.used_by_packs

    def test_detects_missing_blob(self, tmp_path):
        """Pack referencing non-existent blob has MISSING status."""
        store = Store(tmp_path)
        store.init()

        # Create pack with lock that references non-existent blob
        pack_name = "MissingBlobPack"
        fake_sha256 = "0" * 64  # Non-existent blob
        _create_pack_with_blob(store, pack_name, fake_sha256, 1000)

        inventory = store.get_inventory()

        assert inventory.summary.blobs_missing == 1

        item = next((i for i in inventory.items if i.sha256 == fake_sha256), None)
        assert item is not None
        assert item.status == BlobStatus.MISSING
        assert item.location == BlobLocation.NOWHERE

    def test_multiple_packs_same_blob(self, tmp_path):
        """Blob used by multiple packs has correct ref_count."""
        store = Store(tmp_path)
        store.init()

        # Create blob
        blob_content = b"shared blob content"
        sha256 = store.blob_store.adopt(
            _create_temp_file(tmp_path, blob_content)
        )

        # Create two packs referencing same blob
        _create_pack_with_blob(store, "Pack1", sha256, len(blob_content))
        _create_pack_with_blob(store, "Pack2", sha256, len(blob_content))

        inventory = store.get_inventory()

        item = next((i for i in inventory.items if i.sha256 == sha256), None)
        assert item is not None
        assert item.ref_count == 2
        assert set(item.used_by_packs) == {"Pack1", "Pack2"}


class TestInventorySummary:
    """Test inventory summary statistics."""

    def test_summary_bytes_calculation(self, tmp_path):
        """Summary correctly calculates byte totals."""
        store = Store(tmp_path)
        store.init()

        # Create some blobs
        content1 = b"A" * 1000
        content2 = b"B" * 2000
        content3 = b"C" * 3000

        sha1 = store.blob_store.adopt(_create_temp_file(tmp_path, content1))
        sha2 = store.blob_store.adopt(_create_temp_file(tmp_path, content2))
        sha3 = store.blob_store.adopt(_create_temp_file(tmp_path, content3))

        # Reference only first two
        _create_pack_with_blob(store, "RefPack1", sha1, len(content1))
        _create_pack_with_blob(store, "RefPack2", sha2, len(content2))

        inventory = store.get_inventory()

        assert inventory.summary.bytes_total == 6000  # All blobs
        assert inventory.summary.bytes_referenced == 3000  # sha1 + sha2
        assert inventory.summary.bytes_orphan == 3000  # sha3

    def test_summary_disk_stats(self, tmp_path):
        """Summary includes disk statistics."""
        store = Store(tmp_path)
        store.init()

        summary = store.get_inventory_summary()

        # Should have disk info (if system supports it)
        assert summary.disk_total is None or summary.disk_total > 0


class TestInventoryCleanup:
    """Test cleanup operations."""

    def test_cleanup_dry_run_does_not_delete(self, tmp_path):
        """Dry run doesn't actually delete anything."""
        store = Store(tmp_path)
        store.init()

        # Create orphan blob
        content = b"orphan to be kept"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        result = store.cleanup_orphans(dry_run=True)

        assert result.dry_run is True
        assert result.orphans_found == 1
        assert result.orphans_deleted == 0
        assert store.blob_store.blob_exists(sha256)  # Still exists

    def test_cleanup_execute_deletes_orphans(self, tmp_path):
        """Execute actually deletes orphan blobs."""
        store = Store(tmp_path)
        store.init()

        # Create orphan blob
        content = b"orphan to be deleted"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        result = store.cleanup_orphans(dry_run=False)

        assert result.dry_run is False
        assert result.orphans_deleted == 1
        assert result.bytes_freed == len(content)
        assert not store.blob_store.blob_exists(sha256)  # Deleted

    def test_cleanup_never_deletes_referenced(self, tmp_path):
        """Cleanup NEVER deletes referenced blobs."""
        store = Store(tmp_path)
        store.init()

        # Create referenced blob
        content = b"referenced blob - must not delete"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))
        _create_pack_with_blob(store, "ImportantPack", sha256, len(content))

        # Also create orphan
        orphan_sha = store.blob_store.adopt(
            _create_temp_file(tmp_path, b"orphan")
        )

        result = store.cleanup_orphans(dry_run=False)

        # Should delete orphan only
        assert result.orphans_deleted == 1
        assert store.blob_store.blob_exists(sha256)  # Referenced still exists
        assert not store.blob_store.blob_exists(orphan_sha)  # Orphan deleted

    def test_cleanup_max_items(self, tmp_path):
        """Cleanup respects max_items limit."""
        store = Store(tmp_path)
        store.init()

        # Create 5 orphan blobs
        for i in range(5):
            store.blob_store.adopt(
                _create_temp_file(tmp_path, f"orphan{i}".encode())
            )

        result = store.cleanup_orphans(dry_run=False, max_items=2)

        assert result.orphans_found == 5
        assert result.orphans_deleted == 2


class TestInventoryImpacts:
    """Test impact analysis."""

    def test_impacts_orphan_can_delete(self, tmp_path):
        """Orphan blob can be safely deleted."""
        store = Store(tmp_path)
        store.init()

        content = b"orphan"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        impacts = store.get_blob_impacts(sha256)

        assert impacts.can_delete_safely is True
        assert len(impacts.used_by_packs) == 0
        assert impacts.warning is None

    def test_impacts_referenced_cannot_delete(self, tmp_path):
        """Referenced blob cannot be safely deleted."""
        store = Store(tmp_path)
        store.init()

        content = b"referenced"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))
        _create_pack_with_blob(store, "MyPack", sha256, len(content))

        impacts = store.get_blob_impacts(sha256)

        assert impacts.can_delete_safely is False
        assert "MyPack" in impacts.used_by_packs
        assert impacts.warning is not None

    def test_impacts_nonexistent_blob(self, tmp_path):
        """Non-existent blob returns safe to delete."""
        store = Store(tmp_path)
        store.init()

        impacts = store.get_blob_impacts("nonexistent" * 4)

        assert impacts.can_delete_safely is True


class TestDeleteBlob:
    """Test blob deletion."""

    def test_delete_orphan_succeeds(self, tmp_path):
        """Deleting orphan blob succeeds."""
        store = Store(tmp_path)
        store.init()

        content = b"orphan to delete"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        result = store.delete_blob(sha256)

        assert result["deleted"] is True
        assert result["bytes_freed"] == len(content)
        assert not store.blob_store.blob_exists(sha256)

    def test_delete_referenced_fails_without_force(self, tmp_path):
        """Deleting referenced blob fails without force."""
        store = Store(tmp_path)
        store.init()

        content = b"referenced"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))
        _create_pack_with_blob(store, "Pack", sha256, len(content))

        result = store.delete_blob(sha256, force=False)

        assert result["deleted"] is False
        assert "impacts" in result
        assert store.blob_store.blob_exists(sha256)  # Still exists

    def test_delete_referenced_succeeds_with_force(self, tmp_path):
        """Deleting referenced blob succeeds with force=True."""
        store = Store(tmp_path)
        store.init()

        content = b"referenced but force delete"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))
        _create_pack_with_blob(store, "Pack", sha256, len(content))

        result = store.delete_blob(sha256, force=True)

        assert result["deleted"] is True
        assert not store.blob_store.blob_exists(sha256)

    def test_delete_from_backup_target(self, tmp_path):
        """Deleting blob from backup storage with target='backup'."""
        store = Store(tmp_path)
        store.init()

        # Create a local blob
        content = b"blob to backup and delete from backup"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        # Setup backup storage
        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        from src.store.models import BackupConfig
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        # Backup the blob
        backup_result = store.backup_blob(sha256)
        assert backup_result.success is True

        # Verify blob exists in both locations
        assert store.blob_store.blob_exists(sha256)
        backup_blob_path = store.backup_service.backup_blob_path(sha256)
        assert backup_blob_path.exists()

        # Delete from backup only
        result = store.delete_blob(sha256, target="backup")

        assert result["deleted"] is True
        assert "backup" in result["deleted_from"]
        # Local should still exist
        assert store.blob_store.blob_exists(sha256)
        # Backup should be gone
        assert not backup_blob_path.exists()

    def test_delete_from_both_targets(self, tmp_path):
        """Deleting blob from both local and backup with target='both'."""
        store = Store(tmp_path)
        store.init()

        # Create a local blob
        content = b"blob to delete from both locations"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        # Setup backup storage
        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        from src.store.models import BackupConfig
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        # Backup the blob
        backup_result = store.backup_blob(sha256)
        assert backup_result.success is True

        # Verify blob exists in both locations
        assert store.blob_store.blob_exists(sha256)
        backup_blob_path = store.backup_service.backup_blob_path(sha256)
        assert backup_blob_path.exists()

        # Delete from both
        result = store.delete_blob(sha256, target="both")

        assert result["deleted"] is True
        assert "local" in result["deleted_from"]
        assert "backup" in result["deleted_from"]
        # Both should be gone
        assert not store.blob_store.blob_exists(sha256)
        assert not backup_blob_path.exists()

    def test_delete_backup_only_blob_with_backup_target(self, tmp_path):
        """Deleting blob that exists only in backup (simulates UI 'Delete from Backup')."""
        store = Store(tmp_path)
        store.init()

        # Setup backup storage with a blob that only exists there
        backup_path = tmp_path / "backup"
        backup_path.mkdir()
        from src.store.models import BackupConfig
        config = BackupConfig(enabled=True, path=str(backup_path))
        store.configure_backup(config)

        # Create blob directly in backup (simulating backup-only blob)
        sha256 = "a" * 64
        prefix = sha256[:2]
        blob_dir = backup_path / ".synapse" / "store" / "data" / "blobs" / "sha256" / prefix
        blob_dir.mkdir(parents=True)
        backup_blob_file = blob_dir / sha256
        backup_blob_file.write_bytes(b"backup only content")

        # Verify blob exists only in backup
        assert not store.blob_store.blob_exists(sha256)
        assert backup_blob_file.exists()

        # Delete from backup
        result = store.delete_blob(sha256, target="backup")

        assert result["deleted"] is True
        assert "backup" in result["deleted_from"]
        assert not backup_blob_file.exists()


class TestVerifyBlobs:
    """Test blob verification."""

    def test_verify_valid_blob(self, tmp_path):
        """Valid blob passes verification."""
        store = Store(tmp_path)
        store.init()

        content = b"valid content"
        sha256 = store.blob_store.adopt(_create_temp_file(tmp_path, content))

        result = store.verify_blobs(sha256_list=[sha256])

        assert result["verified"] == 1
        assert sha256 in result["valid"]
        assert sha256 not in result["invalid"]

    def test_verify_all_blobs(self, tmp_path):
        """Verify all blobs in store."""
        store = Store(tmp_path)
        store.init()

        # Create some blobs
        for i in range(3):
            store.blob_store.adopt(
                _create_temp_file(tmp_path, f"blob{i}".encode())
            )

        result = store.verify_blobs(all_blobs=True)

        assert result["verified"] == 3
        assert len(result["valid"]) == 3


class TestInventoryFiltering:
    """Test inventory filtering options."""

    def test_filter_by_kind(self, tmp_path):
        """Filter inventory by asset kind."""
        store = Store(tmp_path)
        store.init()

        # Create blobs with different kinds
        sha1 = store.blob_store.adopt(_create_temp_file(tmp_path, b"lora"))
        sha2 = store.blob_store.adopt(_create_temp_file(tmp_path, b"ckpt"))

        _create_pack_with_blob(store, "LoraPack", sha1, 4, kind=AssetKind.LORA)
        _create_pack_with_blob(store, "CkptPack", sha2, 4, kind=AssetKind.CHECKPOINT)

        inventory = store.get_inventory(kind_filter=AssetKind.LORA)

        # Should only have LORA
        assert all(item.kind == AssetKind.LORA for item in inventory.items)

    def test_filter_by_status(self, tmp_path):
        """Filter inventory by blob status."""
        store = Store(tmp_path)
        store.init()

        # Create referenced and orphan blobs
        sha1 = store.blob_store.adopt(_create_temp_file(tmp_path, b"ref"))
        sha2 = store.blob_store.adopt(_create_temp_file(tmp_path, b"orph"))

        _create_pack_with_blob(store, "Pack", sha1, 3)

        inventory = store.get_inventory(status_filter=BlobStatus.ORPHAN)

        assert all(item.status == BlobStatus.ORPHAN for item in inventory.items)
        assert len(inventory.items) == 1


class TestOrphanManifest:
    """Test orphan blob metadata from manifests."""

    def test_orphan_with_manifest_shows_metadata(self, tmp_path):
        """Orphan blob with manifest shows proper display_name and kind."""
        from src.store.models import BlobManifest, BlobOrigin

        store = Store(tmp_path)
        store.init()

        # Create orphan blob
        blob_content = b"orphan blob with manifest"
        sha256 = store.blob_store.adopt(
            _create_temp_file(tmp_path, blob_content)
        )

        # Create manifest for it
        origin = BlobOrigin(
            provider=ProviderName.CIVITAI,
            model_id=12345,
            version_id=67890,
            filename="original_from_civitai.safetensors",
        )
        manifest = BlobManifest(
            original_filename="my_exposed_model.safetensors",
            kind=AssetKind.LORA,
            origin=origin,
        )
        store.blob_store.write_manifest(sha256, manifest)

        # Get inventory
        inventory = store.get_inventory()

        # Find our orphan
        orphan = next((i for i in inventory.items if i.sha256 == sha256), None)
        assert orphan is not None
        assert orphan.status == BlobStatus.ORPHAN

        # Should have metadata from manifest
        assert orphan.display_name == "my_exposed_model.safetensors"
        assert orphan.kind == AssetKind.LORA
        assert orphan.origin is not None
        assert orphan.origin.provider == ProviderName.CIVITAI
        assert orphan.origin.model_id == 12345

    def test_orphan_without_manifest_shows_sha256(self, tmp_path):
        """Orphan blob without manifest shows SHA256 prefix."""
        store = Store(tmp_path)
        store.init()

        # Create orphan blob without manifest
        blob_content = b"orphan blob without manifest"
        sha256 = store.blob_store.adopt(
            _create_temp_file(tmp_path, blob_content)
        )

        inventory = store.get_inventory()

        orphan = next((i for i in inventory.items if i.sha256 == sha256), None)
        assert orphan is not None
        assert orphan.status == BlobStatus.ORPHAN

        # Should fallback to SHA256 prefix
        assert orphan.display_name == sha256[:12] + "..."
        assert orphan.kind == AssetKind.UNKNOWN
        assert orphan.origin is None


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
    # Create pack
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

    # Create lock
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

    # Save
    store.layout.save_pack(pack)
    store.layout.save_pack_lock(lock)


# =============================================================================
# Manifest Migration Tests
# =============================================================================

class TestManifestMigration:
    """Test manifest migration for existing blobs."""

    def test_migrate_creates_manifest_for_blob_without_one(self, tmp_path):
        """Migration creates manifest for blob that has pack reference but no manifest."""
        store = Store(tmp_path)
        store.init()

        # Create blob without manifest
        blob_content = b"referenced blob content"
        sha256 = store.blob_store.adopt(
            _create_temp_file(tmp_path, blob_content)
        )

        # Verify no manifest exists
        assert not store.blob_store.manifest_exists(sha256)

        # Create pack referencing the blob
        _create_pack_with_blob(store, "TestPack", sha256, len(blob_content))

        # Run migration (dry run first)
        result = store.inventory_service.migrate_manifests(dry_run=True)

        assert result.dry_run is True
        assert result.blobs_scanned == 1
        assert result.manifests_existing == 0
        assert result.manifests_created == 1
        assert result.manifests_skipped == 0
        assert len(result.errors) == 0

        # Verify manifest NOT created in dry run
        assert not store.blob_store.manifest_exists(sha256)

        # Run migration (execute)
        result = store.inventory_service.migrate_manifests(dry_run=False)

        assert result.dry_run is False
        assert result.manifests_created == 1

        # Verify manifest was created
        assert store.blob_store.manifest_exists(sha256)

        manifest = store.blob_store.read_manifest(sha256)
        assert manifest is not None
        assert manifest.kind == AssetKind.CHECKPOINT
        assert "TestPack" in manifest.original_filename

    def test_migrate_skips_existing_manifests(self, tmp_path):
        """Migration does not overwrite existing manifests."""
        store = Store(tmp_path)
        store.init()

        # Create blob
        blob_content = b"blob with existing manifest"
        sha256 = store.blob_store.adopt(
            _create_temp_file(tmp_path, blob_content)
        )

        # Create manifest manually
        original_manifest = BlobManifest(
            original_filename="original_name.safetensors",
            kind=AssetKind.LORA,
        )
        store.blob_store.write_manifest(sha256, original_manifest)

        # Create pack referencing the blob with different data
        _create_pack_with_blob(
            store, "DifferentPack", sha256, len(blob_content), kind=AssetKind.CHECKPOINT
        )

        # Run migration
        result = store.inventory_service.migrate_manifests(dry_run=False)

        assert result.manifests_existing == 1
        assert result.manifests_created == 0

        # Verify manifest unchanged
        manifest = store.blob_store.read_manifest(sha256)
        assert manifest.original_filename == "original_name.safetensors"
        assert manifest.kind == AssetKind.LORA

    def test_migrate_skips_orphan_blobs(self, tmp_path):
        """Migration skips blobs without pack references."""
        store = Store(tmp_path)
        store.init()

        # Create orphan blob (no pack reference)
        blob_content = b"orphan blob"
        sha256 = store.blob_store.adopt(
            _create_temp_file(tmp_path, blob_content)
        )

        # Run migration
        result = store.inventory_service.migrate_manifests(dry_run=False)

        assert result.blobs_scanned == 1
        assert result.manifests_skipped == 1
        assert result.manifests_created == 0

        # Verify no manifest created
        assert not store.blob_store.manifest_exists(sha256)

    def test_migrate_uses_expose_filename_when_available(self, tmp_path):
        """Migration uses expose filename from pack dependency."""
        store = Store(tmp_path)
        store.init()

        # Create blob
        blob_content = b"blob with expose filename"
        sha256 = store.blob_store.adopt(
            _create_temp_file(tmp_path, blob_content)
        )

        # Create pack with specific expose filename
        _create_pack_with_blob(store, "TestPack", sha256, len(blob_content))

        # Run migration
        result = store.inventory_service.migrate_manifests(dry_run=False)

        manifest = store.blob_store.read_manifest(sha256)
        assert manifest is not None
        assert manifest.original_filename == "TestPack_model.safetensors"

    def test_migrate_empty_store(self, tmp_path):
        """Migration on empty store succeeds with zero counts."""
        store = Store(tmp_path)
        store.init()

        result = store.inventory_service.migrate_manifests(dry_run=False)

        assert result.blobs_scanned == 0
        assert result.manifests_existing == 0
        assert result.manifests_created == 0
        assert result.manifests_skipped == 0
        assert len(result.errors) == 0

    def test_migrate_idempotent(self, tmp_path):
        """Running migration multiple times is safe and idempotent."""
        store = Store(tmp_path)
        store.init()

        # Create blob and pack
        blob_content = b"idempotent test blob"
        sha256 = store.blob_store.adopt(
            _create_temp_file(tmp_path, blob_content)
        )
        _create_pack_with_blob(store, "TestPack", sha256, len(blob_content))

        # Run migration twice
        result1 = store.inventory_service.migrate_manifests(dry_run=False)
        result2 = store.inventory_service.migrate_manifests(dry_run=False)

        # First run creates manifest
        assert result1.manifests_created == 1
        assert result1.manifests_existing == 0

        # Second run finds existing manifest
        assert result2.manifests_created == 0
        assert result2.manifests_existing == 1

        # Manifest still exists and is unchanged
        manifest = store.blob_store.read_manifest(sha256)
        assert manifest is not None
