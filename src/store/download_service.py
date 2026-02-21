"""
Synapse Store v2 - Centralized Download Service

Provides a single, reusable HTTP download implementation with:
- Auth provider matching and header injection
- Per-request sessions (thread-safe for concurrent downloads)
- Resume via Range headers and .part files
- SHA256 streaming verification
- HTML content-type error detection
- Split timeout (connect, read)
- Progress callbacks

Extracted from BlobStore._download_http() to eliminate 5 duplicate
download implementations across the codebase.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import requests

from .download_auth import DownloadAuthProvider

logger = logging.getLogger(__name__)

# Progress callback type: (downloaded_bytes, total_bytes)
ProgressCallback = Callable[[int, int], None]

USER_AGENT = "Mozilla/5.0 (compatible; Synapse/2.0)"


@dataclass
class DownloadResult:
    """Result of a file download."""
    sha256: str
    size: int
    resumed: bool = False


class DownloadError(Exception):
    """Error during file download."""
    pass


class DownloadService:
    """Centralized HTTP download with auth, resume, hashing, progress.

    Thread-safe: creates a new requests.Session per download call.
    """

    def __init__(
        self,
        auth_providers: Optional[List[DownloadAuthProvider]] = None,
        chunk_size: int = 8192,
    ):
        self._auth_providers = auth_providers or []
        self.chunk_size = chunk_size

    def _prepare_auth(self, url: str):
        """Match auth provider for URL and return (download_url, headers, matched_provider)."""
        download_url = url
        auth_headers: dict[str, str] = {}
        matched_auth = None

        logger.debug(
            "[DownloadService] _prepare_auth: url=%s, providers=%d",
            url[:80], len(self._auth_providers),
        )

        for auth_provider in self._auth_providers:
            if auth_provider.matches(url):
                download_url = auth_provider.authenticate_url(url)
                auth_headers = auth_provider.get_auth_headers(url)
                matched_auth = auth_provider
                logger.debug(
                    "[DownloadService] Auth matched: provider=%s, url_changed=%s, headers=%s",
                    type(auth_provider).__name__,
                    download_url != url,
                    list(auth_headers.keys()),
                )
                break

        if not matched_auth:
            logger.debug("[DownloadService] No auth provider matched for: %s", url[:80])

        return download_url, auth_headers, matched_auth

    def download_to_file(
        self,
        url: str,
        dest: Path,
        *,
        expected_sha256: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
        timeout: tuple[int, int] = (15, 60),
        chunk_size: Optional[int] = None,
        resume: bool = True,
    ) -> DownloadResult:
        """Download URL to file with auth injection, resume, hash verify.

        Args:
            url: HTTP/HTTPS URL to download
            dest: Destination file path (downloads directly, no .part management)
            expected_sha256: Optional expected hash for verification
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
            timeout: (connect_timeout, read_timeout) in seconds
            chunk_size: Override default chunk size
            resume: If True, resume partial downloads via Range header

        Returns:
            DownloadResult with sha256 hash and size

        Raises:
            DownloadError: On network errors, auth failures, or hash mismatch
        """
        chunk = chunk_size or self.chunk_size
        download_url, auth_headers, matched_auth = self._prepare_auth(url)

        # Log auth status for every Civitai URL
        if "civitai.com" in url:
            has_token = "token=" in download_url
            logger.info(
                "[DownloadService] Civitai download: token_in_url=%s, "
                "url_changed=%s, auth_headers=%s, original_url=%s",
                has_token,
                download_url != url,
                list(auth_headers.keys()),
                url[:100],
            )
            if not has_token:
                logger.error(
                    "[DownloadService] NO TOKEN in download URL! "
                    "auth_providers=%d, matched=%s",
                    len(self._auth_providers),
                    type(matched_auth).__name__ if matched_auth else "NONE",
                )

        # Per-request session for thread safety
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

        try:
            headers = {**auth_headers}
            mode = "wb"
            initial_size = 0

            if resume and dest.exists():
                initial_size = dest.stat().st_size
                headers["Range"] = f"bytes={initial_size}-"
                mode = "ab"

            response = session.get(
                download_url,
                headers=headers,
                stream=True,
                timeout=timeout,
            )

            # Handle range response — file already fully downloaded
            if response.status_code == 416:  # Range not satisfiable
                if dest.exists():
                    actual = self._compute_sha256(dest, chunk)
                    if expected_sha256 and actual != expected_sha256.lower():
                        dest.unlink(missing_ok=True)
                        raise DownloadError(
                            f"Hash mismatch for {url}: expected {expected_sha256}, got {actual}"
                        )
                    return DownloadResult(
                        sha256=actual, size=dest.stat().st_size, resumed=True,
                    )
                raise DownloadError(f"Range not satisfiable for {url}")

            response.raise_for_status()

            # Check Content-Type for HTML error pages
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type.lower():
                logger.error("[DownloadService] Received HTML content-type: %s", content_type)
                error_msg = (
                    matched_auth.auth_error_message()
                    if matched_auth
                    else f"Download failed: server returned HTML instead of file for {url}"
                )
                raise DownloadError(error_msg)

            # Calculate total size
            content_length = response.headers.get("content-length")
            total_size = int(content_length) + initial_size if content_length else 0
            downloaded = initial_size

            # Stream with hashing
            sha256 = hashlib.sha256()

            # If resuming, hash existing content first so the final
            # digest covers the entire file (not just the new chunks).
            if initial_size > 0:
                with open(dest, "rb") as f:
                    for existing_chunk in iter(lambda: f.read(chunk), b""):
                        sha256.update(existing_chunk)

            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, mode) as f:
                for data in response.iter_content(chunk_size=chunk):
                    if data:
                        f.write(data)
                        sha256.update(data)
                        downloaded += len(data)
                        if progress_callback:
                            progress_callback(downloaded, total_size)

            actual_sha256 = sha256.hexdigest().lower()

            if expected_sha256 and actual_sha256 != expected_sha256.lower():
                dest.unlink(missing_ok=True)
                raise DownloadError(
                    f"Hash mismatch for {url}: expected {expected_sha256}, got {actual_sha256}"
                )

            return DownloadResult(
                sha256=actual_sha256,
                size=downloaded,
                resumed=initial_size > 0,
            )

        except requests.RequestException as e:
            # Don't delete file on network errors - allow resume
            raise DownloadError(f"Download failed for {url}: {e}") from e
        except DownloadError:
            raise
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        finally:
            session.close()

    def download_to_bytes(
        self,
        url: str,
        *,
        timeout: tuple[int, int] = (15, 30),
    ) -> bytes:
        """Download small files (previews) to memory with auth.

        Args:
            url: HTTP/HTTPS URL to download
            timeout: (connect_timeout, read_timeout) in seconds

        Returns:
            File content as bytes

        Raises:
            DownloadError: On network errors or auth failures
        """
        download_url, auth_headers, matched_auth = self._prepare_auth(url)

        if "civitai.com" in url:
            logger.info(
                "[DownloadService] download_to_bytes: token_in_url=%s, url=%s",
                "token=" in download_url, url[:100],
            )

        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

        try:
            response = session.get(
                download_url,
                headers=auth_headers,
                timeout=timeout,
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type.lower():
                logger.error(
                    "[DownloadService] HTML response in download_to_bytes: "
                    "url=%s, final_url=%s, content_type=%s",
                    url[:100], response.url[:100], content_type,
                )
                error_msg = (
                    matched_auth.auth_error_message()
                    if matched_auth
                    else f"Download failed: server returned HTML instead of file for {url}"
                )
                raise DownloadError(error_msg)

            return response.content

        except requests.RequestException as e:
            raise DownloadError(f"Download failed for {url}: {e}") from e
        finally:
            session.close()

    @staticmethod
    def _compute_sha256(path: Path, chunk_size: int = 8192) -> str:
        """Compute SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256.update(chunk)
        return sha256.hexdigest().lower()
