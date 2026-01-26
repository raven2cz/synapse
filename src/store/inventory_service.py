"""
Synapse Store v2 - Inventory Service

Provides comprehensive blob inventory with:
- Reference tracking (which packs use which blobs)
- Orphan detection
- Missing blob detection
- Safe cleanup operations
- Location tracking (local vs backup)
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from .blob_store import BlobStore
from .layout import StoreLayout

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .backup_service import BackupService
from .models import (
    AssetKind,
    BackupStats,
    BlobLocation,
    BlobOrigin,
    BlobStatus,
    CleanupResult,
    ImpactAnalysis,
    InventoryItem,
    InventoryResponse,
    InventorySummary,
    PackReference,
    ProviderName,
)


class InventoryService:
    """
    Service for blob inventory management.

    Provides:
    - Complete inventory of all blobs with status tracking
    - Reference map (blob -> packs using it)
    - Orphan detection (blobs not referenced by any pack)
    - Missing blob detection (referenced but not present)
    - Safe cleanup operations with guard rails
    - Backup location detection
    """

    def __init__(
        self,
        layout: StoreLayout,
        blob_store: BlobStore,
        backup_service: Optional["BackupService"] = None,
    ):
        """
        Initialize inventory service.

        Args:
            layout: Store layout manager
            blob_store: Blob store instance
            backup_service: Optional backup service for location detection
        """
        self.layout = layout
        self.blob_store = blob_store
        self.backup_service = backup_service

    def set_backup_service(self, backup_service: "BackupService") -> None:
        """Set or update the backup service reference."""
        self.backup_service = backup_service

    def build_inventory(
        self,
        kind_filter: Optional[AssetKind] = None,
        status_filter: Optional[BlobStatus] = None,
        include_verification: bool = False,
    ) -> InventoryResponse:
        """
        Build complete inventory by cross-referencing blobs and pack locks.

        Algorithm:
        1. List all physical blobs (local and backup)
        2. Scan all pack locks for references
        3. Cross-reference to determine status
        4. Optionally verify hashes

        Args:
            kind_filter: Filter by asset kind
            status_filter: Filter by blob status
            include_verification: If True, verify blob hashes (slow!)

        Returns:
            Complete inventory response with summary and items
        """
        # NOTE: No routine logging - this is called frequently for UI refresh
        # Only log errors

        # Step 1: Get all physical blobs (local)
        try:
            local_blobs = set(self.blob_store.list_blobs())
        except Exception as e:
            logger.error("[Inventory] Failed to list local blobs: %s", e, exc_info=True)
            raise

        # Step 1b: Get backup blobs if backup service is available
        backup_blobs: Set[str] = set()
        if self.backup_service and self.backup_service.is_connected():
            try:
                backup_blobs = set(self.backup_service.list_backup_blobs())
            except Exception as e:
                logger.warning("[Inventory] Failed to list backup blobs: %s", e)

        # All physical blobs (union of local and backup)
        all_physical_blobs = local_blobs | backup_blobs

        # Step 2: Build reference map from all pack locks
        ref_map = self._build_reference_map()

        # Step 3: Determine referenced blobs
        referenced_blobs = set(ref_map.keys())

        # Step 4: Calculate sets
        # Blobs that exist locally and are referenced
        local_referenced = local_blobs & referenced_blobs
        # Blobs that exist locally but not referenced (orphan)
        orphan_blobs = local_blobs - referenced_blobs
        # Blobs only on backup but referenced (backup_only referenced)
        backup_only_referenced = (backup_blobs - local_blobs) & referenced_blobs
        # Blobs only on backup and not referenced (backup_only orphan)
        backup_only_orphan = (backup_blobs - local_blobs) - referenced_blobs
        # Blobs referenced but don't exist anywhere (truly missing)
        missing_blobs = referenced_blobs - all_physical_blobs

        # Step 5: Build items
        items: List[InventoryItem] = []

        # Referenced blobs (exist locally and are referenced)
        for sha256 in local_referenced:
            on_backup = sha256 in backup_blobs
            item = self._build_item(
                sha256=sha256,
                status=BlobStatus.REFERENCED,
                refs=ref_map[sha256],
                verify=include_verification,
                on_local=True,
                on_backup=on_backup,
            )
            items.append(item)

        # Orphan blobs (exist locally but not referenced)
        for sha256 in orphan_blobs:
            on_backup = sha256 in backup_blobs
            item = self._build_item(
                sha256=sha256,
                status=BlobStatus.ORPHAN,
                refs=[],
                verify=include_verification,
                on_local=True,
                on_backup=on_backup,
            )
            items.append(item)

        # Backup-only referenced blobs (on backup but not local, and referenced)
        for sha256 in backup_only_referenced:
            item = self._build_item(
                sha256=sha256,
                status=BlobStatus.BACKUP_ONLY,
                refs=ref_map[sha256],
                verify=False,  # Can't verify without local copy
                on_local=False,
                on_backup=True,
            )
            items.append(item)

        # Backup-only orphan blobs (on backup but not local, not referenced)
        for sha256 in backup_only_orphan:
            item = self._build_item(
                sha256=sha256,
                status=BlobStatus.ORPHAN,  # Still orphan, just on backup
                refs=[],
                verify=False,
                on_local=False,
                on_backup=True,
            )
            items.append(item)

        # Missing blobs (referenced but don't exist anywhere)
        for sha256 in missing_blobs:
            item = self._build_item(
                sha256=sha256,
                status=BlobStatus.MISSING,
                refs=ref_map[sha256],
                verify=False,  # Can't verify what doesn't exist
                on_local=False,
                on_backup=False,
            )
            items.append(item)

        # Step 6: Apply filters
        if kind_filter:
            items = [i for i in items if i.kind == kind_filter]
        if status_filter:
            items = [i for i in items if i.status == status_filter]

        # Step 7: Build summary
        summary = self._build_summary(items)

        return InventoryResponse(
            generated_at=datetime.now().isoformat(),
            summary=summary,
            items=items,
        )

    def _build_reference_map(self) -> Dict[str, List[PackReference]]:
        """
        Scan all pack locks and build sha256 -> [references] map.

        Returns:
            Dict mapping SHA256 hashes to list of pack references
        """
        # NOTE: No routine logging - this is called frequently for UI refresh
        ref_map: Dict[str, List[PackReference]] = {}
        packs = self.layout.list_packs()

        for pack_name in packs:
            try:
                lock = self.layout.load_pack_lock(pack_name)
                pack = self.layout.load_pack(pack_name)

                for resolved in lock.resolved:
                    sha256 = resolved.artifact.sha256
                    if not sha256:
                        continue

                    sha256 = sha256.lower()
                    if sha256 not in ref_map:
                        ref_map[sha256] = []

                    # Get expose filename from pack dependency
                    expose_filename = None
                    kind = resolved.artifact.kind
                    for dep in pack.dependencies:
                        if dep.id == resolved.dependency_id:
                            expose_filename = dep.expose.filename
                            kind = dep.kind
                            break

                    # Build origin from artifact provider
                    origin = None
                    if resolved.artifact.provider:
                        prov = resolved.artifact.provider
                        origin = BlobOrigin(
                            provider=prov.name,
                            model_id=prov.model_id,
                            version_id=prov.version_id,
                            file_id=prov.file_id,
                            filename=prov.filename,
                            repo_id=prov.repo_id,
                        )

                    ref_map[sha256].append(PackReference(
                        pack_name=pack_name,
                        dependency_id=resolved.dependency_id,
                        kind=kind,
                        expose_filename=expose_filename,
                        size_bytes=resolved.artifact.size_bytes,
                        origin=origin,
                    ))
            except Exception as e:
                logger.warning("[Inventory] Error processing pack '%s': %s", pack_name, e)
                continue  # Skip packs with missing/invalid locks

        return ref_map

    def _build_item(
        self,
        sha256: str,
        status: BlobStatus,
        refs: List[PackReference],
        verify: bool = False,
        on_local: bool = True,
        on_backup: bool = False,
    ) -> InventoryItem:
        """
        Build an inventory item from blob hash and references.

        Args:
            sha256: Blob SHA256 hash
            status: Blob status
            refs: List of pack references to this blob
            verify: If True, verify blob hash
            on_local: Whether blob exists locally
            on_backup: Whether blob exists on backup

        Returns:
            Populated InventoryItem
        """
        # Determine size
        size_bytes = 0
        if on_local:
            size = self.blob_store.blob_size(sha256)
            if size is not None:
                size_bytes = size
        elif on_backup and self.backup_service:
            # Try to get size from backup
            size = self.backup_service.get_backup_blob_size(sha256)
            if size is not None:
                size_bytes = size

        # If still no size, try to get from reference
        if size_bytes == 0 and refs:
            for ref in refs:
                if ref.size_bytes:
                    size_bytes = ref.size_bytes
                    break

        # Determine display name (priority: expose > origin filename > manifest > sha256)
        display_name = sha256[:12] + "..."
        kind = AssetKind.UNKNOWN
        origin = None

        if refs:
            # Use first reference for display info
            first_ref = refs[0]
            kind = first_ref.kind
            origin = first_ref.origin

            if first_ref.expose_filename:
                display_name = first_ref.expose_filename
            elif first_ref.origin and first_ref.origin.filename:
                display_name = first_ref.origin.filename
        else:
            # No pack references - try to read manifest for orphan blobs
            manifest = self.blob_store.read_manifest(sha256)
            if manifest:
                display_name = manifest.original_filename
                kind = manifest.kind
                origin = manifest.origin

        # Get unique pack names
        used_by_packs = list(set(ref.pack_name for ref in refs))

        # Determine location from provided flags
        if on_local and on_backup:
            location = BlobLocation.BOTH
        elif on_local:
            location = BlobLocation.LOCAL_ONLY
        elif on_backup:
            location = BlobLocation.BACKUP_ONLY
        else:
            location = BlobLocation.NOWHERE

        # Verification
        verified = None
        if verify and on_local:
            verified = self.blob_store.verify(sha256)

        return InventoryItem(
            sha256=sha256,
            kind=kind,
            display_name=display_name,
            size_bytes=size_bytes,
            location=location,
            on_local=on_local,
            on_backup=on_backup,
            status=status,
            used_by_packs=used_by_packs,
            ref_count=len(refs),
            origin=origin,
            active_in_uis=[],  # TODO: Get from runtime
            verified=verified,
        )

    def _build_summary(self, items: List[InventoryItem]) -> InventorySummary:
        """
        Build summary statistics from inventory items.

        Args:
            items: List of inventory items

        Returns:
            Summary statistics
        """
        summary = InventorySummary()

        bytes_by_kind: Dict[str, int] = {}

        # Backup statistics
        blobs_local_only = 0
        blobs_backup_only = 0
        blobs_both = 0
        bytes_local_only = 0
        bytes_backup_only = 0
        bytes_synced = 0

        for item in items:
            summary.blobs_total += 1

            if item.status == BlobStatus.REFERENCED:
                summary.blobs_referenced += 1
                summary.bytes_referenced += item.size_bytes
            elif item.status == BlobStatus.ORPHAN:
                summary.blobs_orphan += 1
                summary.bytes_orphan += item.size_bytes
            elif item.status == BlobStatus.MISSING:
                summary.blobs_missing += 1
            elif item.status == BlobStatus.BACKUP_ONLY:
                summary.blobs_backup_only += 1

            # Only count size for items that exist locally
            if item.on_local:
                summary.bytes_total += item.size_bytes

            # Backup location statistics
            if item.on_local and item.on_backup:
                blobs_both += 1
                bytes_synced += item.size_bytes
            elif item.on_local and not item.on_backup:
                blobs_local_only += 1
                bytes_local_only += item.size_bytes
            elif not item.on_local and item.on_backup:
                blobs_backup_only += 1
                bytes_backup_only += item.size_bytes

            # Bytes by kind
            kind_key = item.kind.value
            if kind_key not in bytes_by_kind:
                bytes_by_kind[kind_key] = 0
            bytes_by_kind[kind_key] += item.size_bytes

        summary.bytes_by_kind = bytes_by_kind

        # Try to get disk stats
        try:
            import shutil
            root = self.layout.root
            usage = shutil.disk_usage(root)
            summary.disk_total = usage.total
            summary.disk_free = usage.free
        except Exception:
            pass

        # Add backup statistics if backup service is available
        if self.backup_service:
            backup_status = self.backup_service.get_status()
            summary.backup = BackupStats(
                enabled=backup_status.enabled,
                connected=backup_status.connected,
                path=backup_status.path,
                blobs_local_only=blobs_local_only,
                blobs_backup_only=blobs_backup_only,
                blobs_both=blobs_both,
                bytes_local_only=bytes_local_only,
                bytes_backup_only=bytes_backup_only,
                bytes_synced=bytes_synced,
                free_space=backup_status.free_space,
                total_space=backup_status.total_space,
                last_sync=backup_status.last_sync,
                error=backup_status.error,
            )

        return summary

    def cleanup_orphans(self, dry_run: bool = True, max_items: int = 0) -> CleanupResult:
        """
        Remove orphan blobs safely.

        NEVER removes referenced blobs.

        Args:
            dry_run: If True, don't actually delete anything
            max_items: Maximum number of items to delete (0 = unlimited)

        Returns:
            Cleanup result with details
        """
        logger.info(
            "[Inventory] Starting cleanup_orphans (dry_run=%s, max_items=%d)",
            dry_run,
            max_items,
        )

        try:
            inventory = self.build_inventory(status_filter=BlobStatus.ORPHAN)
            logger.info("[Inventory] Found %d orphan blobs", len(inventory.items))
        except Exception as e:
            logger.error("[Inventory] Failed to build inventory for cleanup: %s", e, exc_info=True)
            raise

        items_to_delete = inventory.items
        if max_items > 0:
            items_to_delete = items_to_delete[:max_items]
            logger.debug("[Inventory] Limited to %d items (max_items=%d)", len(items_to_delete), max_items)

        result = CleanupResult(
            dry_run=dry_run,
            orphans_found=len(inventory.items),
            orphans_deleted=0,
            bytes_freed=0,
            deleted=[],
        )

        if dry_run:
            result.deleted = items_to_delete
            result.bytes_freed = sum(i.size_bytes for i in items_to_delete)
            logger.info(
                "[Inventory] Dry run complete: would delete %d blobs (%.2f MB)",
                len(items_to_delete),
                result.bytes_freed / 1024 / 1024,
            )
            return result

        # Actually delete
        logger.info("[Inventory] Starting deletion of %d orphan blobs", len(items_to_delete))
        for i, item in enumerate(items_to_delete):
            try:
                logger.debug(
                    "[Inventory] Deleting blob %d/%d: %s (%s)",
                    i + 1,
                    len(items_to_delete),
                    item.sha256[:12],
                    item.display_name,
                )
                if self.blob_store.remove_blob(item.sha256):
                    result.orphans_deleted += 1
                    result.bytes_freed += item.size_bytes
                    result.deleted.append(item)
                    logger.debug("[Inventory] Successfully deleted %s", item.sha256[:12])
                else:
                    logger.warning("[Inventory] remove_blob returned False for %s", item.sha256[:12])
            except Exception as e:
                error_msg = f"{item.sha256}: {str(e)}"
                result.errors.append(error_msg)
                logger.error("[Inventory] Failed to delete %s: %s", item.sha256[:12], e, exc_info=True)

        if result.errors:
            logger.warning("[Inventory] Cleanup completed with %d errors", len(result.errors))
        else:
            logger.info(
                "[Inventory] Cleanup complete: deleted %d blobs, freed %.2f MB",
                result.orphans_deleted,
                result.bytes_freed / 1024 / 1024,
            )

        return result

    def get_impacts(self, sha256: str) -> ImpactAnalysis:
        """
        Analyze what would break if a blob is deleted.

        Args:
            sha256: SHA256 hash of blob to analyze

        Returns:
            Impact analysis
        """
        logger.debug("[Inventory] Analyzing impacts for blob %s", sha256[:12] if len(sha256) >= 12 else sha256)

        try:
            inventory = self.build_inventory()
        except Exception as e:
            logger.error("[Inventory] Failed to build inventory for impacts: %s", e, exc_info=True)
            raise

        item = next((i for i in inventory.items if i.sha256 == sha256.lower()), None)

        if not item:
            logger.debug("[Inventory] Blob %s not found in inventory", sha256[:12])
            return ImpactAnalysis(
                sha256=sha256,
                display_name=sha256[:12] + "...",
                kind=None,
                status=BlobStatus.MISSING,
                size_bytes=0,
                used_by_packs=[],
                active_in_uis=[],
                can_delete_safely=True,
                warning="Blob does not exist",
            )

        can_delete = item.status == BlobStatus.ORPHAN
        warning = None

        if item.status == BlobStatus.REFERENCED:
            pack_count = len(item.used_by_packs)
            warning = (
                f"This blob is used by {pack_count} pack(s). "
                f"Deleting will cause MISSING status."
            )
            logger.debug(
                "[Inventory] Blob %s is REFERENCED by %d packs: %s",
                sha256[:12],
                pack_count,
                item.used_by_packs,
            )
        else:
            logger.debug("[Inventory] Blob %s is %s, can_delete=%s", sha256[:12], item.status, can_delete)

        return ImpactAnalysis(
            sha256=sha256,
            display_name=item.display_name,
            kind=item.kind,
            status=item.status,
            size_bytes=item.size_bytes,
            used_by_packs=item.used_by_packs,
            active_in_uis=item.active_in_uis,
            can_delete_safely=can_delete,
            warning=warning,
        )

    def delete_blob(
        self,
        sha256: str,
        force: bool = False,
        target: str = "local",
    ) -> Dict:
        """
        Delete a blob with safety checks.

        Args:
            sha256: SHA256 hash of blob to delete
            force: If True, delete even if referenced
            target: Where to delete from: "local", "backup", or "both"

        Returns:
            Dict with deletion result
        """
        logger.info(
            "[Inventory] delete_blob called (sha256=%s, force=%s, target=%s)",
            sha256[:12] if len(sha256) >= 12 else sha256,
            force,
            target,
        )

        try:
            impacts = self.get_impacts(sha256)
        except Exception as e:
            logger.error("[Inventory] Failed to get impacts for delete: %s", e, exc_info=True)
            raise

        if not impacts.can_delete_safely and not force:
            logger.info(
                "[Inventory] Refusing to delete %s: blob is referenced by %d packs",
                sha256[:12],
                len(impacts.used_by_packs),
            )
            return {
                "deleted": False,
                "sha256": sha256,
                "reason": "Blob is referenced by packs",
                "impacts": impacts,
            }

        deleted_from = []
        bytes_freed = 0

        # Delete from local if requested
        if target in ("local", "both"):
            try:
                if self.blob_store.blob_exists(sha256):
                    removed = self.blob_store.remove_blob(sha256)
                    if removed:
                        logger.info(
                            "[Inventory] Deleted blob %s from local (%.2f MB)",
                            sha256[:12],
                            impacts.size_bytes / 1024 / 1024,
                        )
                        deleted_from.append("local")
                        bytes_freed += impacts.size_bytes
                    else:
                        logger.warning("[Inventory] remove_blob returned False for %s", sha256[:12])
                else:
                    logger.debug("[Inventory] Blob %s not on local, skipping local delete", sha256[:12])
            except Exception as e:
                logger.error("[Inventory] Failed to remove blob %s from local: %s", sha256[:12], e, exc_info=True)
                raise

        # Delete from backup if requested
        if target in ("backup", "both"):
            try:
                if self.backup_service and self.backup_service.is_connected():
                    backup_path = self.backup_service.backup_blob_path(sha256)
                    if backup_path and backup_path.exists():
                        result = self.backup_service.delete_from_backup(sha256, confirm=True)
                        if result.success:
                            logger.info(
                                "[Inventory] Deleted blob %s from backup (%.2f MB)",
                                sha256[:12],
                                impacts.size_bytes / 1024 / 1024,
                            )
                            deleted_from.append("backup")
                            if "local" not in deleted_from:
                                bytes_freed += impacts.size_bytes
                        else:
                            logger.error("[Inventory] Failed to delete from backup: %s", result.error)
                            raise RuntimeError(f"Backup delete failed: {result.error}")
                    else:
                        logger.debug("[Inventory] Blob %s not on backup, skipping backup delete", sha256[:12])
                else:
                    if target == "backup":
                        raise RuntimeError("Backup storage not connected")
                    logger.warning("[Inventory] Backup not connected, skipping backup delete for target=%s", target)
            except RuntimeError:
                raise
            except Exception as e:
                logger.error("[Inventory] Failed to delete blob %s from backup: %s", sha256[:12], e, exc_info=True)
                raise

        # Determine where blob remains
        remaining_on = []
        if self.blob_store.blob_exists(sha256):
            remaining_on.append("local")
        if self.backup_service and self.backup_service.is_connected():
            backup_path = self.backup_service.backup_blob_path(sha256)
            if backup_path and backup_path.exists():
                remaining_on.append("backup")

        deleted = len(deleted_from) > 0
        if not deleted and target in ("backup", "both"):
            # Nothing was deleted - this is an error if we targeted backup
            return {
                "deleted": False,
                "sha256": sha256,
                "reason": "Blob not found in target location(s)",
                "deleted_from": [],
                "remaining_on": remaining_on,
            }

        return {
            "deleted": deleted,
            "sha256": sha256,
            "bytes_freed": bytes_freed,
            "deleted_from": deleted_from,
            "remaining_on": "nowhere" if not remaining_on else remaining_on,
        }

    def verify_blobs(
        self,
        sha256_list: Optional[List[str]] = None,
        all_blobs: bool = False,
    ) -> Dict:
        """
        Verify blob integrity.

        Args:
            sha256_list: Specific blobs to verify
            all_blobs: If True, verify all blobs

        Returns:
            Verification result
        """
        import time

        logger.info(
            "[Inventory] Starting blob verification (all_blobs=%s, specific=%d)",
            all_blobs,
            len(sha256_list or []),
        )
        start = time.time()

        try:
            if all_blobs:
                valid, invalid = self.blob_store.verify_all()
            else:
                valid = []
                invalid = []
                for h in (sha256_list or []):
                    if self.blob_store.verify(h):
                        valid.append(h)
                    else:
                        invalid.append(h)
                        logger.warning("[Inventory] Blob verification failed: %s", h[:12])
        except Exception as e:
            logger.error("[Inventory] Blob verification failed: %s", e, exc_info=True)
            raise

        duration_ms = int((time.time() - start) * 1000)

        if invalid:
            logger.warning(
                "[Inventory] Verification complete: %d valid, %d INVALID in %dms",
                len(valid),
                len(invalid),
                duration_ms,
            )
        else:
            logger.info(
                "[Inventory] Verification complete: %d valid, 0 invalid in %dms",
                len(valid),
                duration_ms,
            )

        return {
            "verified": len(valid) + len(invalid),
            "valid": valid,
            "invalid": invalid,
            "duration_ms": duration_ms,
        }
