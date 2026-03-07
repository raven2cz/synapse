"""
Evidence providers — 6 providers for dependency resolution evidence gathering.

Based on PLAN-Resolve-Model.md v0.7.1 section 11d.

Providers:
- HashEvidenceProvider (E1, Tier 1): SHA256 lookup on Civitai/HF
- PreviewMetaEvidenceProvider (E2+E3, Tier 2): Preview metadata
- FileMetaEvidenceProvider (E5, Tier 3): Filename patterns
- AliasEvidenceProvider (E6, Tier 3): Configured aliases
- SourceMetaEvidenceProvider (E4, Tier 4): Civitai baseModel field
- AIEvidenceProvider (E7, Tier AI): AI-assisted analysis (ceiling 0.89)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from .models import AssetKind, DependencySelector, SelectorStrategy, CivitaiSelector
from .resolve_config import AI_CONFIDENCE_CEILING, get_kind_config
from .resolve_models import (
    CandidateSeed,
    EvidenceHit,
    EvidenceItem,
    PreviewModelHint,
    ProviderResult,
    ResolveContext,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class EvidenceProvider(Protocol):
    """Protocol for evidence providers.

    Same pattern as DependencyResolver — duck typing, @runtime_checkable.
    """

    @property
    def tier(self) -> int:
        """Confidence tier of this provider (1-4)."""
        ...

    def supports(self, context: ResolveContext) -> bool:
        """Whether this provider is relevant for the given context."""
        ...

    def gather(self, context: ResolveContext) -> ProviderResult:
        """Gather evidence. Returns hits with candidates + evidence."""
        ...


class HashEvidenceProvider:
    """E1: SHA256 lookup on Civitai + HuggingFace. Tier 1."""

    tier = 1

    def __init__(self, pack_service_getter: Callable):
        self._ps = pack_service_getter

    def supports(self, ctx: ResolveContext) -> bool:
        return True  # Always applicable if we have a hash

    def gather(self, ctx: ResolveContext) -> ProviderResult:
        """Look up hash from existing lock or Civitai file metadata."""
        hits = []
        warnings = []

        dep = ctx.dependency
        if dep is None:
            return ProviderResult()

        # Get SHA256 from lock data if available
        sha256 = None
        lock = getattr(dep, "lock", None)
        if lock:
            sha256 = getattr(lock, "sha256", None)

        if not sha256:
            return ProviderResult()

        pack_service = self._ps()
        if pack_service is None:
            return ProviderResult(error="PackService not available")

        # Try Civitai hash lookup
        civitai = getattr(pack_service, "civitai", None)
        if civitai:
            try:
                result = civitai.get_model_by_hash(sha256)
                if result:
                    model_id = result.get("modelId") or result.get("model_id")
                    version_id = result.get("id") or result.get("version_id")
                    file_id = _extract_file_id(result, sha256)
                    display_name = result.get("model", {}).get("name", "Unknown")

                    if model_id and version_id:
                        seed = CandidateSeed(
                            key=f"civitai:{model_id}:{version_id}",
                            selector=DependencySelector(
                                strategy=SelectorStrategy.CIVITAI_FILE,
                                civitai=CivitaiSelector(
                                    model_id=model_id,
                                    version_id=version_id,
                                    file_id=file_id,
                                ),
                            ),
                            display_name=display_name,
                            provider_name="civitai",
                        )
                        hits.append(EvidenceHit(
                            candidate=seed,
                            provenance=f"hash:{sha256[:12]}",
                            item=EvidenceItem(
                                source="hash_match",
                                description=f"SHA256 match on Civitai",
                                confidence=0.95,
                                raw_value=sha256,
                            ),
                        ))
            except Exception as e:
                warnings.append(f"Civitai hash lookup failed: {e}")

        # HF hash lookup (only if kind is eligible)
        kind_config = get_kind_config(ctx.kind)
        if kind_config.hf_hash_lookup:
            pass  # HF LFS pointer check — Phase 3+

        return ProviderResult(hits=hits, warnings=warnings)


class PreviewMetaEvidenceProvider:
    """E2+E3: Preview metadata (PNG embedded + API sidecar). Tier 2."""

    tier = 2

    def supports(self, ctx: ResolveContext) -> bool:
        return bool(ctx.preview_hints)

    def gather(self, ctx: ResolveContext) -> ProviderResult:
        """Convert preview hints to evidence hits with provenance grouping."""
        hits = []

        for hint in ctx.preview_hints:
            if not hint.resolvable:
                continue

            confidence = 0.85 if hint.source_type == "png_embedded" else 0.82
            source = ("preview_embedded" if hint.source_type == "png_embedded"
                      else "preview_api_meta")

            seed = CandidateSeed(
                key=f"preview:{hint.filename}",
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai=CivitaiSelector(model_id=0),  # Placeholder, needs search
                ),
                display_name=hint.filename,
                provider_name="civitai",
            )

            hits.append(EvidenceHit(
                candidate=seed,
                provenance=f"preview:{hint.source_image}",
                item=EvidenceItem(
                    source=source,
                    description=f"{hint.source_type}: {hint.filename}",
                    confidence=confidence,
                    raw_value=hint.raw_value,
                ),
            ))

        return ProviderResult(hits=hits)


class FileMetaEvidenceProvider:
    """E5: Filename patterns, architecture detection. Tier 3."""

    tier = 3

    def supports(self, ctx: ResolveContext) -> bool:
        return True

    def gather(self, ctx: ResolveContext) -> ProviderResult:
        """Extract evidence from filename patterns."""
        dep = ctx.dependency
        if dep is None:
            return ProviderResult()

        filename = getattr(dep, "filename", None) or getattr(dep, "name", None)
        if not filename:
            return ProviderResult()

        hits = []

        # Extract stem and try to match known patterns
        stem = _extract_stem(filename)
        if stem:
            seed = CandidateSeed(
                key=f"file:{stem}",
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai=CivitaiSelector(model_id=0),  # Needs search
                ),
                display_name=stem,
                provider_name="civitai",
            )
            hits.append(EvidenceHit(
                candidate=seed,
                provenance=f"file:{filename}",
                item=EvidenceItem(
                    source="file_metadata",
                    description=f"Filename stem: {stem}",
                    confidence=0.60,
                    raw_value=filename,
                ),
            ))

        return ProviderResult(hits=hits)


class AliasEvidenceProvider:
    """E6: Configured aliases (Civitai + HF targets). Tier 3."""

    tier = 3

    def __init__(self, layout_getter: Callable):
        self._layout = layout_getter

    def supports(self, ctx: ResolveContext) -> bool:
        return True

    def gather(self, ctx: ResolveContext) -> ProviderResult:
        """Look up configured aliases from store config."""
        layout = self._layout()
        if layout is None:
            return ProviderResult()

        # Read base_model_aliases from config
        aliases = _read_aliases(layout)
        if not aliases:
            return ProviderResult()

        dep = ctx.dependency
        if dep is None:
            return ProviderResult()

        # Check if dependency name matches an alias
        dep_name = getattr(dep, "name", None) or getattr(dep, "filename", None)
        base_model = getattr(dep, "base_model", None)

        hits = []
        for alias_key, alias_target in aliases.items():
            if dep_name and alias_key.lower() in dep_name.lower():
                hit = _alias_to_hit(alias_key, alias_target)
                if hit:
                    hits.append(hit)
            elif base_model and alias_key == base_model:
                hit = _alias_to_hit(alias_key, alias_target)
                if hit:
                    hits.append(hit)

        return ProviderResult(hits=hits)


class SourceMetaEvidenceProvider:
    """E4: Civitai baseModel field (hint only). Tier 4."""

    tier = 4

    def supports(self, ctx: ResolveContext) -> bool:
        return True

    def gather(self, ctx: ResolveContext) -> ProviderResult:
        """Use Civitai baseModel as a low-confidence hint."""
        dep = ctx.dependency
        if dep is None:
            return ProviderResult()

        base_model = getattr(dep, "base_model", None)
        if not base_model:
            return ProviderResult()

        seed = CandidateSeed(
            key=f"source_meta:{base_model}",
            selector=DependencySelector(
                strategy=SelectorStrategy.BASE_MODEL_HINT,
                base_model=base_model,
            ),
            display_name=base_model,
            provider_name="civitai",
        )

        return ProviderResult(hits=[
            EvidenceHit(
                candidate=seed,
                provenance=f"source:{base_model}",
                item=EvidenceItem(
                    source="source_metadata",
                    description=f"Civitai baseModel: {base_model}",
                    confidence=0.40,
                    raw_value=base_model,
                ),
            ),
        ])


class AIEvidenceProvider:
    """E7: AI-assisted analysis (MCP-backed). Ceiling 0.89."""

    tier = 2  # AI can be up to Tier 2

    def __init__(self, avatar_getter: Callable):
        self._get_avatar = avatar_getter

    def supports(self, ctx: ResolveContext) -> bool:
        avatar = self._get_avatar()
        return avatar is not None

    def gather(self, ctx: ResolveContext) -> ProviderResult:
        """Delegate to AI task service for dependency resolution."""
        avatar = self._get_avatar()
        if avatar is None:
            return ProviderResult(error="Avatar not available")

        try:
            result = avatar.execute_task("dependency_resolution", {
                "pack_name": getattr(ctx.pack, "name", ""),
                "dep_id": ctx.dep_id,
                "kind": ctx.kind.value if ctx.kind else "unknown",
            })

            hits = []
            if result and isinstance(result, dict):
                candidates = result.get("candidates", [])
                for c in candidates:
                    confidence = min(float(c.get("confidence", 0.5)), AI_CONFIDENCE_CEILING)
                    seed = CandidateSeed(
                        key=f"ai:{c.get('key', 'unknown')}",
                        selector=DependencySelector(
                            strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                            civitai=CivitaiSelector(
                                model_id=c.get("model_id", 0),
                            ),
                        ),
                        display_name=c.get("name", "AI suggestion"),
                        provider_name="civitai",
                    )
                    hits.append(EvidenceHit(
                        candidate=seed,
                        provenance=f"ai:{ctx.dep_id}",
                        item=EvidenceItem(
                            source="ai_analysis",
                            description=c.get("reasoning", "AI analysis"),
                            confidence=confidence,
                            raw_value=str(c),
                        ),
                    ))

            return ProviderResult(hits=hits)
        except Exception as e:
            return ProviderResult(error=f"AI analysis failed: {e}")


# --- Helpers ---

def _extract_file_id(version_data: dict, sha256: str) -> Optional[int]:
    """Extract file_id from Civitai version data by matching hash."""
    files = version_data.get("files", [])
    for f in files:
        hashes = f.get("hashes", {})
        if hashes.get("SHA256", "").lower() == sha256.lower():
            return f.get("id")
    return None


def _extract_stem(filename: str) -> Optional[str]:
    """Extract model stem from filename, removing version suffixes."""
    # Remove extension
    name = filename
    for ext in (".safetensors", ".ckpt", ".pt", ".pth", ".bin"):
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break

    if not name:
        return None

    return name


def _read_aliases(layout: Any) -> dict:
    """Read base_model_aliases from store config."""
    config_path = getattr(layout, "config_path", None)
    if not config_path:
        return {}

    try:
        import yaml
        config_file = config_path / "store.yaml"
        if not config_file.exists():
            return {}
        config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        return config.get("base_model_aliases", {})
    except Exception:
        return {}


def _alias_to_hit(alias_key: str, alias_target: dict) -> Optional[EvidenceHit]:
    """Convert an alias mapping to an EvidenceHit."""
    civitai = alias_target.get("civitai")
    if civitai and isinstance(civitai, dict):
        model_id = civitai.get("model_id")
        if model_id:
            seed = CandidateSeed(
                key=f"alias:{alias_key}",
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                    civitai=CivitaiSelector(model_id=model_id),
                ),
                display_name=alias_key,
                provider_name="civitai",
            )
            return EvidenceHit(
                candidate=seed,
                provenance=f"alias:{alias_key}",
                item=EvidenceItem(
                    source="alias_config",
                    description=f"Alias: {alias_key} → Civitai model {model_id}",
                    confidence=0.70,
                    raw_value=alias_key,
                ),
            )

    hf = alias_target.get("huggingface")
    if hf and isinstance(hf, dict):
        repo_id = hf.get("repo_id")
        if repo_id:
            from .models import HuggingFaceSelector
            seed = CandidateSeed(
                key=f"alias:{alias_key}",
                selector=DependencySelector(
                    strategy=SelectorStrategy.HUGGINGFACE_FILE,
                    huggingface=HuggingFaceSelector(
                        repo_id=repo_id,
                        filename=hf.get("filename", ""),
                    ),
                ),
                display_name=alias_key,
                provider_name="huggingface",
            )
            return EvidenceHit(
                candidate=seed,
                provenance=f"alias:{alias_key}",
                item=EvidenceItem(
                    source="alias_config",
                    description=f"Alias: {alias_key} → HF {repo_id}",
                    confidence=0.70,
                    raw_value=alias_key,
                ),
            )

    return None
