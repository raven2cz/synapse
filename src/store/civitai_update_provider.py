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

    @property
    def civitai(self):
        """Lazy-load Civitai client."""
        if self._civitai is None:
            from ..clients.civitai_client import CivitaiClient
            self._civitai = CivitaiClient()
        return self._civitai

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

        # Get latest version from Civitai
        model_data = self.civitai.get_model(model_id)
        versions = model_data.get("modelVersions", [])
        if not versions:
            return None

        latest = versions[0]
        latest_version_id = latest["id"]

        # Check if we're already on latest version
        current_version_id = current.artifact.provider.version_id
        if current_version_id == latest_version_id:
            return UpdateCheckResult(has_update=False)

        # Find suitable files in latest version
        files = latest.get("files", [])
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
            download_url=target.get("downloadUrl") or self.build_download_url(latest_version_id, None),
            size_bytes=target.get("sizeKB", 0) * 1024 if target.get("sizeKB") else None,
        )

    def build_download_url(
        self,
        version_id: Optional[int],
        file_id: Optional[int],
    ) -> str:
        """Build a Civitai download URL for a specific version/file."""
        url = f"https://civitai.com/api/download/models/{version_id}"
        if file_id:
            url += "?type=Model&format=SafeTensor"
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
            model_data = self.civitai.get_model(model_id)
        except Exception:
            return 0

        # Find the version
        target_version = None
        for v in model_data.get("modelVersions", []):
            if version_id and v["id"] == version_id:
                target_version = v
                break
        if not target_version:
            # Use latest version
            versions = model_data.get("modelVersions", [])
            if versions:
                target_version = versions[0]

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
            model_data = self.civitai.get_model(source.model_id)
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
            model_data = self.civitai.get_model(source.model_id)
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
                    if any(f.get("name", "").endswith(ext) for ext in constraints.file_ext)
                ]
                if ext_filtered:
                    candidates = ext_filtered

        return candidates

    @staticmethod
    def _canonicalize_url(url: str) -> str:
        """Strip query params and fragments for URL dedup comparison."""
        return url.split("?")[0].split("#")[0]
