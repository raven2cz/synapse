"""
Enrichment utilities — shared hash/name lookup for local file imports and evidence providers.

Extracted from PreviewMetaEvidenceProvider for reuse across:
- LocalFileService.import_file() (primary)
- PreviewMetaEvidenceProvider._resolve_hint() (refactored)
- Future: batch import, auto-scan
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .models import (
    AssetKind,
    CanonicalSource,
    CivitaiSelector,
    HuggingFaceSelector,
    SelectorStrategy,
)

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """What we learned about a file from remote lookups."""

    source: str  # "civitai_hash", "civitai_name", "huggingface", "filename_only"
    strategy: SelectorStrategy = SelectorStrategy.LOCAL_FILE
    canonical_source: Optional[CanonicalSource] = None
    civitai: Optional[CivitaiSelector] = None
    huggingface: Optional[HuggingFaceSelector] = None
    display_name: Optional[str] = None
    base_model: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


def enrich_by_hash(
    sha256: str,
    civitai_client: Any,
    kind: Optional[AssetKind] = None,
) -> Optional[EnrichmentResult]:
    """Look up a SHA256 hash on Civitai. Returns enrichment or None.

    Accepts both full SHA256 (64 chars) and short AutoV2 hashes (10 chars).
    """
    if civitai_client is None:
        return None

    try:
        result = civitai_client.get_model_by_hash(sha256)
        if not result:
            return None

        # CivitaiModelVersion is a dataclass — use getattr, not .get()
        model_id = getattr(result, "model_id", None)
        version_id = getattr(result, "id", None)
        display_name = getattr(result, "name", None)
        base_model = getattr(result, "base_model", None) or getattr(
            result, "baseModel", None
        )

        if not model_id or not version_id:
            return None

        file_id = _extract_file_id_from_version(result, sha256)

        return EnrichmentResult(
            source="civitai_hash",
            strategy=SelectorStrategy.CIVITAI_FILE,
            canonical_source=CanonicalSource(
                provider="civitai",
                model_id=model_id,
                version_id=version_id,
            ),
            civitai=CivitaiSelector(
                model_id=model_id,
                version_id=version_id,
                file_id=file_id,
            ),
            display_name=display_name,
            base_model=base_model,
        )
    except Exception as e:
        logger.debug("[enrichment] Hash lookup failed for %s: %s", sha256[:16], e)
        return None


def enrich_by_name(
    filename_stem: str,
    civitai_client: Any,
    kind: Optional[AssetKind] = None,
) -> Optional[EnrichmentResult]:
    """Search by filename stem on Civitai. Returns enrichment or None."""
    if civitai_client is None or not filename_stem or len(filename_stem) < 3:
        return None

    try:
        # Prefer Meilisearch (faster, better fuzzy matching)
        search_fn = getattr(civitai_client, "search_meilisearch", None)
        if search_fn is None:
            search_fn = getattr(civitai_client, "search_models", None)
        if search_fn is None:
            return None

        results = search_fn(query=filename_stem, limit=5)
        items = results.get("items", []) if isinstance(results, dict) else []
        if not items:
            return None

        stem_norm = _normalize_name(filename_stem)

        for item in items:
            item_name = item.get("name") or ""
            item_type = (item.get("type") or "").lower()
            model_id = item.get("id")

            if not model_id:
                continue

            # Kind compatibility check
            if kind and not _kind_matches_civitai_type(kind, item_type):
                continue

            # Name similarity check
            name_norm = _normalize_name(item_name)
            if stem_norm not in name_norm and name_norm not in stem_norm:
                continue

            # Get latest version
            version_id, file_id, base_model = _get_latest_version(
                civitai_client, model_id
            )
            if not version_id:
                continue

            return EnrichmentResult(
                source="civitai_name",
                strategy=SelectorStrategy.CIVITAI_FILE,
                canonical_source=CanonicalSource(
                    provider="civitai",
                    model_id=model_id,
                    version_id=version_id,
                ),
                civitai=CivitaiSelector(
                    model_id=model_id,
                    version_id=version_id,
                    file_id=file_id,
                ),
                display_name=item.get("name", filename_stem),
                base_model=base_model,
            )

    except Exception as e:
        logger.debug(
            "[enrichment] Name search failed for '%s': %s", filename_stem, e
        )

    return None


def enrich_file(
    sha256: str,
    filename: str,
    civitai_client: Any,
    kind: Optional[AssetKind] = None,
) -> EnrichmentResult:
    """Full enrichment pipeline: hash → name → filename-only fallback.

    Always returns a result — worst case is filename_only with display_name.
    """
    stem = extract_stem(filename)

    # 1. Hash lookup (most reliable)
    result = enrich_by_hash(sha256, civitai_client, kind)
    if result:
        return result

    # 2. Name search (fallback)
    result = enrich_by_name(stem, civitai_client, kind)
    if result:
        return result

    # 3. Filename-only fallback (always succeeds)
    return EnrichmentResult(
        source="filename_only",
        display_name=stem or filename,
    )


# --- Helpers ---


def extract_stem(filename: str) -> str:
    """Extract clean model name from filename.

    Examples:
        "ponyDiffusionV6XL.safetensors" → "ponyDiffusionV6XL"
        "sd_xl_turbo_1.0_fp16.safetensors" → "sd xl turbo 1.0 fp16"
    """
    stem = Path(filename).stem
    # Normalize separators for display
    return stem.replace("_", " ").replace("-", " ").strip()


def _normalize_name(name: str) -> str:
    """Normalize a name for comparison."""
    return name.lower().replace("_", " ").replace("-", " ")


def _kind_matches_civitai_type(kind: AssetKind, civitai_type: str) -> bool:
    """Check if an AssetKind matches a Civitai model type string."""
    kind_to_types = {
        AssetKind.CHECKPOINT: {"checkpoint", "model"},
        AssetKind.LORA: {"lora", "locon"},
        AssetKind.VAE: {"vae"},
        AssetKind.CONTROLNET: {"controlnet"},
        AssetKind.EMBEDDING: {"textualinversion", "embedding"},
        AssetKind.UPSCALER: {"upscaler"},
    }
    allowed = kind_to_types.get(kind, set())
    return civitai_type.lower() in allowed


def _extract_file_id_from_version(version_obj: Any, hash_value: str) -> Optional[int]:
    """Extract file_id from CivitaiModelVersion dataclass by matching hash."""
    files = getattr(version_obj, "files", [])
    for f in files:
        if isinstance(f, dict):
            hashes = f.get("hashes", {})
            for h in hashes.values():
                if isinstance(h, str) and h.lower() == hash_value.lower():
                    return f.get("id")
    # Fallback: first file
    if files and isinstance(files[0], dict):
        return files[0].get("id")
    return None


def _get_latest_version(
    civitai_client: Any, model_id: int
) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """Get (version_id, file_id, base_model) from latest model version."""
    try:
        model_data = civitai_client.get_model(model_id)
        if not model_data:
            return None, None, None

        versions = model_data.get("modelVersions", [])
        if not versions:
            return None, None, None

        latest = versions[0]
        version_id = latest.get("id")
        base_model = latest.get("baseModel")

        files = latest.get("files", [])
        file_id = files[0].get("id") if files else None

        return version_id, file_id, base_model
    except Exception:
        return None, None, None
