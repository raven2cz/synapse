"""
Synapse Store v2 - Backup Storage Service

Provides backup storage operations:
- Status checking (is backup connected?)
- Backup blob (local -> backup)
- Restore blob (backup -> local)
- Delete from backup
- Sync operations (bulk backup/restore)
- Verification

Backup storage mirrors the local blob structure:
<backup_path>/.synapse/store/data/blobs/sha256/<prefix>/<hash>
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from .blob_store import compute_sha256
from .layout import StoreLayout

logger = logging.getLogger(__name__)
from .models import (
    BackupConfig,
    BackupDeleteResult,
    BackupOperationResult,
    BackupStatus,
    StateSyncItem,
    StateSyncResult,
    StateSyncStatus,
    StateSyncSummary,
    SyncItem,
    SyncResult,
)


class BackupError(Exception):
    """Base exception for backup errors."""
    pass


class BackupNotEnabledError(BackupError):
    """Backup is not enabled in config."""
    pass


class BackupNotConnectedError(BackupError):
    """Backup storage is not accessible."""
    pass


class BlobNotFoundError(BackupError):
    """Blob not found in the specified location."""
    pass


class InsufficientSpaceError(BackupError):
    """Not enough space for the operation."""
    pass


# Progress callback: (bytes_copied, total_bytes)
ProgressCallback = Callable[[int, int], None]


class BackupService:
    """
    Service for backup storage operations.

    Provides:
    - Status checking for backup connectivity
    - Backup/restore blob operations
    - Sync operations for bulk transfers
    - Verification of backup integrity
    - Guard rails for safe operations
    """

    CHUNK_SIZE = 1024 * 1024  # 1MB chunks for copying

    def __init__(self, layout: StoreLayout, config: BackupConfig):
        """
        Initialize backup service.

        Args:
            layout: Store layout manager
            config: Backup configuration
        """
        self.layout = layout
        self.config = config
        self._last_sync: Optional[str] = None

    # =========================================================================
    # Configuration
    # =========================================================================

    def update_config(self, config: BackupConfig) -> None:
        """Update backup configuration."""
        self.config = config

    @property
    def backup_root(self) -> Optional[Path]:
        """Get the backup storage root path."""
        if not self.config.path:
            return None
        return Path(self.config.path)

    @property
    def backup_blobs_path(self) -> Optional[Path]:
        """Get the backup blobs directory path."""
        root = self.backup_root
        if not root:
            return None
        return root / ".synapse" / "store" / "data" / "blobs" / "sha256"

    def backup_blob_path(self, sha256: str) -> Optional[Path]:
        """Get path to a specific blob in backup storage."""
        blobs_path = self.backup_blobs_path
        if not blobs_path:
            return None
        sha256_lower = sha256.lower()
        return blobs_path / sha256_lower[:2] / sha256_lower

    @property
    def backup_state_path(self) -> Optional[Path]:
        """Get the backup state directory path (mirrors state/)."""
        root = self.backup_root
        if not root:
            return None
        return root / ".synapse" / "store" / "state"

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> BackupStatus:
        """
        Get backup storage status.

        Returns:
            BackupStatus with connection info and statistics
        """
        # NOTE: No debug logging here - called frequently for polling

        if not self.config.enabled:
            return BackupStatus(
                enabled=False,
                connected=False,
                path=self.config.path,
                auto_backup_new=self.config.auto_backup_new,
                warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
            )

        if not self.config.path:
            # Log only once when path is missing (error condition)
            return BackupStatus(
                enabled=True,
                connected=False,
                path=None,
                error="Backup path not configured",
                auto_backup_new=self.config.auto_backup_new,
                warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
            )

        backup_path = self.backup_root
        if not backup_path or not backup_path.exists():
            # Path not accessible - don't log (called frequently)
            return BackupStatus(
                enabled=True,
                connected=False,
                path=self.config.path,
                error="Backup path not accessible",
                auto_backup_new=self.config.auto_backup_new,
                warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
            )

        # Check if we can write to the backup
        blobs_path = self.backup_blobs_path
        try:
            if blobs_path:
                blobs_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            logger.error("[Backup] No write permission to backup path: %s", self.config.path)
            return BackupStatus(
                enabled=True,
                connected=False,
                path=self.config.path,
                error="No write permission to backup path",
                auto_backup_new=self.config.auto_backup_new,
                warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
            )
        except Exception as e:
            logger.error("[Backup] Error accessing backup path: %s", e, exc_info=True)
            return BackupStatus(
                enabled=True,
                connected=False,
                path=self.config.path,
                error=str(e),
                auto_backup_new=self.config.auto_backup_new,
                warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
            )

        # Count blobs and calculate size
        total_blobs = 0
        total_bytes = 0
        if blobs_path and blobs_path.exists():
            for prefix_dir in blobs_path.iterdir():
                if not prefix_dir.is_dir():
                    continue
                for blob_file in prefix_dir.iterdir():
                    if blob_file.is_file():
                        total_blobs += 1
                        total_bytes += blob_file.stat().st_size

        # Get disk space
        free_space = None
        total_space = None
        try:
            usage = shutil.disk_usage(backup_path)
            free_space = usage.free
            total_space = usage.total
        except Exception:
            pass

        return BackupStatus(
            enabled=True,
            connected=True,
            path=self.config.path,
            total_blobs=total_blobs,
            total_bytes=total_bytes,
            total_space=total_space,
            free_space=free_space,
            last_sync=self._last_sync,
            auto_backup_new=self.config.auto_backup_new,
            warn_before_delete_last_copy=self.config.warn_before_delete_last_copy,
        )

    def is_enabled(self) -> bool:
        """Quick check if backup is enabled in config."""
        return self.config.enabled

    def is_connected(self) -> bool:
        """Quick check if backup is connected."""
        status = self.get_status()
        return status.enabled and status.connected

    def _require_connected(self) -> None:
        """Raise if backup is not connected."""
        if not self.config.enabled:
            logger.warning("[Backup] Operation failed: backup not enabled")
            raise BackupNotEnabledError("Backup storage is not enabled")
        if not self.is_connected():
            logger.warning("[Backup] Operation failed: backup not accessible")
            raise BackupNotConnectedError("Backup storage is not accessible")

    # =========================================================================
    # Blob Location Checks
    # =========================================================================

    def blob_exists_on_backup(self, sha256: str) -> bool:
        """Check if blob exists on backup storage."""
        if not self.config.enabled:
            return False
        blob_path = self.backup_blob_path(sha256)
        return blob_path is not None and blob_path.exists()

    def list_backup_blobs(self) -> List[str]:
        """List all blob hashes on backup storage."""
        blobs = []
        blobs_path = self.backup_blobs_path
        if not blobs_path or not blobs_path.exists():
            return blobs

        for prefix_dir in blobs_path.iterdir():
            if not prefix_dir.is_dir():
                continue
            for blob_file in prefix_dir.iterdir():
                if blob_file.is_file():
                    blobs.append(blob_file.name)

        return blobs

    def get_backup_blob_size(self, sha256: str) -> Optional[int]:
        """Get size of a blob on backup storage."""
        blob_path = self.backup_blob_path(sha256)
        if blob_path and blob_path.exists():
            return blob_path.stat().st_size
        return None

    # =========================================================================
    # Backup Operations
    # =========================================================================

    def backup_blob(
        self,
        sha256: str,
        verify_after: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BackupOperationResult:
        """
        Backup a blob from local to backup storage.

        Args:
            sha256: SHA256 hash of the blob
            verify_after: If True, verify the copy after backup
            progress_callback: Optional progress callback

        Returns:
            BackupOperationResult with operation details
        """
        start_time = time.time()
        sha256_lower = sha256.lower()
        logger.info("[Backup] Starting backup of blob %s", sha256_lower[:12])

        try:
            self._require_connected()

            # Check if already on backup
            if self.blob_exists_on_backup(sha256_lower):
                logger.debug("[Backup] Blob %s already exists on backup", sha256_lower[:12])
                return BackupOperationResult(
                    success=True,
                    sha256=sha256_lower,
                    bytes_copied=0,
                    duration_ms=0,
                    verified=True,
                )

            # Get local blob path
            local_path = self.layout.blob_path(sha256_lower)
            if not local_path.exists():
                logger.error("[Backup] Blob %s not found locally", sha256_lower[:12])
                raise BlobNotFoundError(f"Blob {sha256_lower} not found locally")

            blob_size = local_path.stat().st_size
            logger.debug("[Backup] Blob %s size: %.2f MB", sha256_lower[:12], blob_size / 1024 / 1024)

            # Check free space on backup
            status = self.get_status()
            if status.free_space is not None and status.free_space < blob_size:
                logger.error(
                    "[Backup] Insufficient space: need %.2f MB, have %.2f MB",
                    blob_size / 1024 / 1024,
                    status.free_space / 1024 / 1024,
                )
                raise InsufficientSpaceError(
                    f"Not enough space on backup: need {blob_size}, have {status.free_space}"
                )

            # Get backup path and create parent dirs
            backup_path = self.backup_blob_path(sha256_lower)
            if not backup_path:
                logger.error("[Backup] Cannot determine backup path")
                raise BackupError("Cannot determine backup path")
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy with progress
            logger.debug("[Backup] Copying to %s", backup_path)
            bytes_copied = self._copy_file(
                local_path, backup_path, progress_callback
            )

            # Verify if requested
            verified = None
            if verify_after:
                logger.debug("[Backup] Verifying backup copy")
                actual_hash = compute_sha256(backup_path)
                verified = actual_hash == sha256_lower
                if not verified:
                    backup_path.unlink(missing_ok=True)
                    logger.error(
                        "[Backup] Verification failed: expected %s, got %s",
                        sha256_lower[:12],
                        actual_hash[:12],
                    )
                    raise BackupError(
                        f"Verification failed: expected {sha256_lower}, got {actual_hash}"
                    )

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "[Backup] Successfully backed up %s (%.2f MB in %dms)",
                sha256_lower[:12],
                bytes_copied / 1024 / 1024,
                duration_ms,
            )

            return BackupOperationResult(
                success=True,
                sha256=sha256_lower,
                bytes_copied=bytes_copied,
                duration_ms=duration_ms,
                verified=verified,
            )

        except (BackupNotEnabledError, BackupNotConnectedError, BlobNotFoundError,
                InsufficientSpaceError, BackupError) as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("[Backup] Backup failed for %s: %s", sha256_lower[:12], e)
            return BackupOperationResult(
                success=False,
                sha256=sha256_lower,
                duration_ms=duration_ms,
                error=str(e),
            )

    def restore_blob(
        self,
        sha256: str,
        verify_after: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BackupOperationResult:
        """
        Restore a blob from backup to local storage.

        Args:
            sha256: SHA256 hash of the blob
            verify_after: If True, verify the copy after restore
            progress_callback: Optional progress callback

        Returns:
            BackupOperationResult with operation details
        """
        start_time = time.time()
        sha256_lower = sha256.lower()
        logger.info("[Backup] Starting restore of blob %s", sha256_lower[:12])

        try:
            self._require_connected()

            # Check if already local
            local_path = self.layout.blob_path(sha256_lower)
            if local_path.exists():
                logger.debug("[Backup] Blob %s already exists locally", sha256_lower[:12])
                return BackupOperationResult(
                    success=True,
                    sha256=sha256_lower,
                    bytes_copied=0,
                    duration_ms=0,
                    verified=True,
                )

            # Check if on backup
            backup_path = self.backup_blob_path(sha256_lower)
            if not backup_path or not backup_path.exists():
                logger.error("[Backup] Blob %s not found on backup", sha256_lower[:12])
                raise BlobNotFoundError(f"Blob {sha256_lower} not found on backup")

            blob_size = backup_path.stat().st_size
            logger.debug("[Backup] Blob %s size: %.2f MB", sha256_lower[:12], blob_size / 1024 / 1024)

            # Check free space locally
            try:
                usage = shutil.disk_usage(self.layout.blobs_path)
                if usage.free < blob_size:
                    logger.error(
                        "[Backup] Insufficient local space: need %.2f MB, have %.2f MB",
                        blob_size / 1024 / 1024,
                        usage.free / 1024 / 1024,
                    )
                    raise InsufficientSpaceError(
                        f"Not enough local space: need {blob_size}, have {usage.free}"
                    )
            except InsufficientSpaceError:
                raise
            except Exception as e:
                logger.debug("[Backup] Could not check local disk space: %s", e)

            # Create parent dirs
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy with progress
            logger.debug("[Backup] Restoring to %s", local_path)
            bytes_copied = self._copy_file(
                backup_path, local_path, progress_callback
            )

            # Verify if requested
            verified = None
            if verify_after:
                logger.debug("[Backup] Verifying restored copy")
                actual_hash = compute_sha256(local_path)
                verified = actual_hash == sha256_lower
                if not verified:
                    local_path.unlink(missing_ok=True)
                    logger.error(
                        "[Backup] Restore verification failed: expected %s, got %s",
                        sha256_lower[:12],
                        actual_hash[:12],
                    )
                    raise BackupError(
                        f"Verification failed: expected {sha256_lower}, got {actual_hash}"
                    )

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "[Backup] Successfully restored %s (%.2f MB in %dms)",
                sha256_lower[:12],
                bytes_copied / 1024 / 1024,
                duration_ms,
            )

            return BackupOperationResult(
                success=True,
                sha256=sha256_lower,
                bytes_copied=bytes_copied,
                duration_ms=duration_ms,
                verified=verified,
            )

        except (BackupNotEnabledError, BackupNotConnectedError, BlobNotFoundError,
                InsufficientSpaceError, BackupError) as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("[Backup] Restore failed for %s: %s", sha256_lower[:12], e)
            return BackupOperationResult(
                success=False,
                sha256=sha256_lower,
                duration_ms=duration_ms,
                error=str(e),
            )

    def delete_from_backup(
        self,
        sha256: str,
        confirm: bool = False,
    ) -> BackupDeleteResult:
        """
        Delete a blob from backup storage.

        Args:
            sha256: SHA256 hash of the blob
            confirm: Must be True to actually delete

        Returns:
            BackupDeleteResult with operation details
        """
        sha256_lower = sha256.lower()

        try:
            self._require_connected()

            if not confirm:
                return BackupDeleteResult(
                    success=False,
                    sha256=sha256_lower,
                    error="Deletion not confirmed",
                )

            backup_path = self.backup_blob_path(sha256_lower)
            if not backup_path or not backup_path.exists():
                return BackupDeleteResult(
                    success=False,
                    sha256=sha256_lower,
                    error="Blob not found on backup",
                )

            blob_size = backup_path.stat().st_size

            # Check if still on local
            local_path = self.layout.blob_path(sha256_lower)
            still_on_local = local_path.exists()

            # Delete from backup
            backup_path.unlink()

            # Try to clean up empty parent directory
            try:
                backup_path.parent.rmdir()
            except OSError:
                pass  # Directory not empty

            return BackupDeleteResult(
                success=True,
                sha256=sha256_lower,
                bytes_freed=blob_size,
                still_on_local=still_on_local,
            )

        except (BackupNotEnabledError, BackupNotConnectedError) as e:
            return BackupDeleteResult(
                success=False,
                sha256=sha256_lower,
                error=str(e),
            )

    # =========================================================================
    # Sync Operations
    # =========================================================================

    def sync(
        self,
        direction: str = "to_backup",
        only_missing: bool = True,
        dry_run: bool = True,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> SyncResult:
        """
        Sync blobs between local and backup storage.

        Args:
            direction: "to_backup" or "from_backup"
            only_missing: Only sync blobs missing from target
            dry_run: If True, don't actually copy anything
            progress_callback: Optional callback (sha256, bytes_done, total_bytes)

        Returns:
            SyncResult with sync details
        """
        result = SyncResult(
            dry_run=dry_run,
            direction=direction,
        )

        try:
            self._require_connected()
        except (BackupNotEnabledError, BackupNotConnectedError) as e:
            result.errors.append(str(e))
            return result

        # Get blob sets
        local_blobs = set(self._list_local_blobs())
        backup_blobs = set(self.list_backup_blobs())

        # Determine what to sync
        if direction == "to_backup":
            if only_missing:
                to_sync = local_blobs - backup_blobs
            else:
                to_sync = local_blobs
        else:  # from_backup
            if only_missing:
                to_sync = backup_blobs - local_blobs
            else:
                to_sync = backup_blobs

        # Build items list
        for sha256 in to_sync:
            if direction == "to_backup":
                size = self._get_local_blob_size(sha256) or 0
            else:
                size = self.get_backup_blob_size(sha256) or 0

            result.items.append(SyncItem(sha256=sha256, size_bytes=size))
            result.bytes_to_sync += size

        result.blobs_to_sync = len(result.items)

        # If dry run, we're done
        if dry_run:
            return result

        # Actually sync
        for item in result.items:
            try:
                if direction == "to_backup":
                    op_result = self.backup_blob(item.sha256, verify_after=True)
                else:
                    op_result = self.restore_blob(item.sha256, verify_after=True)

                if op_result.success:
                    result.blobs_synced += 1
                    result.bytes_synced += op_result.bytes_copied
                else:
                    result.errors.append(f"{item.sha256}: {op_result.error}")

                if progress_callback:
                    progress_callback(item.sha256, result.bytes_synced, result.bytes_to_sync)

            except Exception as e:
                result.errors.append(f"{item.sha256}: {str(e)}")

        # Update last sync time
        self._last_sync = datetime.now().isoformat()

        return result

    # =========================================================================
    # Verification
    # =========================================================================

    def verify_backup_blob(self, sha256: str) -> bool:
        """
        Verify a blob's integrity on backup storage.

        Args:
            sha256: SHA256 hash to verify

        Returns:
            True if blob exists and hash matches
        """
        backup_path = self.backup_blob_path(sha256)
        if not backup_path or not backup_path.exists():
            return False

        actual_hash = compute_sha256(backup_path)
        return actual_hash == sha256.lower()

    def verify_all_backup_blobs(self) -> Tuple[List[str], List[str]]:
        """
        Verify all blobs on backup storage.

        Returns:
            Tuple of (valid_hashes, invalid_hashes)
        """
        valid = []
        invalid = []

        for sha256 in self.list_backup_blobs():
            if self.verify_backup_blob(sha256):
                valid.append(sha256)
            else:
                invalid.append(sha256)

        return valid, invalid

    # =========================================================================
    # Guard Rails
    # =========================================================================

    def is_last_copy(self, sha256: str) -> bool:
        """
        Check if this is the last copy of a blob.

        Returns True if blob exists in exactly one location.
        """
        local_exists = self.layout.blob_path(sha256).exists()
        backup_exists = self.blob_exists_on_backup(sha256)

        # Last copy if only in one place
        return (local_exists and not backup_exists) or (backup_exists and not local_exists)

    def get_delete_warning(self, sha256: str, target: str) -> Optional[str]:
        """
        Get a warning message if deletion would be dangerous.

        Args:
            sha256: Blob hash
            target: "local", "backup", or "both"

        Returns:
            Warning message or None if safe
        """
        local_exists = self.layout.blob_path(sha256).exists()
        backup_exists = self.blob_exists_on_backup(sha256)

        if target == "both":
            if local_exists or backup_exists:
                return (
                    "This will permanently delete the blob from ALL locations. "
                    "You will need to re-download it from the original source."
                )
        elif target == "local":
            if local_exists and not backup_exists:
                return (
                    "This blob is NOT backed up. "
                    "Deleting it will require re-downloading from the original source."
                )
        elif target == "backup":
            if backup_exists and not local_exists:
                return (
                    "This blob exists ONLY on backup. "
                    "Deleting it will require re-downloading from the original source."
                )

        return None

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _copy_file(
        self,
        src: Path,
        dst: Path,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy a file with optional progress callback."""
        total_size = src.stat().st_size
        bytes_copied = 0

        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            while True:
                chunk = fsrc.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                fdst.write(chunk)
                bytes_copied += len(chunk)
                if progress_callback:
                    progress_callback(bytes_copied, total_size)

        return bytes_copied

    def _list_local_blobs(self) -> List[str]:
        """List all blob hashes in local storage."""
        blobs = []
        blobs_path = self.layout.blobs_path
        if not blobs_path.exists():
            return blobs

        for prefix_dir in blobs_path.iterdir():
            if not prefix_dir.is_dir():
                continue
            for blob_file in prefix_dir.iterdir():
                if blob_file.is_file() and not blob_file.name.endswith(".part"):
                    blobs.append(blob_file.name)

        return blobs

    def _get_local_blob_size(self, sha256: str) -> Optional[int]:
        """Get size of a local blob."""
        blob_path = self.layout.blob_path(sha256)
        if blob_path.exists():
            return blob_path.stat().st_size
        return None

    # =========================================================================
    # State Sync Operations
    # =========================================================================

    def get_state_sync_status(self) -> StateSyncResult:
        """
        Get the current sync status of the state/ directory.

        Returns:
            StateSyncResult with dry_run=True showing what would be synced
        """
        return self.sync_state(dry_run=True)

    def sync_state(
        self,
        direction: str = "to_backup",
        dry_run: bool = True,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> StateSyncResult:
        """
        Sync the state/ directory between local and backup.

        Args:
            direction: "to_backup", "from_backup", or "bidirectional"
            dry_run: If True, don't actually copy files
            progress_callback: Optional callback (file_path, done, total)

        Returns:
            StateSyncResult with sync details
        """
        result = StateSyncResult(
            dry_run=dry_run,
            direction=direction,
            summary=StateSyncSummary(),
        )

        try:
            self._require_connected()
        except (BackupNotEnabledError, BackupNotConnectedError) as e:
            result.errors.append(str(e))
            return result

        state_path = self.layout.state_path
        backup_state = self.backup_state_path

        if not backup_state:
            result.errors.append("Cannot determine backup state path")
            return result

        # Collect all files from both sides
        local_files = self._collect_state_files(state_path, state_path)
        backup_files = self._collect_state_files(backup_state, backup_state)

        all_paths = set(local_files.keys()) | set(backup_files.keys())
        result.summary.total_files = len(all_paths)

        # Analyze each file
        for rel_path in sorted(all_paths):
            local_info = local_files.get(rel_path)
            backup_info = backup_files.get(rel_path)

            item = self._analyze_state_file(rel_path, local_info, backup_info)
            result.items.append(item)

            # Update summary
            if item.status == StateSyncStatus.SYNCED:
                result.summary.synced += 1
            elif item.status == StateSyncStatus.LOCAL_ONLY:
                result.summary.local_only += 1
            elif item.status == StateSyncStatus.BACKUP_ONLY:
                result.summary.backup_only += 1
            elif item.status == StateSyncStatus.MODIFIED:
                result.summary.modified += 1
            elif item.status == StateSyncStatus.CONFLICT:
                result.summary.conflicts += 1

        # If dry run, we're done
        if dry_run:
            return result

        # Actually sync files
        done = 0
        total = len([i for i in result.items if i.status != StateSyncStatus.SYNCED])

        for item in result.items:
            if item.status == StateSyncStatus.SYNCED:
                continue

            try:
                synced = self._sync_state_file(item, direction, state_path, backup_state)
                if synced:
                    result.synced_files += 1

                done += 1
                if progress_callback:
                    progress_callback(item.relative_path, done, total)

            except Exception as e:
                result.errors.append(f"{item.relative_path}: {str(e)}")

        # Update last sync time
        self._last_sync = datetime.now().isoformat()
        result.summary.last_sync = self._last_sync

        return result

    def _collect_state_files(
        self, root: Path, base: Path
    ) -> Dict[str, Tuple[datetime, int]]:
        """
        Collect all files in a state directory.

        Returns:
            Dict mapping relative paths to (mtime, size)
        """
        files = {}
        if not root.exists():
            return files

        for path in root.rglob("*"):
            if path.is_file():
                # Skip hidden files and temp files
                if path.name.startswith(".") or path.name.endswith(".tmp"):
                    continue
                rel_path = str(path.relative_to(base))
                stat = path.stat()
                files[rel_path] = (
                    datetime.fromtimestamp(stat.st_mtime),
                    stat.st_size,
                )

        return files

    def _analyze_state_file(
        self,
        rel_path: str,
        local_info: Optional[Tuple[datetime, int]],
        backup_info: Optional[Tuple[datetime, int]],
    ) -> StateSyncItem:
        """Analyze a single state file and determine its sync status."""
        if local_info is None and backup_info is None:
            # Should not happen
            return StateSyncItem(
                relative_path=rel_path,
                status=StateSyncStatus.SYNCED,
            )

        if local_info is None:
            # Only on backup
            return StateSyncItem(
                relative_path=rel_path,
                status=StateSyncStatus.BACKUP_ONLY,
                backup_mtime=backup_info[0].isoformat() if backup_info else None,
                backup_size=backup_info[1] if backup_info else None,
            )

        if backup_info is None:
            # Only on local
            return StateSyncItem(
                relative_path=rel_path,
                status=StateSyncStatus.LOCAL_ONLY,
                local_mtime=local_info[0].isoformat(),
                local_size=local_info[1],
            )

        # Both exist - compare
        local_mtime, local_size = local_info
        backup_mtime, backup_size = backup_info

        # If same size and mtime within 1 second, consider synced
        time_diff = abs((local_mtime - backup_mtime).total_seconds())
        if local_size == backup_size and time_diff < 2:
            return StateSyncItem(
                relative_path=rel_path,
                status=StateSyncStatus.SYNCED,
                local_mtime=local_mtime.isoformat(),
                backup_mtime=backup_mtime.isoformat(),
                local_size=local_size,
                backup_size=backup_size,
            )

        # Files differ - determine which is newer
        return StateSyncItem(
            relative_path=rel_path,
            status=StateSyncStatus.MODIFIED,
            local_mtime=local_mtime.isoformat(),
            backup_mtime=backup_mtime.isoformat(),
            local_size=local_size,
            backup_size=backup_size,
        )

    def _sync_state_file(
        self,
        item: StateSyncItem,
        direction: str,
        state_path: Path,
        backup_state: Path,
    ) -> bool:
        """
        Sync a single state file.

        Returns:
            True if file was synced
        """
        local_path = state_path / item.relative_path
        backup_path = backup_state / item.relative_path

        if direction == "to_backup":
            if item.status in (StateSyncStatus.LOCAL_ONLY, StateSyncStatus.MODIFIED):
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local_path, backup_path)
                return True

        elif direction == "from_backup":
            if item.status in (StateSyncStatus.BACKUP_ONLY, StateSyncStatus.MODIFIED):
                local_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, local_path)
                return True

        elif direction == "bidirectional":
            # For bidirectional, newer file wins
            if item.status == StateSyncStatus.LOCAL_ONLY:
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local_path, backup_path)
                return True
            elif item.status == StateSyncStatus.BACKUP_ONLY:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, local_path)
                return True
            elif item.status == StateSyncStatus.MODIFIED:
                # Compare mtimes - newer wins
                local_mtime = datetime.fromisoformat(item.local_mtime) if item.local_mtime else datetime.min
                backup_mtime = datetime.fromisoformat(item.backup_mtime) if item.backup_mtime else datetime.min
                if local_mtime >= backup_mtime:
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(local_path, backup_path)
                else:
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_path, local_path)
                return True

        return False

    def backup_state_file(self, relative_path: str) -> bool:
        """
        Backup a single state file.

        Args:
            relative_path: Path relative to state/ (e.g., "packs/MyPack/pack.json")

        Returns:
            True if backed up successfully
        """
        try:
            self._require_connected()
        except (BackupNotEnabledError, BackupNotConnectedError):
            return False

        state_path = self.layout.state_path
        backup_state = self.backup_state_path

        if not backup_state:
            return False

        local_path = state_path / relative_path
        backup_path = backup_state / relative_path

        if not local_path.exists():
            return False

        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, backup_path)
        return True

    def restore_state_file(self, relative_path: str) -> bool:
        """
        Restore a single state file from backup.

        Args:
            relative_path: Path relative to state/ (e.g., "packs/MyPack/pack.json")

        Returns:
            True if restored successfully
        """
        try:
            self._require_connected()
        except (BackupNotEnabledError, BackupNotConnectedError):
            return False

        state_path = self.layout.state_path
        backup_state = self.backup_state_path

        if not backup_state:
            return False

        local_path = state_path / relative_path
        backup_path = backup_state / relative_path

        if not backup_path.exists():
            return False

        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, local_path)
        return True
