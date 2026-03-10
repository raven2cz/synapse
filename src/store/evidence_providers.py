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
                    # CivitaiModelVersion is a dataclass — use getattr, not .get()
                    model_id = getattr(result, "model_id", None) or getattr(result, "modelId", None)
                    version_id = getattr(result, "id", None)
                    file_id = _extract_file_id(result, sha256)
                    display_name = getattr(result, "name", "Unknown")

                    if model_id and version_id:
                        # Extract base_model from Civitai API response
                        candidate_base_model = (
                            getattr(result, "base_model", None)
                            or getattr(result, "baseModel", None)
                        )
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
                            base_model=candidate_base_model,
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

        # HF hash lookup (only if kind is eligible for HF hash check)
        kind_config = get_kind_config(ctx.kind)
        if kind_config.hf_hash_lookup:
            hf_hit = _hf_hash_lookup(pack_service, sha256, ctx)
            if hf_hit:
                hits.append(hf_hit)

        return ProviderResult(hits=hits, warnings=warnings)


class PreviewMetaEvidenceProvider:
    """E2+E3: Preview metadata (PNG embedded + API sidecar). Tier 2.

    Enriches preview hints with real Civitai model IDs via:
    1. Hash lookup (get_model_by_hash) — most reliable
    2. Name search (meilisearch/search_models) — fallback
    3. Placeholder (model_id=0) — last resort for AI/manual resolution
    """

    tier = 2

    def __init__(self, pack_service_getter: Optional[Callable] = None):
        self._ps = pack_service_getter

    def supports(self, ctx: ResolveContext) -> bool:
        return bool(ctx.preview_hints)

    def gather(self, ctx: ResolveContext) -> ProviderResult:
        """Convert preview hints to evidence hits, enriching with real IDs."""
        hits = []
        warnings = []

        civitai = self._get_civitai()
        # Cache resolved hashes to avoid duplicate API calls within one suggest
        hash_cache: dict[str, Optional[dict]] = {}

        for hint in ctx.preview_hints:
            if not hint.resolvable:
                continue

            confidence = 0.85 if hint.source_type == "png_embedded" else 0.82
            source = ("preview_embedded" if hint.source_type == "png_embedded"
                      else "preview_api_meta")

            # Try to resolve real Civitai IDs
            resolved = self._resolve_hint(hint, civitai, hash_cache, warnings)

            if resolved:
                model_id, version_id, file_id, display_name = resolved
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
                # Boost confidence when we have real IDs
                confidence = min(confidence + 0.05, 0.90)
            else:
                seed = CandidateSeed(
                    key=f"preview:{hint.filename}",
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                        civitai=CivitaiSelector(model_id=0),  # Unresolved
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

        return ProviderResult(hits=hits, warnings=warnings)

    def _get_civitai(self) -> Any:
        """Get Civitai client from pack_service, or None."""
        if self._ps is None:
            return None
        ps = self._ps()
        if ps is None:
            return None
        return getattr(ps, "civitai", None)

    def _resolve_hint(
        self,
        hint: PreviewModelHint,
        civitai: Any,
        hash_cache: dict,
        warnings: list,
    ) -> Optional[tuple]:
        """Try to resolve a hint to (model_id, version_id, file_id, display_name).

        Strategy:
        1. Hash lookup (most reliable, single API call)
        2. Name search via Meilisearch (fallback)
        """
        if civitai is None:
            return None

        # 1. Hash lookup
        if hint.hash:
            result = self._lookup_by_hash(hint.hash, civitai, hash_cache, warnings)
            if result:
                return result

        # 2. Name search fallback
        return self._search_by_name(hint, civitai, warnings)

    def _lookup_by_hash(
        self,
        hash_value: str,
        civitai: Any,
        hash_cache: dict,
        warnings: list,
    ) -> Optional[tuple]:
        """Look up model by hash, with caching."""
        if hash_value in hash_cache:
            cached = hash_cache[hash_value]
            if cached is None:
                return None
            return cached

        try:
            result = civitai.get_model_by_hash(hash_value)
            if result:
                # CivitaiModelVersion is a dataclass — use attrs, not .get()
                model_id = getattr(result, "model_id", None)
                version_id = getattr(result, "id", None)
                display_name = getattr(result, "name", "Unknown")
                file_id = _extract_file_id_from_version(result, hash_value)

                if model_id and version_id:
                    resolved = (model_id, version_id, file_id, display_name)
                    hash_cache[hash_value] = resolved
                    return resolved

            hash_cache[hash_value] = None
        except Exception as e:
            warnings.append(f"Preview hash lookup failed for {hash_value[:10]}: {e}")
            hash_cache[hash_value] = None

        return None

    def _search_by_name(
        self,
        hint: PreviewModelHint,
        civitai: Any,
        warnings: list,
    ) -> Optional[tuple]:
        """Search Civitai by model name extracted from hint."""
        # Build search query from filename stem
        stem = _extract_stem(hint.filename)
        if not stem or len(stem) < 3:
            return None

        try:
            # Prefer Meilisearch (faster, better fuzzy matching)
            search_fn = getattr(civitai, "search_meilisearch", None)
            if search_fn is None:
                search_fn = getattr(civitai, "search_models", None)
            if search_fn is None:
                return None

            results = search_fn(query=stem, limit=5)
            items = results.get("items", []) if isinstance(results, dict) else []

            if not items:
                return None

            # Find best match: prefer exact name match, then kind match
            for item in items:
                item_name = (item.get("name") or "").lower()
                item_type = (item.get("type") or "").lower()
                model_id = item.get("id")

                if not model_id:
                    continue

                # Check kind compatibility
                if hint.kind and not _kind_matches_civitai_type(hint.kind, item_type):
                    continue

                # Check name similarity (normalize underscores/spaces for comparison)
                stem_norm = stem.lower().replace("_", " ").replace("-", " ")
                name_norm = item_name.replace("_", " ").replace("-", " ")
                if stem_norm not in name_norm and name_norm not in stem_norm:
                    continue

                # Get latest version from model details
                version_id = None
                file_id = None
                try:
                    model_data = civitai.get_model(model_id)
                    if model_data:
                        versions = model_data.get("modelVersions", [])
                        if versions:
                            latest = versions[0]
                            version_id = latest.get("id")
                            files = latest.get("files", [])
                            if files:
                                file_id = files[0].get("id")
                except Exception:
                    pass

                if version_id:
                    display_name = item.get("name", stem)
                    return (model_id, version_id, file_id, display_name)

        except Exception as e:
            logger.debug("[preview-provider] Name search failed for '%s': %s", stem, e)

        return None


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
    """E7: AI-assisted analysis (MCP-backed). Ceiling 0.89.

    Delegates to AvatarTaskService.execute_task("dependency_resolution", ...)
    which uses MCP tools (search_civitai, analyze_civitai_model,
    search_huggingface, find_model_by_hash) to find matching models.

    Input is formatted as structured text matching the format expected by
    config/avatar/skills/model-resolution.md.
    """

    tier = 2  # AI can reach up to Tier 2

    def __init__(self, avatar_getter: Callable):
        self._get_avatar = avatar_getter

    def supports(self, ctx: ResolveContext) -> bool:
        return self._get_avatar() is not None

    def gather(self, ctx: ResolveContext) -> ProviderResult:
        """Build structured input, call AI task, convert candidates to hits."""
        avatar = self._get_avatar()
        if avatar is None:
            return ProviderResult(error="Avatar not available")

        try:
            input_text = _build_ai_input(ctx)
            task_result = avatar.execute_task("dependency_resolution", input_text)

            if not task_result.success:
                return ProviderResult(
                    error=f"AI task failed: {task_result.error}",
                    warnings=[f"AI analysis failed: {task_result.error}"],
                )

            output = task_result.output
            if not isinstance(output, dict):
                return ProviderResult(warnings=["AI returned non-dict output"])

            candidates = output.get("candidates", [])
            if not isinstance(candidates, list):
                return ProviderResult(warnings=["AI returned invalid candidates"])

            hits = []
            for c in candidates:
                hit = _ai_candidate_to_hit(c, ctx.dep_id)
                if hit:
                    hits.append(hit)

            summary = output.get("search_summary", "")
            warnings = [f"AI search: {summary}"] if summary else []

            return ProviderResult(hits=hits, warnings=warnings)
        except Exception as e:
            logger.warning("[ai-provider] gather failed: %s", e, exc_info=True)
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


def _extract_first_file_id(version_data: dict) -> Optional[int]:
    """Extract file_id of the primary (first) file from version data."""
    files = version_data.get("files", [])
    if files:
        return files[0].get("id")
    return None


def _extract_file_id_from_version(version_obj: Any, hash_value: str) -> Optional[int]:
    """Extract file_id from CivitaiModelVersion dataclass by matching hash."""
    files = getattr(version_obj, "files", [])
    for f in files:
        if isinstance(f, dict):
            hashes = f.get("hashes", {})
            for h in hashes.values():
                if isinstance(h, str) and h.lower() == hash_value.lower():
                    return f.get("id")
    # Fallback: return first file id
    if files and isinstance(files[0], dict):
        return files[0].get("id")
    return None


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


def _hf_hash_lookup(
    pack_service: Any, sha256: str, ctx: ResolveContext
) -> Optional[EvidenceHit]:
    """Check if a SHA256 matches an LFS file in a known HF repo.

    Only works when the dependency already has a HuggingFace selector
    (from alias or previous resolve). HF has no reverse hash lookup API,
    so we verify against the specific repo/file referenced in the selector.
    """
    dep = ctx.dependency
    selector = getattr(dep, "selector", None)
    if not selector:
        return None

    hf_sel = getattr(selector, "huggingface", None)
    if not hf_sel:
        return None

    repo_id = getattr(hf_sel, "repo_id", None)
    filename = getattr(hf_sel, "filename", None)
    if not repo_id or not filename:
        return None

    hf_client = getattr(pack_service, "huggingface", None)
    if hf_client is None:
        return None

    try:
        repo_info = hf_client.get_repo_files(repo_id)
        for file_info in repo_info.files:
            if file_info.filename == filename and file_info.sha256:
                if file_info.sha256.lower() == sha256.lower():
                    from .models import HuggingFaceSelector
                    seed = CandidateSeed(
                        key=f"hf:{repo_id}:{filename}",
                        selector=DependencySelector(
                            strategy=SelectorStrategy.HUGGINGFACE_FILE,
                            huggingface=HuggingFaceSelector(
                                repo_id=repo_id,
                                filename=filename,
                                revision=getattr(hf_sel, "revision", None) or "main",
                            ),
                        ),
                        display_name=f"{repo_id}/{filename}",
                        provider_name="huggingface",
                    )
                    return EvidenceHit(
                        candidate=seed,
                        provenance=f"hash:{sha256[:12]}",
                        item=EvidenceItem(
                            source="hash_match",
                            description="SHA256 match on HuggingFace LFS",
                            confidence=0.95,
                            raw_value=sha256,
                        ),
                    )
    except Exception as e:
        logger.debug("[hash-provider] HF LFS hash check failed: %s", e)

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


# --- AI helpers ---

def _build_ai_input(ctx: ResolveContext) -> str:
    """Build structured text input for the AI dependency resolution task.

    Matches the format expected by config/avatar/skills/model-resolution.md.
    """
    pack = ctx.pack
    dep = ctx.dependency
    kind = ctx.kind.value if ctx.kind else "unknown"

    lines = ["PACK INFO:"]
    lines.append(f"  name: {getattr(pack, 'name', 'unknown')}")
    lines.append(f"  type: {getattr(pack, 'type', 'unknown')}")
    lines.append(f"  base_model: {getattr(pack, 'base_model', None)}")

    desc = getattr(pack, 'description', '') or ''
    lines.append(f"  description: {desc[:500]}")

    tags = getattr(pack, 'tags', []) or []
    lines.append(f"  tags: [{', '.join(str(t) for t in tags[:20])}]")

    lines.append("")
    lines.append("DEPENDENCY TO RESOLVE:")
    lines.append(f"  id: {ctx.dep_id}")
    lines.append(f"  kind: {kind}")

    # hint: base_model from selector or pack-level base_model
    selector = getattr(dep, 'selector', None)
    hint = None
    if selector:
        hint = getattr(selector, 'base_model', None)
    if not hint:
        hint = getattr(pack, 'base_model', None)
    lines.append(f"  hint: {hint}")

    expose = getattr(dep, 'expose', None)
    expose_fn = getattr(expose, 'filename', None) if expose else None
    lines.append(f"  expose_filename: {expose_fn}")

    # Preview hints
    if ctx.preview_hints:
        lines.append("")
        lines.append("PREVIEW HINTS:")
        for hint_item in ctx.preview_hints:
            src = getattr(hint_item, 'source_image', 'unknown')
            fn = getattr(hint_item, 'filename', '')
            raw = getattr(hint_item, 'raw_value', '')
            lines.append(f"  - {src}: model=\"{fn}\", raw=\"{raw}\"")
    else:
        lines.append("")
        lines.append("EXISTING EVIDENCE (from rule-based providers):")
        lines.append("  (none)")

    return "\n".join(lines)


def _ai_candidate_to_hit(
    candidate: dict, dep_id: str
) -> Optional[EvidenceHit]:
    """Convert a single AI candidate dict to an EvidenceHit.

    Supports both civitai and huggingface providers.
    """
    if not isinstance(candidate, dict):
        return None

    provider = candidate.get("provider", "")
    display_name = candidate.get("display_name", "AI suggestion")
    confidence = candidate.get("confidence", 0.0)
    reasoning = candidate.get("reasoning", "AI analysis")

    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    confidence = min(float(confidence), AI_CONFIDENCE_CEILING)

    if provider == "civitai":
        model_id = candidate.get("model_id")
        if not model_id:
            return None
        version_id = candidate.get("version_id")
        file_id = candidate.get("file_id")

        # Use CIVITAI_FILE if we have version+file, otherwise CIVITAI_MODEL_LATEST
        if version_id and file_id:
            strategy = SelectorStrategy.CIVITAI_FILE
        else:
            strategy = SelectorStrategy.CIVITAI_MODEL_LATEST

        seed = CandidateSeed(
            key=f"civitai:{model_id}:{version_id or 'latest'}",
            selector=DependencySelector(
                strategy=strategy,
                civitai=CivitaiSelector(
                    model_id=model_id,
                    version_id=version_id,
                    file_id=file_id,
                ),
            ),
            display_name=display_name,
            provider_name="civitai",
        )
    elif provider == "huggingface":
        from .models import HuggingFaceSelector
        repo_id = candidate.get("repo_id")
        filename = candidate.get("filename")
        if not repo_id or not filename:
            return None

        seed = CandidateSeed(
            key=f"hf:{repo_id}:{filename}",
            selector=DependencySelector(
                strategy=SelectorStrategy.HUGGINGFACE_FILE,
                huggingface=HuggingFaceSelector(
                    repo_id=repo_id,
                    filename=filename,
                    revision=candidate.get("revision", "main"),
                ),
            ),
            display_name=display_name,
            provider_name="huggingface",
        )
    else:
        return None

    return EvidenceHit(
        candidate=seed,
        provenance=f"ai:{dep_id}",
        item=EvidenceItem(
            source="ai_analysis",
            description=reasoning,
            confidence=confidence,
            raw_value=str(candidate),
        ),
    )
