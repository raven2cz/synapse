"""
Synapse Store v2 - Blob Store

Content-addressable storage for model files using SHA256 hashing.

Features:
- Deduplication by SHA256 hash
- Atomic downloads with .part files
- Hash verification
- Support for file:// URLs (for testing)
- Progress callbacks
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from .layout import StoreLayout
from .models import BlobManifest

logger = logging.getLogger(__name__)


class BlobStoreError(Exception):
    """Base exception for blob store errors."""
    pass


class HashMismatchError(BlobStoreError):
    """Error when downloaded file hash doesn't match expected."""
    pass


class DownloadError(BlobStoreError):
    """Error during file download."""
    pass


# Progress callback type: (downloaded_bytes, total_bytes)
ProgressCallback = Callable[[int, int], None]


def compute_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """
    Compute SHA256 hash of a file.
    
    Args:
        path: Path to file
        chunk_size: Read chunk size (default 1MB)
    
    Returns:
        Lowercase hex SHA256 hash
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256.update(chunk)
    return sha256.hexdigest().lower()


def compute_sha256_streaming(
    data_iter,
    chunk_size: int = 1024 * 1024
) -> Tuple[bytes, str]:
    """
    Compute SHA256 while streaming data.
    
    Returns:
        Tuple of (data_bytes, sha256_hex)
    """
    sha256 = hashlib.sha256()
    chunks = []
    for chunk in data_iter:
        sha256.update(chunk)
        chunks.append(chunk)
    return b"".join(chunks), sha256.hexdigest().lower()


class BlobStore:
    """
    Content-addressable blob store using SHA256.
    
    Blobs are stored at: data/blobs/sha256/<first2>/<full_hash>
    
    Features:
    - Deduplication: same content = same blob
    - Atomic writes: download to .part, verify, rename
    - Concurrent downloads with worker pool
    """
    
    DEFAULT_CHUNK_SIZE = 8192
    DEFAULT_TIMEOUT = 300
    DEFAULT_MAX_WORKERS = 4
    
    def __init__(
        self,
        layout: StoreLayout,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        timeout: int = DEFAULT_TIMEOUT,
        max_workers: int = DEFAULT_MAX_WORKERS,
        api_key: Optional[str] = None,
    ):
        """
        Initialize blob store.
        
        Args:
            layout: Store layout manager
            chunk_size: Download chunk size
            timeout: Download timeout in seconds
            max_workers: Max concurrent downloads
            api_key: Optional API key for authenticated downloads (Civitai)
        """
        self.layout = layout
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.max_workers = max_workers
        self.api_key = api_key or os.environ.get("CIVITAI_API_KEY")
        
        self._session: Optional[requests.Session] = None
    
    @property
    def session(self) -> requests.Session:
        """Lazy-initialized requests session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": "Mozilla/5.0 (compatible; Synapse/2.0)",
            })
        return self._session
    
    # =========================================================================
    # Blob Path Operations
    # =========================================================================
    
    def blob_path(self, sha256: str) -> Path:
        """Get path to a blob."""
        return self.layout.blob_path(sha256.lower())
    
    def blob_exists(self, sha256: str) -> bool:
        """Check if a blob exists."""
        return self.blob_path(sha256).exists()
    
    def blob_size(self, sha256: str) -> Optional[int]:
        """Get size of a blob in bytes. Returns None if not exists."""
        path = self.blob_path(sha256)
        if path.exists():
            return path.stat().st_size
        return None
    
    # =========================================================================
    # Download Operations
    # =========================================================================
    
    def download(
        self,
        url: str,
        expected_sha256: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
        force: bool = False,
    ) -> str:
        """
        Download a file to blob store.
        
        Args:
            url: Download URL (http://, https://, or file://)
            expected_sha256: Expected SHA256 hash. If None, hash is computed after download.
            progress_callback: Optional progress callback (downloaded, total)
            force: If True, re-download even if blob exists
        
        Returns:
            SHA256 hash of downloaded file
        
        Raises:
            HashMismatchError: If downloaded hash doesn't match expected
            DownloadError: If download fails
        """
        # If we know the hash and blob exists, skip download
        if expected_sha256 and not force:
            if self.blob_exists(expected_sha256):
                return expected_sha256.lower()
        
        # Handle file:// URLs (for testing)
        parsed = urlparse(url)
        if parsed.scheme == "file":
            return self._copy_local_file(parsed.path, expected_sha256)
        
        # HTTP/HTTPS download
        return self._download_http(url, expected_sha256, progress_callback)
    
    def _copy_local_file(
        self,
        source_path: str,
        expected_sha256: Optional[str] = None,
    ) -> str:
        """Copy a local file to blob store."""
        source = Path(source_path)
        if not source.exists():
            raise DownloadError(f"Local file not found: {source_path}")
        
        # Compute hash
        actual_sha256 = compute_sha256(source)
        
        # Verify if expected
        if expected_sha256 and actual_sha256 != expected_sha256.lower():
            raise HashMismatchError(
                f"Hash mismatch for {source_path}: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        
        # Check if blob exists
        blob_path = self.blob_path(actual_sha256)
        if blob_path.exists():
            return actual_sha256
        
        # Copy to blob store
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, blob_path)
        
        return actual_sha256
    
    def _download_http(
        self,
        url: str,
        expected_sha256: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Download file via HTTP/HTTPS."""
        # Determine part file location
        if expected_sha256:
            part_path = self.layout.blob_part_path(expected_sha256)
        else:
            # Use temp location until we know the hash
            import uuid
            temp_name = f"download_{uuid.uuid4().hex}"
            part_path = self.layout.tmp_path / temp_name
        
        part_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add API key for Civitai downloads
        download_url = url
        if "civitai.com" in url:
            if self.api_key:
                separator = "&" if "?" in url else "?"
                download_url = f"{url}{separator}token={self.api_key}"
                logger.debug(f"[BlobStore] Using Civitai API key for download")
            else:
                logger.warning(f"[BlobStore] No Civitai API key configured! Some downloads may fail.")
        
        try:
            # Check for resume
            headers = {}
            mode = "wb"
            initial_size = 0
            
            if part_path.exists():
                initial_size = part_path.stat().st_size
                headers["Range"] = f"bytes={initial_size}-"
                mode = "ab"
            
            # Start download
            response = self.session.get(
                download_url,
                headers=headers,
                stream=True,
                timeout=self.timeout,
            )
            
            # Handle range response
            if response.status_code == 416:  # Range not satisfiable
                # File might be complete
                if expected_sha256 and part_path.exists():
                    actual = compute_sha256(part_path)
                    if actual == expected_sha256.lower():
                        return self._finalize_download(part_path, actual)
                raise DownloadError(f"Range not satisfiable for {url}")
            
            response.raise_for_status()

            # Check Content-Type - Civitai error pages return text/html
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type.lower():
                logger.error(f"[BlobStore] Received HTML content-type: {content_type}")
                raise DownloadError(
                    f"Download failed: server returned HTML error page instead of file. "
                    f"This usually means authentication is required. "
                    f"Please configure your Civitai API key in Settings."
                )

            # Get total size
            content_length = response.headers.get("content-length")
            total_size = int(content_length) + initial_size if content_length else 0
            downloaded = initial_size
            
            # Download with progress
            sha256 = hashlib.sha256()
            
            # If resuming, we need to hash the existing content first
            if initial_size > 0 and expected_sha256 is None:
                with open(part_path, "rb") as f:
                    for chunk in iter(lambda: f.read(self.chunk_size), b""):
                        sha256.update(chunk)
            
            with open(part_path, mode) as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        sha256.update(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            actual_sha256 = sha256.hexdigest().lower()
            
            # Verify hash if expected
            if expected_sha256 and actual_sha256 != expected_sha256.lower():
                part_path.unlink(missing_ok=True)
                raise HashMismatchError(
                    f"Hash mismatch for {url}: "
                    f"expected {expected_sha256}, got {actual_sha256}"
                )
            
            return self._finalize_download(part_path, actual_sha256)
            
        except requests.RequestException as e:
            # Don't delete part file - allow resume
            raise DownloadError(f"Download failed for {url}: {e}") from e
        except Exception:
            # Clean up on other errors
            part_path.unlink(missing_ok=True)
            raise
    
    def _finalize_download(self, part_path: Path, sha256: str) -> str:
        """Move completed download to final blob location."""
        blob_path = self.blob_path(sha256)
        
        # If blob already exists (race condition), just delete part
        if blob_path.exists():
            part_path.unlink(missing_ok=True)
            return sha256
        
        # Atomic rename to final location
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        part_path.replace(blob_path)
        
        return sha256
    
    # =========================================================================
    # Batch Operations
    # =========================================================================
    
    def download_many(
        self,
        downloads: List[Tuple[str, Optional[str]]],  # List of (url, expected_sha256)
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Dict[str, str]:
        """
        Download multiple files concurrently.
        
        Args:
            downloads: List of (url, expected_sha256) tuples
            progress_callback: Optional callback (url, downloaded, total)
        
        Returns:
            Dict mapping url -> sha256 for successful downloads
        
        Raises:
            DownloadError: If any download fails (after all attempts)
        """
        results = {}
        errors = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for url, sha256 in downloads:
                # Skip if already downloaded
                if sha256 and self.blob_exists(sha256):
                    results[url] = sha256.lower()
                    continue
                
                def make_callback(u: str):
                    if progress_callback:
                        return lambda d, t: progress_callback(u, d, t)
                    return None
                
                future = executor.submit(
                    self.download,
                    url,
                    sha256,
                    make_callback(url),
                )
                futures[future] = url
            
            for future in as_completed(futures):
                url = futures[future]
                try:
                    sha256 = future.result()
                    results[url] = sha256
                except Exception as e:
                    errors.append((url, str(e)))
        
        if errors:
            error_msgs = [f"{url}: {msg}" for url, msg in errors]
            raise DownloadError(f"Failed downloads:\n" + "\n".join(error_msgs))
        
        return results
    
    # =========================================================================
    # Verification
    # =========================================================================
    
    def verify(self, sha256: str) -> bool:
        """
        Verify a blob's integrity.
        
        Returns:
            True if blob exists and hash matches
        """
        path = self.blob_path(sha256)
        if not path.exists():
            return False
        
        actual = compute_sha256(path)
        return actual == sha256.lower()
    
    def verify_all(self) -> Tuple[List[str], List[str]]:
        """
        Verify all blobs in the store.
        
        Returns:
            Tuple of (valid_hashes, invalid_hashes)
        """
        valid = []
        invalid = []
        
        blobs_path = self.layout.blobs_path
        if not blobs_path.exists():
            return valid, invalid
        
        for prefix_dir in blobs_path.iterdir():
            if not prefix_dir.is_dir():
                continue
            for blob_file in prefix_dir.iterdir():
                # Skip .part (partial downloads) and .meta (manifests)
                if blob_file.is_file() and not blob_file.suffix:
                    expected = blob_file.name
                    if self.verify(expected):
                        valid.append(expected)
                    else:
                        invalid.append(expected)

        return valid, invalid
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def list_blobs(self) -> List[str]:
        """List all blob SHA256 hashes (excludes .part and .meta files)."""
        blobs = []
        blobs_path = self.layout.blobs_path
        if not blobs_path.exists():
            return blobs

        for prefix_dir in blobs_path.iterdir():
            if not prefix_dir.is_dir():
                continue
            for blob_file in prefix_dir.iterdir():
                # Skip .part (partial downloads) and .meta (manifests)
                if blob_file.is_file() and not blob_file.suffix:
                    blobs.append(blob_file.name)

        return blobs
    
    def remove_blob(self, sha256: str) -> bool:
        """
        Remove a blob from the store (and its manifest).

        Returns:
            True if blob was removed, False if it didn't exist
        """
        path = self.blob_path(sha256)
        if path.exists():
            path.unlink()
            # Also remove manifest if exists
            self.delete_manifest(sha256)
            # Remove empty parent directory
            try:
                path.parent.rmdir()
            except OSError:
                pass  # Directory not empty
            return True
        return False
    
    def clean_partial(self) -> int:
        """
        Remove all partial downloads (.part files).
        
        Returns:
            Number of files removed
        """
        count = 0
        blobs_path = self.layout.blobs_path
        if not blobs_path.exists():
            return count
        
        for prefix_dir in blobs_path.iterdir():
            if not prefix_dir.is_dir():
                continue
            for part_file in prefix_dir.glob("*.part"):
                try:
                    part_file.unlink()
                    count += 1
                except Exception:
                    pass
        
        return count
    
    def get_total_size(self) -> int:
        """Get total size of all blobs in bytes."""
        total = 0
        blobs_path = self.layout.blobs_path
        if not blobs_path.exists():
            return total
        
        for prefix_dir in blobs_path.iterdir():
            if not prefix_dir.is_dir():
                continue
            for blob_file in prefix_dir.iterdir():
                if blob_file.is_file() and not blob_file.name.endswith(".part"):
                    total += blob_file.stat().st_size
        
        return total
    
    # =========================================================================
    # Adopt Existing Files
    # =========================================================================
    
    def adopt(
        self,
        source_path: Path,
        expected_sha256: Optional[str] = None,
        prefer_hardlink: bool = True,
    ) -> str:
        """
        Adopt an existing file into the blob store.
        
        Args:
            source_path: Path to existing file
            expected_sha256: Optional expected hash (skips computation if provided)
            prefer_hardlink: If True, try hardlink before copy
        
        Returns:
            SHA256 hash of the file
        """
        if not source_path.exists():
            raise BlobStoreError(f"Source file not found: {source_path}")
        
        # Compute or use expected hash
        sha256 = expected_sha256.lower() if expected_sha256 else compute_sha256(source_path)
        
        # Check if already in store
        blob_path = self.blob_path(sha256)
        if blob_path.exists():
            return sha256
        
        # Create parent directory
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Try hardlink first (same filesystem, no copy)
        if prefer_hardlink:
            try:
                os.link(source_path, blob_path)
                return sha256
            except OSError:
                pass  # Fall through to copy
        
        # Fall back to copy
        shutil.copy2(source_path, blob_path)
        return sha256

    # =========================================================================
    # Blob Manifest Operations (write-once metadata)
    # =========================================================================

    def manifest_path(self, sha256: str) -> Path:
        """Get path to the manifest file for a blob."""
        return self.layout.blob_manifest_path(sha256.lower())

    def manifest_exists(self, sha256: str) -> bool:
        """Check if a manifest exists for this blob."""
        return self.manifest_path(sha256).exists()

    def read_manifest(self, sha256: str) -> Optional[BlobManifest]:
        """
        Read manifest for a blob.

        Returns:
            BlobManifest if exists, None otherwise
        """
        path = self.manifest_path(sha256)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return BlobManifest.model_validate(data)
        except Exception as e:
            logger.warning(f"[BlobStore] Failed to read manifest {sha256[:12]}: {e}")
            return None

    def write_manifest(self, sha256: str, manifest: BlobManifest) -> bool:
        """
        Write manifest for a blob (write-once, never overwrites).

        Args:
            sha256: Blob hash
            manifest: Manifest data

        Returns:
            True if written, False if manifest already exists (not an error)
        """
        path = self.manifest_path(sha256)

        # Write-once: never overwrite existing manifest
        if path.exists():
            logger.debug(f"[BlobStore] Manifest already exists for {sha256[:12]}, skipping")
            return False

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Write atomically via temp file
            temp_path = path.with_suffix(".meta.tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(manifest.model_dump(mode="json"), f, indent=2)
            temp_path.replace(path)
            logger.debug(f"[BlobStore] Created manifest for {sha256[:12]}")
            return True
        except Exception as e:
            logger.error(f"[BlobStore] Failed to write manifest {sha256[:12]}: {e}")
            # Clean up temp file if exists
            temp_path = path.with_suffix(".meta.tmp")
            if temp_path.exists():
                temp_path.unlink()
            return False

    def delete_manifest(self, sha256: str) -> bool:
        """
        Delete manifest for a blob (used when blob is deleted).

        Returns:
            True if deleted, False if didn't exist
        """
        path = self.manifest_path(sha256)
        if path.exists():
            try:
                path.unlink()
                return True
            except Exception as e:
                logger.warning(f"[BlobStore] Failed to delete manifest {sha256[:12]}: {e}")
        return False
