"""
Dependency Resolver Protocol and Implementations.

Defines the DependencyResolver protocol for resolving pack dependencies,
with provider-specific implementations for Civitai, HuggingFace, URL, and local files.

Each resolver is responsible for one or more SelectorStrategy values
and is registered in PackService via a strategy -> resolver registry.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .models import (
    ArtifactDownload,
    ArtifactIntegrity,
    ArtifactProvider,
    AssetKind,
    PackDependency,
    ProviderName,
    ResolvedArtifact,
    SelectorConstraints,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class DependencyResolver(Protocol):
    """Protocol for resolving a pack dependency to a downloadable artifact."""

    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
        """
        Resolve a dependency to an artifact with download URL(s).

        Args:
            dep: The dependency to resolve.
            **kwargs: Additional context (e.g., existing_lock, layout).

        Returns:
            ResolvedArtifact if resolution succeeds, None if this resolver
            cannot handle the dependency.
        """
        ...


class CivitaiFileResolver:
    """Resolves pinned Civitai file dependencies (CIVITAI_FILE strategy)."""

    def __init__(self, civitai_client: Any):
        self._civitai = civitai_client

    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
        if not dep.selector.civitai:
            return None

        civ = dep.selector.civitai
        if not civ.version_id:
            return None

        version_data = self._civitai.get_model_version(civ.version_id)
        files = version_data.get("files", [])

        target_file = None
        if civ.file_id:
            for f in files:
                if f.get("id") == civ.file_id:
                    target_file = f
                    break
        if not target_file and files:
            target_file = files[0]

        if not target_file:
            return None

        hashes = target_file.get("hashes", {})
        sha256 = hashes.get("SHA256", "").lower() if hashes else None

        download_url = target_file.get("downloadUrl", "")
        if not download_url:
            download_url = f"https://civitai.com/api/download/models/{civ.version_id}"

        return ResolvedArtifact(
            kind=dep.kind,
            sha256=sha256,
            size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
            provider=ArtifactProvider(
                name=ProviderName.CIVITAI,
                model_id=civ.model_id,
                version_id=civ.version_id,
                file_id=target_file.get("id"),
                filename=target_file.get("name"),
            ),
            download=ArtifactDownload(urls=[download_url]),
            integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
        )


class CivitaiLatestResolver:
    """Resolves latest Civitai model version (CIVITAI_MODEL_LATEST strategy)."""

    def __init__(self, civitai_client: Any):
        self._civitai = civitai_client

    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
        if not dep.selector.civitai:
            return None

        civ = dep.selector.civitai

        # If a specific version_id is pinned, fetch that exact version
        # instead of blindly taking versions[0] (latest).
        # Multi-version packs have different version_ids per dependency.
        if civ.version_id:
            return self._resolve_pinned_version(dep, civ)

        # No pinned version — fall back to latest
        model_data = self._civitai.get_model(civ.model_id)
        versions = model_data.get("modelVersions", [])
        if not versions:
            return None

        latest = versions[0]
        return self._build_artifact(dep, civ, latest)

    def _resolve_pinned_version(
        self, dep: PackDependency, civ: Any
    ) -> Optional[ResolvedArtifact]:
        """Resolve a dependency pinned to a specific version_id."""
        version_data = self._civitai.get_model_version(civ.version_id)
        files = version_data.get("files", [])
        if not files:
            return None

        # If file_id is specified, find that exact file
        target_file = None
        if civ.file_id:
            for f in files:
                if f.get("id") == civ.file_id:
                    target_file = f
                    break

        # Fall back to file selection by constraints or primary
        if not target_file:
            target_file = _select_file(files, dep.selector.constraints)
        if not target_file:
            return None

        hashes = target_file.get("hashes", {})
        sha256 = hashes.get("SHA256", "").lower() if hashes else None

        download_url = target_file.get("downloadUrl", "")
        if not download_url:
            download_url = f"https://civitai.com/api/download/models/{civ.version_id}"

        return ResolvedArtifact(
            kind=dep.kind,
            sha256=sha256,
            size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
            provider=ArtifactProvider(
                name=ProviderName.CIVITAI,
                model_id=civ.model_id,
                version_id=civ.version_id,
                file_id=target_file.get("id"),
                filename=target_file.get("name"),
            ),
            download=ArtifactDownload(urls=[download_url]),
            integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
        )

    def _build_artifact(
        self, dep: PackDependency, civ: Any, version_data: dict
    ) -> Optional[ResolvedArtifact]:
        """Build a ResolvedArtifact from version data."""
        files = version_data.get("files", [])
        if not files:
            return None

        target_file = _select_file(files, dep.selector.constraints)
        if not target_file:
            return None

        hashes = target_file.get("hashes", {})
        sha256 = hashes.get("SHA256", "").lower() if hashes else None

        download_url = target_file.get("downloadUrl", "")
        if not download_url:
            download_url = f"https://civitai.com/api/download/models/{version_data['id']}"

        return ResolvedArtifact(
            kind=dep.kind,
            sha256=sha256,
            size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
            provider=ArtifactProvider(
                name=ProviderName.CIVITAI,
                model_id=civ.model_id,
                version_id=version_data["id"],
                file_id=target_file.get("id"),
                filename=target_file.get("name"),
            ),
            download=ArtifactDownload(urls=[download_url]),
            integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
        )


class BaseModelHintResolver:
    """Resolves base model hints via config aliases (BASE_MODEL_HINT strategy)."""

    def __init__(self, civitai_client: Any, layout: Any):
        self._civitai = civitai_client
        self._layout = layout

    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
        if not dep.selector.base_model:
            return None

        try:
            config = self._layout.load_config()
            alias = config.base_model_aliases.get(dep.selector.base_model)
            if not alias or not alias.selector.civitai:
                return None

            civ = alias.selector.civitai
            if civ.version_id:
                version_data = self._civitai.get_model_version(civ.version_id)
                files = version_data.get("files", [])

                target_file = None
                if civ.file_id:
                    for f in files:
                        if f.get("id") == civ.file_id:
                            target_file = f
                            break
                if not target_file:
                    target_file = _select_file(files, dep.selector.constraints if hasattr(dep.selector, 'constraints') else None)
                if not target_file and files:
                    target_file = files[0]

                if target_file:
                    hashes = target_file.get("hashes", {})
                    sha256 = hashes.get("SHA256", "").lower() if hashes else None

                    download_url = target_file.get("downloadUrl", "")
                    if not download_url:
                        download_url = f"https://civitai.com/api/download/models/{civ.version_id}"

                    return ResolvedArtifact(
                        kind=dep.kind,
                        sha256=sha256,
                        size_bytes=target_file.get("sizeKB", 0) * 1024 if target_file.get("sizeKB") else None,
                        provider=ArtifactProvider(
                            name=ProviderName.CIVITAI,
                            model_id=civ.model_id,
                            version_id=civ.version_id,
                            file_id=target_file.get("id"),
                            filename=target_file.get("name"),
                        ),
                        download=ArtifactDownload(urls=[download_url]),
                        integrity=ArtifactIntegrity(sha256_verified=sha256 is not None),
                    )
        except Exception:
            pass

        return None


class HuggingFaceResolver:
    """Resolves HuggingFace file dependencies (HUGGINGFACE_FILE strategy)."""

    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
        if not dep.selector.huggingface:
            return None

        hf = dep.selector.huggingface

        url = f"https://huggingface.co/{hf.repo_id}/resolve/{hf.revision or 'main'}"
        if hf.subfolder:
            url += f"/{hf.subfolder}"
        url += f"/{hf.filename}"

        return ResolvedArtifact(
            kind=dep.kind,
            sha256=None,
            size_bytes=None,
            provider=ArtifactProvider(
                name=ProviderName.HUGGINGFACE,
                repo_id=hf.repo_id,
                filename=hf.filename,
                revision=hf.revision,
            ),
            download=ArtifactDownload(urls=[url]),
            integrity=ArtifactIntegrity(sha256_verified=False),
        )


class UrlResolver:
    """Resolves direct URL dependencies (URL_DOWNLOAD strategy)."""

    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
        if not dep.selector.url:
            return None

        return ResolvedArtifact(
            kind=dep.kind,
            sha256=None,
            size_bytes=None,
            provider=ArtifactProvider(name=ProviderName.URL),
            download=ArtifactDownload(urls=[dep.selector.url]),
            integrity=ArtifactIntegrity(sha256_verified=False),
        )


class LocalFileResolver:
    """Resolves local file dependencies (LOCAL_FILE strategy)."""

    def resolve(self, dep: PackDependency, **kwargs: Any) -> Optional[ResolvedArtifact]:
        if not dep.selector.local_path:
            return None

        path = Path(dep.selector.local_path)
        if not path.exists():
            return None

        from .blob_store import compute_sha256
        sha256 = compute_sha256(path)

        return ResolvedArtifact(
            kind=dep.kind,
            sha256=sha256,
            size_bytes=path.stat().st_size,
            provider=ArtifactProvider(name=ProviderName.LOCAL),
            download=ArtifactDownload(urls=[path.as_uri()]),
            integrity=ArtifactIntegrity(sha256_verified=True),
        )


# =============================================================================
# Shared Helpers
# =============================================================================

def _select_file(
    files: List[Dict[str, Any]],
    constraints: Optional[SelectorConstraints],
) -> Optional[Dict[str, Any]]:
    """Select best file from list based on constraints."""
    if not files:
        return None

    candidates = files.copy()

    if constraints:
        if constraints.primary_file_only:
            primary = [f for f in candidates if f.get("primary")]
            if primary:
                candidates = primary

        if constraints.file_ext:
            ext_filtered = [
                f for f in candidates
                if any(f.get("name", "").endswith(ext) for ext in constraints.file_ext)
            ]
            if ext_filtered:
                candidates = ext_filtered

    return candidates[0] if candidates else None
