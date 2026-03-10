"""
Local File Service — browse, validate, and import local model files.

Lets users resolve dependencies from files already on disk instead of downloading.

Three scenarios:
A) Dep has known remote source → recommend matching files by SHA256/filename
B) Unknown file → hash → Civitai/HF lookup → enrich metadata
C) No remote match → filename search → fallback to display_name from stem

Security:
- Path traversal prevention (no .., resolved path check)
- Extension allowlist (.safetensors, .ckpt, .pt, .bin, .pth, .onnx, .sft)
- Regular file check (no symlinks to sensitive locations, no devices)
- fstat on opened handle for TOCTOU prevention
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, Field

from .blob_store import compute_sha256
from .enrichment import EnrichmentResult, enrich_file, extract_stem
from .hash_cache import HashCache
from .models import AssetKind

logger = logging.getLogger(__name__)

# --- Constants ---

ALLOWED_EXTENSIONS = frozenset(
    {".safetensors", ".ckpt", ".pt", ".bin", ".pth", ".onnx", ".sft", ".gguf"}
)

# Extension filtering by AssetKind (for smarter browsing)
KIND_EXTENSIONS: dict[AssetKind, frozenset[str]] = {
    AssetKind.CHECKPOINT: frozenset({".safetensors", ".ckpt", ".pt"}),
    AssetKind.LORA: frozenset({".safetensors", ".pt"}),
    AssetKind.VAE: frozenset({".safetensors", ".pt", ".bin"}),
    AssetKind.CONTROLNET: frozenset({".safetensors", ".pt", ".bin", ".pth"}),
    AssetKind.EMBEDDING: frozenset({".safetensors", ".pt", ".bin"}),
    AssetKind.UPSCALER: frozenset({".safetensors", ".pt", ".bin", ".pth", ".onnx"}),
    AssetKind.CLIP: frozenset({".safetensors", ".bin"}),
    AssetKind.UNET: frozenset({".safetensors", ".pt", ".gguf"}),
}


# --- Data Models ---


@dataclass
class LocalFileInfo:
    """A single file found during directory browsing."""

    name: str  # "ponyDiffusionV6XL.safetensors"
    path: str  # Absolute path
    size: int  # bytes
    mtime: float  # Modification time
    extension: str  # ".safetensors"
    cached_hash: Optional[str] = None  # SHA256 if already in hash cache


@dataclass
class FileRecommendation:
    """A file with a match score for a specific dependency."""

    file: LocalFileInfo
    match_type: Literal["sha256_exact", "filename_exact", "filename_stem", "size_match", "none"]
    confidence: float  # 0.0 - 1.0
    reason: str  # "SHA256 matches expected hash"


class BrowseResult(BaseModel):
    """Result of browsing a local directory."""

    directory: str
    files: list[dict] = Field(default_factory=list)  # Serialized LocalFileInfo
    total_count: int = 0
    error: Optional[str] = None


class LocalImportResult(BaseModel):
    """Result of importing a local file."""

    success: bool
    sha256: Optional[str] = None
    file_size: Optional[int] = None
    display_name: Optional[str] = None
    enrichment_source: Optional[str] = None  # "civitai_hash", "civitai_name", "filename_only"
    canonical_source: Optional[dict] = None
    message: str = ""


# --- Security ---


class PathValidationError(Exception):
    """Raised when a path fails security validation."""

    pass


def validate_path(path: str) -> Path:
    """Validate a local file path for security.

    Returns resolved Path on success, raises PathValidationError on failure.

    Checks:
    1. Path is absolute
    2. No '..' components
    3. Resolved path matches (no symlink tricks to sensitive locations)
    4. File has allowlisted extension
    5. File is a regular file (not device, socket, pipe, etc.)
    """
    if not path:
        raise PathValidationError("Empty path")

    p = Path(path)

    # 1. Must be absolute
    if not p.is_absolute():
        raise PathValidationError(f"Path must be absolute: {path}")

    # 2. No '..' components
    if ".." in p.parts:
        raise PathValidationError(f"Path traversal not allowed: {path}")

    # 3. Resolve and compare (catches symlinks that escape)
    try:
        resolved = p.resolve(strict=True)
    except OSError as e:
        raise PathValidationError(f"Cannot resolve path: {e}") from e

    # 4. Extension check
    ext = resolved.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise PathValidationError(
            f"Extension '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 5. Must be a regular file (fstat on resolved path)
    try:
        st = resolved.stat()
    except OSError as e:
        raise PathValidationError(f"Cannot stat file: {e}") from e

    if not stat.S_ISREG(st.st_mode):
        raise PathValidationError(f"Not a regular file: {path}")

    return resolved


def validate_directory(path: str) -> Path:
    """Validate a directory path for browsing.

    Returns resolved Path on success, raises PathValidationError on failure.
    """
    if not path:
        raise PathValidationError("Empty path")

    p = Path(path)

    if not p.is_absolute():
        raise PathValidationError(f"Path must be absolute: {path}")

    if ".." in p.parts:
        raise PathValidationError(f"Path traversal not allowed: {path}")

    try:
        resolved = p.resolve(strict=True)
    except OSError as e:
        raise PathValidationError(f"Cannot resolve path: {e}") from e

    if not resolved.is_dir():
        raise PathValidationError(f"Not a directory: {path}")

    return resolved


# --- Service ---


class LocalFileService:
    """Service for browsing, validating, and importing local model files.

    Follows Store facade pattern — injected as 10th service in Store.__init__.
    """

    def __init__(
        self,
        hash_cache: HashCache,
        blob_store: Any,  # BlobStore (avoid circular import)
        pack_service_getter: Optional[Callable] = None,
    ):
        self._hash_cache = hash_cache
        self._blob_store = blob_store
        self._ps = pack_service_getter

    def browse(
        self,
        directory: str,
        kind: Optional[AssetKind] = None,
    ) -> BrowseResult:
        """List model files in a directory, optionally filtered by kind.

        Args:
            directory: Absolute path to directory
            kind: If provided, filter by kind-specific extensions
        """
        try:
            dir_path = validate_directory(directory)
        except PathValidationError as e:
            return BrowseResult(directory=directory, error=str(e))

        # Determine allowed extensions
        extensions = ALLOWED_EXTENSIONS
        if kind and kind in KIND_EXTENSIONS:
            extensions = KIND_EXTENSIONS[kind]

        files: list[LocalFileInfo] = []
        try:
            for entry in sorted(dir_path.iterdir(), key=lambda e: e.name.lower()):
                if not entry.is_file():
                    continue
                ext = entry.suffix.lower()
                if ext not in extensions:
                    continue

                try:
                    st = entry.stat()
                except OSError:
                    continue

                # Check hash cache for precomputed hash
                cached_hash = self._hash_cache.get(entry)

                files.append(
                    LocalFileInfo(
                        name=entry.name,
                        path=str(entry),
                        size=st.st_size,
                        mtime=st.st_mtime,
                        extension=ext,
                        cached_hash=cached_hash,
                    )
                )
        except PermissionError:
            return BrowseResult(
                directory=directory, error=f"Permission denied: {directory}"
            )
        except OSError as e:
            return BrowseResult(directory=directory, error=str(e))

        return BrowseResult(
            directory=directory,
            files=[_file_info_to_dict(f) for f in files],
            total_count=len(files),
        )

    def recommend(
        self,
        directory: str,
        dep: Any,  # PackDependency
        kind: Optional[AssetKind] = None,
    ) -> list[FileRecommendation]:
        """Scan directory and rank files by match likelihood to a dependency.

        Uses dependency's known SHA256, filename, and name to score files.
        """
        browse_result = self.browse(directory, kind)
        if browse_result.error or not browse_result.files:
            return []

        # Extract dependency hints
        dep_sha256 = _get_dep_sha256(dep)
        dep_filename = getattr(dep, "filename", None) or getattr(dep, "name", None) or ""
        dep_stem = extract_stem(dep_filename).lower() if dep_filename else ""

        recommendations: list[FileRecommendation] = []

        for file_dict in browse_result.files:
            file_info = _dict_to_file_info(file_dict)
            rec = self._score_file(file_info, dep_sha256, dep_filename, dep_stem)
            recommendations.append(rec)

        # Sort by confidence descending, then by name
        recommendations.sort(key=lambda r: (-r.confidence, r.file.name.lower()))
        return recommendations

    def _score_file(
        self,
        file_info: LocalFileInfo,
        dep_sha256: Optional[str],
        dep_filename: str,
        dep_stem: str,
    ) -> FileRecommendation:
        """Score a single file against dependency hints."""
        # 1. Exact SHA256 match (if cached hash available)
        if dep_sha256 and file_info.cached_hash:
            if file_info.cached_hash.lower() == dep_sha256.lower():
                return FileRecommendation(
                    file=file_info,
                    match_type="sha256_exact",
                    confidence=1.0,
                    reason="SHA256 hash matches expected",
                )

        # 2. Exact filename match
        if dep_filename and file_info.name.lower() == dep_filename.lower():
            return FileRecommendation(
                file=file_info,
                match_type="filename_exact",
                confidence=0.85,
                reason=f"Filename matches: {dep_filename}",
            )

        # 3. Stem similarity
        if dep_stem:
            file_stem = extract_stem(file_info.name).lower()
            if dep_stem in file_stem or file_stem in dep_stem:
                return FileRecommendation(
                    file=file_info,
                    match_type="filename_stem",
                    confidence=0.6,
                    reason=f"Name contains: {dep_stem}",
                )

        # 4. No match
        return FileRecommendation(
            file=file_info,
            match_type="none",
            confidence=0.0,
            reason="",
        )

    def import_file(
        self,
        file_path: str,
        pack_name: str,
        dep_id: str,
        *,
        skip_enrichment: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> LocalImportResult:
        """Import a local file into blob store and resolve dependency.

        Steps:
        1. Validate path (security)
        2. Hash file (SHA256) — uses hash cache
        3. Copy to blob store (or skip if blob already exists)
        4. Enrich metadata (Civitai/HF lookup)
        5. Apply resolution to dependency

        Args:
            file_path: Absolute path to model file
            pack_name: Target pack name
            dep_id: Target dependency ID
            skip_enrichment: Skip remote lookups (for testing)
            progress_callback: Optional (stage, progress_0_to_1) callback
        """
        # 1. Validate path
        try:
            resolved_path = validate_path(file_path)
        except PathValidationError as e:
            return LocalImportResult(success=False, message=str(e))

        file_size = resolved_path.stat().st_size

        # 2. Hash (use cache if available)
        if progress_callback:
            progress_callback("hashing", 0.0)

        sha256 = self._hash_cache.get(resolved_path)
        if sha256 is None:
            sha256 = compute_sha256(resolved_path)
            self._hash_cache.compute_and_cache(resolved_path)
            sha256 = self._hash_cache.get(resolved_path) or sha256

        if progress_callback:
            progress_callback("hashing", 1.0)

        # 3. Copy to blob store (dedup: skip if exists)
        if progress_callback:
            progress_callback("copying", 0.0)

        blob_path = self._blob_store.blob_path(sha256)
        if not blob_path.exists():
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: copy to unique .tmp, then os.replace() to final location
            # Prevents race condition if two imports run for the same file
            import uuid as _uuid
            tmp_path = blob_path.parent / f"{blob_path.name}.{_uuid.uuid4().hex[:8]}.tmp"
            try:
                # Try reflink first (instant, zero-copy), then hardlink, then copy
                if not _try_reflink(resolved_path, tmp_path):
                    if not _try_hardlink(resolved_path, tmp_path):
                        shutil.copy2(resolved_path, tmp_path)
                os.replace(str(tmp_path), str(blob_path))
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

        if progress_callback:
            progress_callback("copying", 1.0)

        # 4. Enrich metadata
        enrichment = EnrichmentResult(source="filename_only", display_name=extract_stem(resolved_path.name))
        if not skip_enrichment:
            if progress_callback:
                progress_callback("enriching", 0.0)

            civitai = self._get_civitai()
            hf = self._get_hf_client()
            kind = self._get_dep_kind(pack_name, dep_id)
            enrichment = enrich_file(sha256, resolved_path.name, civitai, kind, hf_client=hf)

            if progress_callback:
                progress_callback("enriching", 1.0)

        # 5. Apply resolution
        if progress_callback:
            progress_callback("applying", 0.0)

        apply_error = self._apply_resolution(
            pack_name, dep_id, sha256, file_size, resolved_path, enrichment
        )

        if progress_callback:
            progress_callback("applying", 1.0)

        # Save hash cache
        self._hash_cache.save()

        if apply_error:
            return LocalImportResult(
                success=False,
                sha256=sha256,
                file_size=file_size,
                message=f"Import succeeded but apply failed: {apply_error}",
            )

        return LocalImportResult(
            success=True,
            sha256=sha256,
            file_size=file_size,
            display_name=enrichment.display_name,
            enrichment_source=enrichment.source,
            canonical_source=(
                enrichment.canonical_source.model_dump()
                if enrichment.canonical_source
                else None
            ),
            message="File imported and dependency resolved",
        )

    def _get_civitai(self) -> Any:
        """Get Civitai client via pack_service."""
        if self._ps is None:
            return None
        ps = self._ps()
        if ps is None:
            return None
        return getattr(ps, "civitai", None)

    def _get_hf_client(self) -> Any:
        """Get HuggingFace client via pack_service."""
        if self._ps is None:
            return None
        ps = self._ps()
        if ps is None:
            return None
        return getattr(ps, "hf_client", None)

    def _get_dep_kind(self, pack_name: str, dep_id: str) -> Optional[AssetKind]:
        """Get AssetKind for a dependency."""
        if self._ps is None:
            return None
        ps = self._ps()
        if ps is None:
            return None
        try:
            pack = ps.get_pack(pack_name)
            if pack:
                for dep in pack.dependencies:
                    if dep.id == dep_id:
                        return getattr(dep, "kind", None)
        except Exception:
            pass
        return None

    def _apply_resolution(
        self,
        pack_name: str,
        dep_id: str,
        sha256: str,
        file_size: int,
        file_path: Path,
        enrichment: EnrichmentResult,
    ) -> Optional[str]:
        """Apply the resolution to the dependency. Returns error message or None."""
        if self._ps is None:
            return "No pack service available"

        ps = self._ps()
        if ps is None:
            return "Pack service not initialized"

        try:
            from .models import DependencySelector, SelectorStrategy
            from .resolve_models import ManualResolveData

            # Build selector based on enrichment
            if enrichment.civitai and enrichment.strategy == SelectorStrategy.CIVITAI_FILE:
                selector_data = ManualResolveData(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=enrichment.civitai,
                    local_path=str(file_path),
                    canonical_source=enrichment.canonical_source,
                    display_name=enrichment.display_name,
                )
            elif enrichment.huggingface:
                selector_data = ManualResolveData(
                    strategy=SelectorStrategy.HUGGINGFACE_FILE,
                    huggingface=enrichment.huggingface,
                    local_path=str(file_path),
                    canonical_source=enrichment.canonical_source,
                    display_name=enrichment.display_name,
                )
            else:
                selector_data = ManualResolveData(
                    strategy=SelectorStrategy.LOCAL_FILE,
                    local_path=str(file_path),
                    display_name=enrichment.display_name,
                )

            # Use resolve_service.apply_manual if available
            store = getattr(ps, "_store", None)
            if store and hasattr(store, "resolve_service"):
                result = store.resolve_service.apply_manual(
                    pack_name, dep_id, selector_data
                )
                if not result.success:
                    return result.message
                return None

            # Fallback: direct pack_service write
            if hasattr(ps, "apply_dependency_resolution"):
                selector = DependencySelector(
                    strategy=selector_data.strategy,
                    civitai=selector_data.civitai,
                    huggingface=selector_data.huggingface,
                    local_path=selector_data.local_path,
                    canonical_source=selector_data.canonical_source,
                )
                ps.apply_dependency_resolution(
                    pack_name=pack_name,
                    dep_id=dep_id,
                    selector=selector,
                    canonical_source=selector_data.canonical_source,
                    lock_entry=None,
                    display_name=selector_data.display_name,
                )
                return None

            return "No apply method available"
        except Exception as e:
            logger.error("[local-import] Apply failed: %s", e, exc_info=True)
            return str(e)


# --- File copy strategies ---


def _try_reflink(src: Path, dst: Path) -> bool:
    """Try copy-on-write reflink (Btrfs, XFS, APFS). Zero extra disk space."""
    try:
        # Linux: use ioctl FICLONE or cp --reflink=always
        import subprocess

        result = subprocess.run(
            ["cp", "--reflink=always", str(src), str(dst)],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _try_hardlink(src: Path, dst: Path) -> bool:
    """Try hardlink (same filesystem only). Zero extra disk space."""
    try:
        os.link(str(src), str(dst))
        return True
    except OSError:
        return False


# --- Helpers ---


def _file_info_to_dict(info: LocalFileInfo) -> dict:
    """Serialize LocalFileInfo to dict for API response."""
    return {
        "name": info.name,
        "path": info.path,
        "size": info.size,
        "mtime": info.mtime,
        "extension": info.extension,
        "cached_hash": info.cached_hash,
    }


def _dict_to_file_info(d: dict) -> LocalFileInfo:
    """Deserialize dict to LocalFileInfo."""
    return LocalFileInfo(
        name=d["name"],
        path=d["path"],
        size=d["size"],
        mtime=d["mtime"],
        extension=d["extension"],
        cached_hash=d.get("cached_hash"),
    )


def _get_dep_sha256(dep: Any) -> Optional[str]:
    """Extract expected SHA256 from dependency selector or lock."""
    selector = getattr(dep, "selector", None)
    if selector is None:
        return None

    # Check civitai selector
    civitai = getattr(selector, "civitai", None)
    if civitai:
        sha = getattr(civitai, "sha256", None)
        if sha:
            return sha

    # Check lock entry
    lock = getattr(dep, "lock", None) or getattr(dep, "resolved", None)
    if lock:
        sha = getattr(lock, "sha256", None)
        if sha:
            return sha

    return None
