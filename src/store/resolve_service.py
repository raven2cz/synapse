"""
ResolveService — orchestration for dependency resolution.

9th service in Store facade. Suggest/Apply two-phase pattern.
Based on PLAN-Resolve-Model.md v0.7.1 section 11e.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

from .models import (
    AssetKind,
    DependencySelector,
    SelectorStrategy,
)
from .resolve_config import check_cross_kind_compatibility, get_kind_config, get_tier_for_confidence
from .resolve_models import (
    ApplyResult,
    CandidateSeed,
    EvidenceGroup,
    EvidenceHit,
    ManualResolveData,
    PreviewModelHint,
    ResolveContext,
    ResolutionCandidate,
    SuggestOptions,
    SuggestResult,
)
from .resolve_scoring import group_by_provenance, score_candidate
from .resolve_validation import validate_before_apply, validate_selector_fields

logger = logging.getLogger(__name__)

# Cache TTL: 5 minutes
CACHE_TTL_SECONDS = 300


@runtime_checkable
class CandidateCacheStore(Protocol):
    """Abstraction for candidate cache — injectable, testable."""

    def store(
        self, request_id: str, fingerprint: str,
        candidates: List[ResolutionCandidate],
    ) -> None: ...

    def get(
        self, request_id: str, candidate_id: str,
    ) -> Optional[ResolutionCandidate]: ...

    def check_fingerprint(
        self, request_id: str, fingerprint: str,
    ) -> bool: ...

    def cleanup_expired(self) -> None: ...


class InMemoryCandidateCache:
    """Default in-process cache. TTL 5min. With fingerprint check."""

    def __init__(self, ttl: float = CACHE_TTL_SECONDS):
        self._ttl = ttl
        self._store: Dict[str, Dict[str, Any]] = {}

    def store(
        self, request_id: str, fingerprint: str,
        candidates: List[ResolutionCandidate],
    ) -> None:
        self._store[request_id] = {
            "fingerprint": fingerprint,
            "candidates": {c.candidate_id: c for c in candidates},
            "stored_at": time.time(),
        }

    def get(
        self, request_id: str, candidate_id: str,
    ) -> Optional[ResolutionCandidate]:
        entry = self._store.get(request_id)
        if entry is None:
            return None
        if time.time() - entry["stored_at"] > self._ttl:
            del self._store[request_id]
            return None
        return entry["candidates"].get(candidate_id)

    def check_fingerprint(self, request_id: str, fingerprint: str) -> bool:
        entry = self._store.get(request_id)
        if entry is None:
            return False
        return entry["fingerprint"] == fingerprint

    def cleanup_expired(self) -> None:
        now = time.time()
        expired = [
            k for k, v in self._store.items()
            if now - v["stored_at"] > self._ttl
        ]
        for k in expired:
            del self._store[k]

    def find_by_candidate_id(
        self, candidate_id: str,
    ) -> Optional[ResolutionCandidate]:
        """Search all non-expired requests for a candidate by ID."""
        now = time.time()
        for entry in self._store.values():
            if now - entry["stored_at"] > self._ttl:
                continue
            c = entry["candidates"].get(candidate_id)
            if c:
                return c
        return None


class ResolveService:
    """Orchestration for dependency resolution.

    9th service in Store facade.
    Does NOT hold own clients — accesses through pack_service (R2).
    Does NOT know PackService backwards — unidirectional flow (R1).
    Avatar through getter callable (R3).
    """

    def __init__(
        self,
        layout: Any,  # StoreLayout
        pack_service: Any,  # PackService
        avatar_getter: Callable[[], Any] = lambda: None,
        providers: Optional[Dict[str, Any]] = None,
        candidate_cache: Optional[CandidateCacheStore] = None,
    ):
        self._layout = layout
        self._pack_service = pack_service
        self._avatar_getter = avatar_getter
        self._providers = providers
        self._cache = candidate_cache or InMemoryCandidateCache()

    def _ensure_providers(self) -> None:
        """Lazy init. Providers use getters, not direct references."""
        if self._providers is not None:
            return
        from .evidence_providers import (
            AIEvidenceProvider,
            AliasEvidenceProvider,
            FileMetaEvidenceProvider,
            HashEvidenceProvider,
            PreviewMetaEvidenceProvider,
            SourceMetaEvidenceProvider,
        )
        ps_getter = lambda: self._pack_service
        layout_getter = lambda: self._layout
        self._providers = {
            "hash_match": HashEvidenceProvider(ps_getter),
            "preview_meta": PreviewMetaEvidenceProvider(),
            "file_meta": FileMetaEvidenceProvider(),
            "alias": AliasEvidenceProvider(layout_getter),
            "source_meta": SourceMetaEvidenceProvider(),
            "ai": AIEvidenceProvider(self._avatar_getter),
        }

    def suggest(
        self,
        pack: Any,
        dep_id: str,
        options: Optional[SuggestOptions] = None,
    ) -> SuggestResult:
        """Suggest resolution candidates for a dependency.

        1. Build ResolveContext
        2. Run providers (by tier order, only supports()==True)
        3. Merge EvidenceHit by candidate.key
        4. Score (Noisy-OR with provenance grouping + tier ceiling)
        5. Sort, assign rank, cache
        6. Return SuggestResult
        """
        if options is None:
            options = SuggestOptions()

        self._ensure_providers()

        # Build context
        dep = _find_dependency(pack, dep_id)
        if dep is None:
            return SuggestResult(warnings=[f"Dependency {dep_id} not found"])

        kind = getattr(dep, "kind", AssetKind.UNKNOWN)
        if isinstance(kind, str):
            try:
                kind = AssetKind(kind)
            except ValueError:
                kind = AssetKind.UNKNOWN

        # Get preview hints — prefer override from import pipeline
        if options.preview_hints_override is not None:
            preview_hints = options.preview_hints_override
        else:
            preview_hints = getattr(dep, "_preview_hints", [])

        ctx = ResolveContext(
            pack=pack,
            dependency=dep,
            dep_id=dep_id,
            kind=kind,
            preview_hints=preview_hints,
            layout=self._layout,
        )

        # Gather evidence from all providers
        all_hits: List[EvidenceHit] = []
        warnings: List[str] = []

        # Sort providers by tier (lower tier = higher priority)
        sorted_providers = sorted(
            self._providers.items(),
            key=lambda p: getattr(p[1], "tier", 99),
        )

        for name, provider in sorted_providers:
            # Skip AI if not requested
            if name == "ai" and not options.include_ai:
                continue

            if not provider.supports(ctx):
                continue

            try:
                result = provider.gather(ctx)
                all_hits.extend(result.hits)
                warnings.extend(result.warnings)
                if result.error:
                    warnings.append(f"{name}: {result.error}")
            except Exception as e:
                warnings.append(f"Provider {name} failed: {e}")
                logger.warning("Provider %s failed: %s", name, e, exc_info=True)

        # Merge by candidate key and score
        candidates = self._merge_and_score(all_hits, kind, pack, options)

        # Build result
        fingerprint = _compute_pack_fingerprint(pack)
        result = SuggestResult(
            candidates=candidates[:options.max_candidates],
            pack_fingerprint=fingerprint,
            warnings=warnings,
        )

        # Cache for apply
        self._cache.store(result.request_id, fingerprint, result.candidates)

        return result

    def apply(
        self,
        pack_name: str,
        dep_id: str,
        candidate_id: str,
        request_id: Optional[str] = None,
    ) -> ApplyResult:
        """Apply a candidate from a previous suggest.

        1. Find candidate in cache (by request_id + candidate_id)
        2. Validate: min fields + cross-kind check
        3. Delegate to pack_service.apply_dependency_resolution()
        4. Return ApplyResult
        """
        # Find candidate
        candidate = None
        if request_id:
            candidate = self._cache.get(request_id, candidate_id)
        else:
            # Search all cached requests for this candidate_id
            candidate = self._find_candidate_in_cache(candidate_id)

        if candidate is None:
            return ApplyResult(
                success=False,
                message="Candidate not found or expired. Please re-run suggest.",
            )

        # Build selector from candidate
        selector = self._candidate_to_selector(candidate)

        # Check fingerprint staleness (warn but don't block)
        stale_warnings: List[str] = []
        if request_id and pack_name:
            try:
                pack_for_fp = self._pack_service.layout.load_pack(pack_name) if hasattr(self._pack_service, "layout") else None
                if pack_for_fp:
                    current_fp = _compute_pack_fingerprint(pack_for_fp)
                    if not self._cache.check_fingerprint(request_id, current_fp):
                        stale_warnings.append(
                            "Pack has changed since suggest was run. "
                            "Results may be stale — consider re-running suggest."
                        )
            except Exception:
                pass  # Non-critical check

        # Validate
        pack = self._pack_service.layout.load_pack(pack_name) if hasattr(self._pack_service, "layout") else None
        dep = _find_dependency(pack, dep_id) if pack else None
        kind = getattr(dep, "kind", AssetKind.UNKNOWN) if dep else AssetKind.UNKNOWN
        pack_base_model = getattr(pack, "base_model", None) if pack else None

        validation = validate_before_apply(
            selector, kind,
            pack_base_model=pack_base_model,
            candidate_base_model=None,  # TODO: extract from candidate
        )

        if not validation.success:
            return validation

        # Delegate write to pack_service
        try:
            if hasattr(self._pack_service, "apply_dependency_resolution"):
                self._pack_service.apply_dependency_resolution(
                    pack_name=pack_name,
                    dep_id=dep_id,
                    selector=selector,
                    canonical_source=candidate.canonical_source,
                    lock_entry=None,
                    display_name=candidate.display_name,
                )
            all_warnings = stale_warnings + (validation.compatibility_warnings or [])
            return ApplyResult(
                success=True,
                message="Resolution applied",
                compatibility_warnings=all_warnings,
            )
        except Exception as e:
            return ApplyResult(success=False, message=f"Apply failed: {e}")

    def apply_manual(
        self,
        pack_name: str,
        dep_id: str,
        manual: ManualResolveData,
    ) -> ApplyResult:
        """Apply manual resolve data. Same validation as apply."""
        selector = DependencySelector(
            strategy=manual.strategy,
            civitai=manual.civitai,
            huggingface=manual.huggingface,
            local_path=manual.local_path,
            url=manual.url,
            canonical_source=manual.canonical_source,
        )

        # Validate fields
        validation = validate_selector_fields(selector)
        if not validation.success:
            return validation

        # Delegate write
        try:
            if hasattr(self._pack_service, "apply_dependency_resolution"):
                self._pack_service.apply_dependency_resolution(
                    pack_name=pack_name,
                    dep_id=dep_id,
                    selector=selector,
                    canonical_source=manual.canonical_source,
                    lock_entry=None,
                    display_name=manual.display_name,
                )
            return ApplyResult(success=True, message="Manual resolution applied")
        except Exception as e:
            return ApplyResult(success=False, message=f"Apply failed: {e}")

    def _merge_and_score(
        self,
        hits: List[EvidenceHit],
        kind: AssetKind,
        pack: Any,
        options: SuggestOptions,
    ) -> List[ResolutionCandidate]:
        """Merge evidence hits by candidate key, score, and rank."""
        # Group hits by candidate key
        by_key: Dict[str, List[EvidenceHit]] = defaultdict(list)
        seeds: Dict[str, CandidateSeed] = {}

        for hit in hits:
            key = hit.candidate.key
            by_key[key].append(hit)
            if key not in seeds:
                seeds[key] = hit.candidate

        # Score each candidate
        candidates: List[ResolutionCandidate] = []
        pack_base_model = getattr(pack, "base_model", None)

        for key, key_hits in by_key.items():
            seed = seeds[key]
            groups = group_by_provenance(key_hits)
            group_list = list(groups.values())
            confidence = score_candidate(group_list)
            tier = get_tier_for_confidence(confidence)

            # Cross-kind compatibility check
            candidate_base_model = getattr(seed.selector, "base_model", None)
            compat_warnings = check_cross_kind_compatibility(
                pack_base_model, candidate_base_model, kind,
            )

            candidate = ResolutionCandidate(
                confidence=confidence,
                tier=tier,
                strategy=seed.selector.strategy,
                selector_data=seed.selector.model_dump(exclude_none=True),
                canonical_source=seed.canonical_source,
                evidence_groups=group_list,
                display_name=seed.display_name,
                display_description=seed.display_description,
                provider=seed.provider_name,
                compatibility_warnings=compat_warnings,
            )
            candidates.append(candidate)

        # Sort by confidence descending
        candidates.sort(key=lambda c: c.confidence, reverse=True)

        # Assign ranks
        for i, c in enumerate(candidates):
            c.rank = i + 1

        return candidates

    def _candidate_to_selector(
        self, candidate: ResolutionCandidate,
    ) -> DependencySelector:
        """Reconstruct DependencySelector from a candidate."""
        return DependencySelector(**{
            k: v for k, v in candidate.selector_data.items()
            if k in DependencySelector.model_fields
        })

    def _find_candidate_in_cache(
        self, candidate_id: str,
    ) -> Optional[ResolutionCandidate]:
        """Search all cached requests for a candidate.

        Falls back to linear search through known request_ids.
        Only works with InMemoryCandidateCache (known implementation).
        """
        cache = self._cache
        if isinstance(cache, InMemoryCandidateCache):
            return cache.find_by_candidate_id(candidate_id)
        return None


# --- Helpers ---

def _find_dependency(pack: Any, dep_id: str) -> Any:
    """Find a dependency by ID in a pack."""
    deps = getattr(pack, "dependencies", [])
    if not deps:
        return None
    for dep in deps:
        if getattr(dep, "id", None) == dep_id:
            return dep
    return None


def _compute_pack_fingerprint(pack: Any) -> str:
    """Compute a fingerprint for stale detection."""
    try:
        data = pack.model_dump() if hasattr(pack, "model_dump") else str(pack)
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]
    except Exception:
        return ""
