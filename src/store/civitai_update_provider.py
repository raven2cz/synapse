"""
Synapse Store v2 - Civitai Update Provider

Implements UpdateProvider for Civitai-hosted models.
Handles version checking, file filtering, download URL construction,
and metadata sync (previews, description, model info) via Civitai API.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import (
    Pack,
    PackDependency,
    PreviewInfo,
    ResolvedDependency,
    SelectorConstraints,
    UpdateCandidate,
)
from .update_provider import UpdateCheckResult

logger = logging.getLogger(__name__)


class CivitaiUpdateProvider:
    """
    Update provider for Civitai-hosted models.

    Checks for new versions by calling the Civitai API and comparing
    the latest version_id against the currently locked version_id.
    """

    def __init__(self, civitai_client: Optional[Any] = None):
        self._civitai = civitai_client
        self._model_cache: Dict[int, Dict[str, Any]] = {}

    @property
    def civitai(self):
        """Lazy-load Civitai client."""
        if self._civitai is None:
            from ..clients.civitai_client import CivitaiClient
            self._civitai = CivitaiClient()
        return self._civitai

    def get_model_cached(self, model_id: int) -> Dict[str, Any]:
        """Fetch model data with per-session cache to avoid duplicate API calls."""
        if model_id in self._model_cache:
            logger.debug("[CivitaiUpdateProvider] Cache hit for model %d", model_id)
            return self._model_cache[model_id]
        data = self.civitai.get_model(model_id)
        self._model_cache[model_id] = data
        return data

    def clear_cache(self) -> None:
        """Clear the model response cache (call before/after check-all sessions)."""
        self._model_cache.clear()

    # =========================================================================
    # UpdateProvider interface
    # =========================================================================

    def check_update(
        self,
        dep: PackDependency,
        current: ResolvedDependency,
    ) -> Optional[UpdateCheckResult]:
        """Check if a Civitai dependency has a newer version available."""
        if not dep.selector.civitai:
            return None

        model_id = dep.selector.civitai.model_id

        # Get latest version from Civitai (cached per check-all session)
        model_data = self.get_model_cached(model_id)
        versions = model_data.get("modelVersions", [])
        if not versions:
            return None

        latest = versions[0]
        latest_version_id = latest["id"]
        files = latest.get("files", [])

        # Check if we're already on latest version
        current_version_id = current.artifact.provider.version_id
        if current_version_id == latest_version_id:
            # Same version - still resolve the correct file and download URL.
            # This is needed for pending downloads where lock was updated
            # but blob is missing (e.g. download failed after apply).
            target = self._match_file_for_dep(files, dep, current)
            if not target:
                candidates = self._filter_files(files, dep.selector.constraints)
                if len(candidates) == 1:
                    target = candidates[0]

            if target:
                hashes = target.get("hashes", {})
                sha256 = hashes.get("SHA256", "").lower() if hashes else None
                return UpdateCheckResult(
                    has_update=False,
                    model_id=model_id,
                    version_id=latest_version_id,
                    file_id=target.get("id"),
                    sha256=sha256,
                    download_url=target.get("downloadUrl") or self.build_download_url(latest_version_id, target.get("id")),
                    filename=target.get("name"),
                )

            return UpdateCheckResult(has_update=False)

        # For multi-file models, try to match by filename from current lock
        # (each dep originally came from a specific file)
        target = self._match_file_for_dep(files, dep, current)

        if target:
            hashes = target.get("hashes", {})
            sha256 = hashes.get("SHA256", "").lower() if hashes else None
            return UpdateCheckResult(
                has_update=True,
                ambiguous=False,
                model_id=model_id,
                version_id=latest_version_id,
                file_id=target.get("id"),
                sha256=sha256,
                download_url=target.get("downloadUrl") or self.build_download_url(latest_version_id, target.get("id")),
                size_bytes=target.get("sizeKB", 0) * 1024 if target.get("sizeKB") else None,
                filename=target.get("name"),
            )

        # Filename matching failed — check if we have filename info.
        # If we know the current dep's filename but it doesn't match ANY file
        # in the latest version, this is NOT an update for this dep.
        # Civitai creators sometimes publish different artifacts (different
        # LoRAs, different workflows) as "versions" of one model page.
        # Without filename match we cannot reliably identify which file in
        # the new version corresponds to this dep.
        dep_filename = (
            current.artifact.provider.filename
            or (dep.expose.filename if dep.expose and isinstance(dep.expose.filename, str) else None)
        )
        if dep_filename:
            logger.debug(
                "[CivitaiUpdateProvider] No filename match for dep %s in "
                "version %d (current file: %s) — skipping as different artifact",
                dep.id, latest_version_id, dep_filename,
            )
            return UpdateCheckResult(has_update=False)

        # Fallback: generic filtering by constraints (only when no filename)
        candidates = self._filter_files(files, dep.selector.constraints)

        if not candidates:
            return None

        if len(candidates) > 1:
            # Ambiguous selection needed
            return UpdateCheckResult(
                has_update=True,
                ambiguous=True,
                candidates=[
                    UpdateCandidate(
                        provider="civitai",
                        provider_model_id=model_id,
                        provider_version_id=latest_version_id,
                        provider_file_id=f.get("id"),
                        sha256=f.get("hashes", {}).get("SHA256", "").lower() if f.get("hashes") else None,
                        filename=f.get("name"),
                        size_bytes=f.get("sizeKB", 0) * 1024 if f.get("sizeKB") else None,
                    )
                    for f in candidates
                ],
            )

        # Single candidate - update available
        target = candidates[0]
        hashes = target.get("hashes", {})
        sha256 = hashes.get("SHA256", "").lower() if hashes else None

        return UpdateCheckResult(
            has_update=True,
            ambiguous=False,
            model_id=model_id,
            version_id=latest_version_id,
            file_id=target.get("id"),
            sha256=sha256,
            download_url=target.get("downloadUrl") or self.build_download_url(latest_version_id, target.get("id")),
            size_bytes=target.get("sizeKB", 0) * 1024 if target.get("sizeKB") else None,
            filename=target.get("name"),
        )

    def build_download_url(
        self,
        version_id: Optional[int],
        file_id: Optional[int],
    ) -> str:
        """Build a Civitai download URL for a specific version/file."""
        url = f"https://civitai.com/api/download/models/{version_id}"
        if file_id:
            url += f"?id={file_id}"
        return url

    def merge_previews(self, pack: Pack) -> int:
        """Merge new preview images/videos from Civitai into the pack."""
        source = pack.source
        if not source or source.provider != "civitai":
            return 0

        model_id = source.model_id
        version_id = source.version_id
        if not model_id:
            return 0

        try:
            model_data = self.get_model_cached(model_id)
        except Exception:
            return 0

        # Find the version
        target_version = None
        for v in model_data.get("modelVersions", []):
            if version_id and v["id"] == version_id:
                target_version = v
                break
        if not target_version:
            # Use latest version as fallback — may not match pack's pinned version
            versions = model_data.get("modelVersions", [])
            if versions:
                target_version = versions[0]
                logger.warning(
                    "[CivitaiUpdateProvider] version_id=%s not found in model %d, "
                    "falling back to latest version %d",
                    version_id, model_id, target_version["id"],
                )

        if not target_version:
            return 0

        # Get Civitai images
        civitai_images = target_version.get("images", [])
        if not civitai_images:
            return 0

        # Build set of existing preview URLs for dedup (canonical form)
        existing_urls = set()
        for p in pack.previews:
            if p.url:
                existing_urls.add(self._canonicalize_url(p.url))

        # Add new previews
        added = 0
        for img in civitai_images:
            url = img.get("url", "")
            if not url or self._canonicalize_url(url) in existing_urls:
                continue

            # Derive filename from URL
            filename = url.rsplit("/", 1)[-1].split("?")[0] if "/" in url else "preview"

            # Determine media type from Civitai's type field
            img_type = img.get("type", "image")
            media_type = "video" if img_type == "video" else "image"

            preview = PreviewInfo(
                filename=filename,
                url=url,
                media_type=media_type,
                width=img.get("width"),
                height=img.get("height"),
                nsfw=img.get("nsfwLevel", 0) > 1,
                meta=img.get("meta"),
            )
            pack.previews.append(preview)
            existing_urls.add(self._canonicalize_url(url))
            added += 1

        return added

    def update_description(self, pack: Pack) -> bool:
        """Replace pack description with Civitai's latest."""
        source = pack.source
        if not source or source.provider != "civitai" or not source.model_id:
            return False

        try:
            model_data = self.get_model_cached(source.model_id)
        except Exception:
            return False

        new_description = model_data.get("description", "")
        if new_description and new_description != pack.description:
            pack.description = new_description
            return True
        return False

    def update_model_info(self, pack: Pack) -> bool:
        """Sync model info fields (trigger words, base model) from Civitai."""
        source = pack.source
        if not source or source.provider != "civitai" or not source.model_id:
            return False

        try:
            model_data = self.get_model_cached(source.model_id)
        except Exception:
            return False

        changed = False
        versions = model_data.get("modelVersions", [])

        # Find matching version or use latest
        target_version = None
        if source.version_id:
            for v in versions:
                if v["id"] == source.version_id:
                    target_version = v
                    break
        if not target_version and versions:
            target_version = versions[0]

        if not target_version:
            return False

        # Sync base model
        new_base = target_version.get("baseModel")
        if new_base and new_base != pack.base_model:
            pack.base_model = new_base
            changed = True

        # Sync trigger words into dependencies that have expose.trigger_words
        trained_words = target_version.get("trainedWords", [])
        if trained_words:
            for dep in pack.dependencies:
                if dep.expose and dep.expose.trigger_words is not None:
                    if set(dep.expose.trigger_words) != set(trained_words):
                        dep.expose.trigger_words = trained_words
                        changed = True

        return changed

    # =========================================================================
    # Internal helpers
    # =========================================================================

    @staticmethod
    def _match_file_for_dep(
        files: List[Dict[str, Any]],
        dep: PackDependency,
        current: ResolvedDependency,
    ) -> Optional[Dict[str, Any]]:
        """
        Try to match a specific file in the new version for this dependency.

        Uses filename matching: the current lock entry has provider.filename
        from the original import. Find the file with the same name in the
        new version's file list.

        This is critical for multi-file model versions (e.g. lora bundles)
        where each dependency corresponds to a different file.
        """
        current_filename = current.artifact.provider.filename
        # Fallback: use the expose filename from pack dependency
        if not current_filename:
            try:
                current_filename = dep.expose.filename if dep.expose and isinstance(dep.expose.filename, str) else None
            except (AttributeError, TypeError):
                current_filename = None
        if not current_filename or not files:
            return None

        # Strip path prefixes for comparison
        current_base = current_filename.rsplit("/", 1)[-1].lower()

        # Exact filename match
        for f in files:
            fname = f.get("name", "")
            if fname.lower() == current_base:
                return f

        # Partial match: same base name without version suffix
        # e.g. "ExtremeFrenchKissV1.safetensors" → "ExtremeFrenchKissV2.safetensors"
        import re
        # Strip trailing version suffixes: V1, v2, v1.5, V2.0, etc.
        # Only strip at the end of the stem to avoid removing "v1" from semantic names.
        _VERSION_RE = re.compile(r'[_.\- ]?[Vv]\d+(?:\.\d+)*$')
        current_parts = current_base.rsplit(".", 1)
        current_ext = current_parts[1].lower() if len(current_parts) > 1 else ""
        current_stem = _VERSION_RE.sub('', current_parts[0]).strip("_- ")
        if current_stem:
            for f in files:
                fname = f.get("name", "")
                fparts = fname.rsplit(".", 1)
                fext = fparts[1].lower() if len(fparts) > 1 else ""
                # Extension must match to prevent cross-type confusion
                if current_ext and fext and current_ext != fext:
                    continue
                candidate_stem = _VERSION_RE.sub('', fparts[0]).strip("_- ").lower()
                if candidate_stem == current_stem:
                    return f

        return None

    @staticmethod
    def _filter_files(
        files: List[Dict[str, Any]],
        constraints: Optional[SelectorConstraints],
    ) -> List[Dict[str, Any]]:
        """Filter files based on selector constraints."""
        if not files:
            return []

        candidates = files.copy()

        if constraints:
            # Filter by primary file
            if constraints.primary_file_only:
                primary = [f for f in candidates if f.get("primary")]
                if primary:
                    candidates = primary

            # Filter by extension
            if constraints.file_ext:
                ext_filtered = [
                    f for f in candidates
                    if any(f.get("name", "").lower().endswith(ext.lower()) for ext in constraints.file_ext)
                ]
                if ext_filtered:
                    candidates = ext_filtered

        return candidates

    @staticmethod
    def _canonicalize_url(url: str) -> str:
        """Strip query params and fragments for URL dedup comparison."""
        return url.split("?")[0].split("#")[0]
