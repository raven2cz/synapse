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
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from .blob_store import compute_sha256
from .layout import StoreLayout
from .models import (
    BackupConfig,
    BackupDeleteResult,
    BackupOperationResult,
    BackupStatus,
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

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> BackupStatus:
        """
        Get backup storage status.

        Returns:
            BackupStatus with connection info and statistics
        """
        if not self.config.enabled:
            return BackupStatus(
                enabled=False,
                connected=False,
                path=self.config.path,
            )

        if not self.config.path:
            return BackupStatus(
                enabled=True,
                connected=False,
                path=None,
                error="Backup path not configured",
            )

        backup_path = self.backup_root
        if not backup_path or not backup_path.exists():
            return BackupStatus(
                enabled=True,
                connected=False,
                path=self.config.path,
                error="Backup path not accessible",
            )

        # Check if we can write to the backup
        blobs_path = self.backup_blobs_path
        try:
            if blobs_path:
                blobs_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return BackupStatus(
                enabled=True,
                connected=False,
                path=self.config.path,
                error="No write permission to backup path",
            )
        except Exception as e:
            return BackupStatus(
                enabled=True,
                connected=False,
                path=self.config.path,
                error=str(e),
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

        # Get free space
        free_space = None
        try:
            usage = shutil.disk_usage(backup_path)
            free_space = usage.free
        except Exception:
            pass

        return BackupStatus(
            enabled=True,
            connected=True,
            path=self.config.path,
            total_blobs=total_blobs,
            total_bytes=total_bytes,
            free_space=free_space,
            last_sync=self._last_sync,
        )

    def is_connected(self) -> bool:
        """Quick check if backup is connected."""
        status = self.get_status()
        return status.enabled and status.connected

    def _require_connected(self) -> None:
        """Raise if backup is not connected."""
        if not self.config.enabled:
            raise BackupNotEnabledError("Backup storage is not enabled")
        if not self.is_connected():
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

        try:
            self._require_connected()

            # Check if already on backup
            if self.blob_exists_on_backup(sha256_lower):
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
                raise BlobNotFoundError(f"Blob {sha256_lower} not found locally")

            blob_size = local_path.stat().st_size

            # Check free space on backup
            status = self.get_status()
            if status.free_space is not None and status.free_space < blob_size:
                raise InsufficientSpaceError(
                    f"Not enough space on backup: need {blob_size}, have {status.free_space}"
                )

            # Get backup path and create parent dirs
            backup_path = self.backup_blob_path(sha256_lower)
            if not backup_path:
                raise BackupError("Cannot determine backup path")
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy with progress
            bytes_copied = self._copy_file(
                local_path, backup_path, progress_callback
            )

            # Verify if requested
            verified = None
            if verify_after:
                actual_hash = compute_sha256(backup_path)
                verified = actual_hash == sha256_lower
                if not verified:
                    backup_path.unlink(missing_ok=True)
                    raise BackupError(
                        f"Verification failed: expected {sha256_lower}, got {actual_hash}"
                    )

            duration_ms = int((time.time() - start_time) * 1000)

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

        try:
            self._require_connected()

            # Check if already local
            local_path = self.layout.blob_path(sha256_lower)
            if local_path.exists():
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
                raise BlobNotFoundError(f"Blob {sha256_lower} not found on backup")

            blob_size = backup_path.stat().st_size

            # Check free space locally
            try:
                usage = shutil.disk_usage(self.layout.blobs_path)
                if usage.free < blob_size:
                    raise InsufficientSpaceError(
                        f"Not enough local space: need {blob_size}, have {usage.free}"
                    )
            except Exception:
                pass  # Continue if we can't check space

            # Create parent dirs
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy with progress
            bytes_copied = self._copy_file(
                backup_path, local_path, progress_callback
            )

            # Verify if requested
            verified = None
            if verify_after:
                actual_hash = compute_sha256(local_path)
                verified = actual_hash == sha256_lower
                if not verified:
                    local_path.unlink(missing_ok=True)
                    raise BackupError(
                        f"Verification failed: expected {sha256_lower}, got {actual_hash}"
                    )

            duration_ms = int((time.time() - start_time) * 1000)

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
