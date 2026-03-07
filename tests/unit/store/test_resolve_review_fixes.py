"""
Tests for review fixes — tier boundary gaps, zero-value validation,
fingerprint stale check, atomic cache write.

These tests verify all fixes from the Gemini/Codex/Claude review cycle.
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.store.models import (
    AssetKind,
    CivitaiSelector,
    DependencySelector,
    HuggingFaceSelector,
    SelectorStrategy,
)
from src.store.resolve_config import get_tier_for_confidence
from src.store.resolve_models import (
    ApplyResult,
    CandidateSeed,
    EvidenceGroup,
    EvidenceHit,
    EvidenceItem,
    ManualResolveData,
    ProviderResult,
    ResolutionCandidate,
    SuggestOptions,
)
from src.store.resolve_scoring import score_candidate
from src.store.resolve_service import InMemoryCandidateCache, ResolveService
from src.store.resolve_validation import validate_selector_fields
from src.store.hash_cache import HashCache
from src.store.models import (
    ExposeConfig,
    Pack,
    PackDependency,
    PackSource,
    ProviderName,
)


# =============================================================================
# Fix 1: Tier boundary gaps — values between tier ranges must not fall to T4
# =============================================================================

class TestTierBoundaryGaps:
    """Gemini issue 1.1: confidence values in gaps between tiers."""

    @pytest.mark.parametrize("confidence,expected_tier", [
        # Exact boundaries
        (0.90, 1),
        (0.75, 2),
        (0.50, 3),
        (0.30, 4),
        # Gap values — MUST NOT fall to tier 4
        (0.895, 2),   # Between T1 min (0.90) and T2 max (0.89)
        (0.745, 3),   # Between T2 min (0.75) and T3 max (0.74)
        (0.495, 4),   # Between T3 min (0.50) and T4 max (0.49)
        # Near-boundary
        (0.899, 2),
        (0.901, 1),
        (0.749, 3),
        (0.751, 2),
        (0.499, 4),
        (0.501, 3),
        (0.299, 4),   # Below T4 min
        (0.001, 4),
        (1.001, 1),   # Above T1 max
    ])
    def test_no_gap_fallthrough(self, confidence, expected_tier):
        """Every confidence value must map to the correct tier, no gaps."""
        assert get_tier_for_confidence(confidence) == expected_tier

    def test_monotonic_tier_assignment(self):
        """Tiers must be monotonically non-increasing as confidence rises."""
        prev_tier = 4
        for c in [i / 100.0 for i in range(0, 105)]:
            tier = get_tier_for_confidence(c)
            assert tier <= prev_tier, (
                f"Tier went UP from {prev_tier} to {tier} at confidence {c}"
            )
            prev_tier = tier


# =============================================================================
# Fix 2: model_id=0 rejected by validation
# =============================================================================

class TestZeroValueValidation:
    """Codex issue 3: model_id=0 placeholders must not pass validation."""

    def test_civitai_model_id_zero_rejected(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
            civitai=CivitaiSelector(model_id=0),
        )
        result = validate_selector_fields(sel)
        assert result.success is False
        assert "zero" in result.message.lower()

    def test_civitai_file_version_id_zero_rejected(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=123, version_id=0, file_id=456),
        )
        result = validate_selector_fields(sel)
        assert result.success is False

    def test_civitai_file_all_valid_passes(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=1, version_id=2, file_id=3),
        )
        result = validate_selector_fields(sel)
        assert result.success is True

    def test_nonzero_ids_pass(self):
        """Normal IDs should pass validation."""
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
            civitai=CivitaiSelector(model_id=133005),
        )
        result = validate_selector_fields(sel)
        assert result.success is True

    def test_apply_manual_with_zero_model_id_fails(self):
        """apply_manual should reject selectors with model_id=0."""
        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
        )
        manual = ManualResolveData(
            strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
            civitai=CivitaiSelector(model_id=0),
            display_name="Placeholder",
        )
        result = service.apply_manual("pack", "dep_001", manual)
        assert result.success is False


# =============================================================================
# Fix 3: Fingerprint stale warning in apply()
# =============================================================================

class TestFingerprintStaleWarning:
    """Codex issue 6: apply() must warn when pack changed since suggest."""

    def _setup_service_with_suggest(self, pack_v1, pack_v2):
        """Create a service, run suggest on pack_v1, return service + suggest result."""
        hit = EvidenceHit(
            candidate=CandidateSeed(
                key="civitai:1:2",
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=CivitaiSelector(model_id=1, version_id=2, file_id=3),
                ),
                display_name="Test",
                provider_name="civitai",
            ),
            provenance="hash:abc123",
            item=EvidenceItem(
                source="hash_match", description="SHA match", confidence=0.95,
            ),
        )
        provider = MagicMock()
        provider.tier = 1
        provider.supports.return_value = True
        provider.gather.return_value = ProviderResult(hits=[hit])

        ps = MagicMock()
        ps.layout.load_pack.return_value = pack_v2  # Return v2 on apply
        ps.apply_dependency_resolution = MagicMock()

        service = ResolveService(
            layout=MagicMock(),
            pack_service=ps,
            providers={"hash": provider},
        )
        suggest_result = service.suggest(pack_v1, "dep_001")
        return service, suggest_result

    def test_stale_fingerprint_produces_warning(self):
        """When pack changes between suggest and apply, warn."""
        dep = MagicMock()
        dep.id = "dep_001"
        dep.kind = AssetKind.CHECKPOINT
        dep._preview_hints = []

        pack_v1 = MagicMock()
        pack_v1.name = "test"
        pack_v1.base_model = "SDXL"
        pack_v1.dependencies = [dep]
        pack_v1.model_dump.return_value = {"name": "test", "version": "v1"}

        pack_v2 = MagicMock()
        pack_v2.name = "test"
        pack_v2.base_model = "SDXL"
        pack_v2.dependencies = [dep]
        pack_v2.model_dump.return_value = {"name": "test", "version": "v2"}  # Changed!

        service, suggest_result = self._setup_service_with_suggest(pack_v1, pack_v2)

        cid = suggest_result.candidates[0].candidate_id
        apply_result = service.apply(
            "test", "dep_001", cid,
            request_id=suggest_result.request_id,
        )

        assert apply_result.success is True
        # Should have stale warning
        assert any("stale" in w.lower() for w in (apply_result.compatibility_warnings or []))

    def test_same_fingerprint_no_warning(self):
        """When pack unchanged, no stale warning."""
        dep = MagicMock()
        dep.id = "dep_001"
        dep.kind = AssetKind.CHECKPOINT
        dep._preview_hints = []

        pack = MagicMock()
        pack.name = "test"
        pack.base_model = "SDXL"
        pack.dependencies = [dep]
        pack.model_dump.return_value = {"name": "test", "version": "v1"}

        service, suggest_result = self._setup_service_with_suggest(pack, pack)

        cid = suggest_result.candidates[0].candidate_id
        apply_result = service.apply(
            "test", "dep_001", cid,
            request_id=suggest_result.request_id,
        )

        assert apply_result.success is True
        # No stale warnings (but there might be other compatibility warnings)
        stale = [w for w in (apply_result.compatibility_warnings or []) if "stale" in w.lower()]
        assert stale == []


# =============================================================================
# Fix 4: Atomic hash cache write
# =============================================================================

class TestAtomicCacheWrite:
    """Gemini issue 3.1: hash cache must use atomic write (temp + rename)."""

    def test_no_tmp_file_after_save(self, tmp_path):
        """After successful save, .tmp file should not remain."""
        registry = tmp_path / "registry"
        registry.mkdir()
        model_file = tmp_path / "model.safetensors"
        model_file.write_bytes(b"test data")

        cache = HashCache(registry)
        cache.compute_and_cache(model_file)
        cache.save()

        assert (registry / "local_model_hashes.json").exists()
        assert not (registry / "local_model_hashes.json.tmp").exists()

    def test_save_produces_valid_json(self, tmp_path):
        """Saved file must be valid JSON."""
        registry = tmp_path / "registry"
        registry.mkdir()
        model_file = tmp_path / "model.safetensors"
        model_file.write_bytes(b"test data")

        cache = HashCache(registry)
        cache.compute_and_cache(model_file)
        cache.save()

        data = json.loads((registry / "local_model_hashes.json").read_text())
        assert str(model_file) in data
        entry = data[str(model_file)]
        assert "sha256" in entry
        assert "mtime" in entry
        assert "size" in entry
        assert entry["size"] == len(b"test data")

    def test_round_trip_after_atomic_save(self, tmp_path):
        """Data must survive save → reload cycle."""
        registry = tmp_path / "registry"
        registry.mkdir()
        f1 = tmp_path / "a.safetensors"
        f2 = tmp_path / "b.safetensors"
        f1.write_bytes(b"data A")
        f2.write_bytes(b"data B")

        cache1 = HashCache(registry)
        h1 = cache1.compute_and_cache(f1)
        h2 = cache1.compute_and_cache(f2)
        cache1.save()

        cache2 = HashCache(registry)
        assert cache2.get(f1) == h1
        assert cache2.get(f2) == h2
        assert cache2.size == 2


# =============================================================================
# Fix 5: Scoring pipeline — spec examples verified
# =============================================================================

class TestScoringSpecExamples:
    """Verify PLAN-Resolve-Model.md spec examples produce correct scores."""

    def test_single_hash_match(self):
        """E1 hash match alone → confidence 0.95, tier 1."""
        groups = [
            EvidenceGroup(
                provenance="hash:abc123",
                items=[EvidenceItem(
                    source="hash_match", description="SHA256 match",
                    confidence=0.95,
                )],
                combined_confidence=0.95,
            ),
        ]
        score = score_candidate(groups)
        assert score == pytest.approx(0.95)
        assert get_tier_for_confidence(score) == 1

    def test_two_preview_images_capped_at_tier2(self):
        """Two preview images → Noisy-OR exceeds 0.89, capped at T2 ceiling."""
        groups = [
            EvidenceGroup(
                provenance="preview:001.png",
                items=[EvidenceItem(
                    source="preview_embedded", description="PNG tEXt",
                    confidence=0.85,
                )],
                combined_confidence=0.85,
            ),
            EvidenceGroup(
                provenance="preview:002.png",
                items=[EvidenceItem(
                    source="preview_api_meta", description="API meta",
                    confidence=0.82,
                )],
                combined_confidence=0.82,
            ),
        ]
        score = score_candidate(groups)
        # Noisy-OR: 1 - (1-0.85)*(1-0.82) = 1 - 0.15*0.18 = 0.973
        # Ceiling: best evidence=T2, cap=0.89
        assert score == pytest.approx(0.89)

    def test_hash_plus_preview_combines(self):
        """Hash (T1) + preview (T2) → ceiling lifted to 1.0, Noisy-OR applies."""
        groups = [
            EvidenceGroup(
                provenance="hash:abc",
                items=[EvidenceItem(
                    source="hash_match", description="SHA match", confidence=0.95,
                )],
                combined_confidence=0.95,
            ),
            EvidenceGroup(
                provenance="preview:001.png",
                items=[EvidenceItem(
                    source="preview_embedded", description="PNG", confidence=0.85,
                )],
                combined_confidence=0.85,
            ),
        ]
        score = score_candidate(groups)
        # Noisy-OR: 1 - (0.05)*(0.15) = 0.9925
        # Ceiling: T1 → 1.0
        assert score == pytest.approx(0.9925, abs=0.001)
        assert get_tier_for_confidence(score) == 1

    def test_file_meta_alone_capped_at_tier3(self):
        """File metadata alone: confidence 0.60, tier 3, ceiling 0.74."""
        groups = [
            EvidenceGroup(
                provenance="file:model_name",
                items=[EvidenceItem(
                    source="file_metadata", description="stem",
                    confidence=0.60,
                )],
                combined_confidence=0.60,
            ),
        ]
        score = score_candidate(groups)
        assert score == pytest.approx(0.60)
        assert get_tier_for_confidence(score) == 3

    def test_source_meta_hint_only(self):
        """Source metadata: confidence 0.40, tier 4 — hint only."""
        groups = [
            EvidenceGroup(
                provenance="source:SDXL",
                items=[EvidenceItem(
                    source="source_metadata", description="baseModel",
                    confidence=0.40,
                )],
                combined_confidence=0.40,
            ),
        ]
        score = score_candidate(groups)
        assert score == pytest.approx(0.40)
        assert get_tier_for_confidence(score) == 4

    def test_ai_evidence_capped_at_089(self):
        """AI evidence with 0.89 confidence stays in T2."""
        groups = [
            EvidenceGroup(
                provenance="ai:dep_001",
                items=[EvidenceItem(
                    source="ai_analysis", description="AI",
                    confidence=0.89,
                )],
                combined_confidence=0.89,
            ),
        ]
        score = score_candidate(groups)
        assert score == pytest.approx(0.89)
        assert get_tier_for_confidence(score) == 2


# =============================================================================
# Fix 6: Full suggest→apply round-trip with realistic data
# =============================================================================

class TestSuggestApplyRoundTrip:
    """End-to-end suggest→apply with realistic candidate data."""

    def _make_service(self, pack, hits):
        provider = MagicMock()
        provider.tier = 1
        provider.supports.return_value = True
        provider.gather.return_value = ProviderResult(hits=hits)

        ps = MagicMock()
        ps.layout.load_pack.return_value = pack
        ps.apply_dependency_resolution = MagicMock()

        return ResolveService(
            layout=MagicMock(),
            pack_service=ps,
            providers={"test": provider},
        ), ps

    def _make_dep_and_pack(self):
        dep = MagicMock()
        dep.id = "lora_001"
        dep.kind = AssetKind.LORA
        dep.filename = "detail_tweaker.safetensors"
        dep.name = "detail_tweaker.safetensors"
        dep.base_model = "SDXL"
        dep.lock = None
        dep._preview_hints = []

        pack = MagicMock()
        pack.name = "my_sdxl_pack"
        pack.base_model = "SDXL"
        pack.dependencies = [dep]
        pack.model_dump.return_value = {"name": "my_sdxl_pack"}
        return dep, pack

    def test_suggest_returns_ranked_candidates(self):
        dep, pack = self._make_dep_and_pack()

        hits = [
            EvidenceHit(
                candidate=CandidateSeed(
                    key="civitai:100:200",
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_FILE,
                        civitai=CivitaiSelector(model_id=100, version_id=200, file_id=300),
                    ),
                    display_name="Detail Tweaker XL",
                    provider_name="civitai",
                ),
                provenance="hash:abc123",
                item=EvidenceItem(
                    source="hash_match", description="SHA256 match", confidence=0.95,
                ),
            ),
            EvidenceHit(
                candidate=CandidateSeed(
                    key="civitai:101:201",
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                        civitai=CivitaiSelector(model_id=101),
                    ),
                    display_name="Detail Tweaker Alt",
                    provider_name="civitai",
                ),
                provenance="file:detail_tweaker",
                item=EvidenceItem(
                    source="file_metadata", description="stem match", confidence=0.60,
                ),
            ),
        ]

        service, _ = self._make_service(pack, hits)
        result = service.suggest(pack, "lora_001")

        assert len(result.candidates) == 2
        # Best candidate first
        assert result.candidates[0].confidence > result.candidates[1].confidence
        assert result.candidates[0].rank == 1
        assert result.candidates[1].rank == 2
        # First candidate: hash match T1
        assert result.candidates[0].tier == 1
        assert result.candidates[0].display_name == "Detail Tweaker XL"

    def test_apply_after_suggest_calls_pack_service(self):
        dep, pack = self._make_dep_and_pack()

        hits = [
            EvidenceHit(
                candidate=CandidateSeed(
                    key="civitai:100:200",
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_FILE,
                        civitai=CivitaiSelector(model_id=100, version_id=200, file_id=300),
                    ),
                    display_name="Detail Tweaker XL",
                    provider_name="civitai",
                ),
                provenance="hash:abc",
                item=EvidenceItem(
                    source="hash_match", description="test", confidence=0.95,
                ),
            ),
        ]

        service, ps = self._make_service(pack, hits)
        suggest = service.suggest(pack, "lora_001")

        cid = suggest.candidates[0].candidate_id
        apply_result = service.apply(
            "my_sdxl_pack", "lora_001", cid,
            request_id=suggest.request_id,
        )

        assert apply_result.success is True
        ps.apply_dependency_resolution.assert_called_once()
        call_kwargs = ps.apply_dependency_resolution.call_args
        assert call_kwargs.kwargs["pack_name"] == "my_sdxl_pack"
        assert call_kwargs.kwargs["dep_id"] == "lora_001"
        selector = call_kwargs.kwargs["selector"]
        assert selector.strategy == SelectorStrategy.CIVITAI_FILE
        assert selector.civitai.model_id == 100
        assert selector.civitai.version_id == 200
        assert selector.civitai.file_id == 300

    def test_apply_expired_candidate_fails(self):
        dep, pack = self._make_dep_and_pack()

        hit = EvidenceHit(
            candidate=CandidateSeed(
                key="civitai:1:2",
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=CivitaiSelector(model_id=1, version_id=2, file_id=3),
                ),
                display_name="Test",
                provider_name="civitai",
            ),
            provenance="hash:abc",
            item=EvidenceItem(source="hash_match", description="t", confidence=0.95),
        )

        # Use very short TTL cache
        cache = InMemoryCandidateCache(ttl=0.01)
        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"test": MagicMock(tier=1, supports=MagicMock(return_value=True),
                                         gather=MagicMock(return_value=ProviderResult(hits=[hit])))},
            candidate_cache=cache,
        )

        suggest = service.suggest(pack, "lora_001")
        cid = suggest.candidates[0].candidate_id

        # Wait for cache to expire
        time.sleep(0.02)

        result = service.apply("pack", "lora_001", cid, request_id=suggest.request_id)
        assert result.success is False
        assert "expired" in result.message.lower() or "not found" in result.message.lower()

    def test_suggest_with_no_matching_providers_returns_empty(self):
        dep, pack = self._make_dep_and_pack()

        # Provider that doesn't support this context
        unsupported = MagicMock()
        unsupported.tier = 1
        unsupported.supports.return_value = False

        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"unsupported": unsupported},
        )
        result = service.suggest(pack, "lora_001")
        assert result.candidates == []

    def test_candidate_id_is_stable_uuid(self):
        """Each candidate gets a unique UUID, not index-based."""
        dep, pack = self._make_dep_and_pack()

        hits = [
            EvidenceHit(
                candidate=CandidateSeed(
                    key=f"civitai:{i}:{i}",
                    selector=DependencySelector(
                        strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
                        civitai=CivitaiSelector(model_id=i),
                    ),
                    display_name=f"Model {i}",
                    provider_name="civitai",
                ),
                provenance=f"file:{i}",
                item=EvidenceItem(source="file_metadata", description="t", confidence=0.50 + i * 0.01),
            )
            for i in range(1, 6)
        ]

        service, _ = self._make_service(pack, hits)
        result = service.suggest(pack, "lora_001")

        ids = [c.candidate_id for c in result.candidates]
        # All unique
        assert len(set(ids)) == len(ids)
        # All look like UUIDs (32 hex chars + 4 dashes)
        for cid in ids:
            assert len(cid) == 36
            assert cid.count("-") == 4


# =============================================================================
# InMemoryCandidateCache — find_by_candidate_id
# =============================================================================

class TestCacheFindByCandidateId:
    """Tests for find_by_candidate_id added during Claude review."""

    def test_finds_candidate_across_requests(self):
        cache = InMemoryCandidateCache()
        c1 = ResolutionCandidate(
            confidence=0.95, tier=1,
            strategy=SelectorStrategy.CIVITAI_FILE,
            display_name="Model A",
        )
        c2 = ResolutionCandidate(
            confidence=0.80, tier=2,
            strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
            display_name="Model B",
        )
        cache.store("req1", "fp1", [c1])
        cache.store("req2", "fp2", [c2])

        found = cache.find_by_candidate_id(c2.candidate_id)
        assert found is not None
        assert found.display_name == "Model B"

    def test_returns_none_for_unknown_id(self):
        cache = InMemoryCandidateCache()
        assert cache.find_by_candidate_id("nonexistent") is None

    def test_skips_expired_entries(self):
        cache = InMemoryCandidateCache(ttl=0.01)
        c = ResolutionCandidate(
            confidence=0.95, tier=1,
            strategy=SelectorStrategy.CIVITAI_FILE,
            display_name="Expired",
        )
        cache.store("req1", "fp1", [c])
        time.sleep(0.02)

        assert cache.find_by_candidate_id(c.candidate_id) is None


# =============================================================================
# Real Pydantic models — NOT MagicMock
# =============================================================================

class TestWithRealPydanticModels:
    """Verify suggest/apply works with REAL Pack + PackDependency Pydantic models.

    This is the critical "does it actually work" test — no MagicMock for data models.
    """

    def _make_real_pack(self):
        """Create a real Pack with real PackDependency — no mocks."""
        dep = PackDependency(
            id="lora-detail-tweaker",
            kind=AssetKind.LORA,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                civitai=CivitaiSelector(model_id=100, version_id=200, file_id=300),
            ),
            expose=ExposeConfig(filename="detail_tweaker.safetensors"),
        )
        pack = Pack(
            name="test-sdxl-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=999),
            dependencies=[dep],
        )
        return pack, dep

    def _make_hit(self, key="civitai:100:200", confidence=0.95, source="hash_match"):
        return EvidenceHit(
            candidate=CandidateSeed(
                key=key,
                selector=DependencySelector(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=CivitaiSelector(model_id=100, version_id=200, file_id=300),
                ),
                display_name="Detail Tweaker XL",
                provider_name="civitai",
            ),
            provenance=f"{source}:abc123",
            item=EvidenceItem(source=source, description="test", confidence=confidence),
        )

    def test_suggest_with_real_pack(self):
        """suggest() works with real Pydantic Pack object."""
        pack, dep = self._make_real_pack()
        hit = self._make_hit()

        provider = MagicMock()
        provider.tier = 1
        provider.supports.return_value = True
        provider.gather.return_value = ProviderResult(hits=[hit])

        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"hash": provider},
        )
        result = service.suggest(pack, "lora-detail-tweaker")

        assert len(result.candidates) == 1
        assert result.candidates[0].confidence == pytest.approx(0.95)
        assert result.candidates[0].tier == 1
        assert result.candidates[0].display_name == "Detail Tweaker XL"
        assert len(result.pack_fingerprint) == 16  # SHA256[:16]

    def test_suggest_dep_not_found_real_pack(self):
        """suggest() returns warning for nonexistent dep_id on real Pack."""
        pack, _ = self._make_real_pack()
        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"x": MagicMock(tier=1)},
        )
        result = service.suggest(pack, "nonexistent-dep")
        assert any("not found" in w for w in result.warnings)
        assert result.candidates == []

    def test_suggest_reads_kind_from_real_dep(self):
        """suggest() correctly reads AssetKind from real PackDependency."""
        pack, dep = self._make_real_pack()

        provider = MagicMock()
        provider.tier = 1
        provider.supports.return_value = True
        provider.gather.return_value = ProviderResult(hits=[])

        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"test": provider},
        )
        result = service.suggest(pack, "lora-detail-tweaker")

        # Provider was called — means dep was found and context built
        provider.supports.assert_called_once()
        ctx = provider.supports.call_args[0][0]
        assert ctx.kind == AssetKind.LORA
        assert ctx.dep_id == "lora-detail-tweaker"

    def test_full_suggest_apply_with_real_pack(self):
        """Full suggest→apply round-trip with real Pack models."""
        pack, _ = self._make_real_pack()
        hit = self._make_hit()

        provider = MagicMock()
        provider.tier = 1
        provider.supports.return_value = True
        provider.gather.return_value = ProviderResult(hits=[hit])

        ps = MagicMock()
        ps.layout.load_pack.return_value = pack
        ps.apply_dependency_resolution = MagicMock()

        service = ResolveService(
            layout=MagicMock(),
            pack_service=ps,
            providers={"hash": provider},
        )

        # Suggest
        suggest = service.suggest(pack, "lora-detail-tweaker")
        assert len(suggest.candidates) == 1

        # Apply
        cid = suggest.candidates[0].candidate_id
        apply_result = service.apply(
            "test-sdxl-pack", "lora-detail-tweaker", cid,
            request_id=suggest.request_id,
        )

        assert apply_result.success is True
        ps.apply_dependency_resolution.assert_called_once()

        # Verify selector was reconstructed correctly
        call_kw = ps.apply_dependency_resolution.call_args.kwargs
        assert call_kw["selector"].civitai.model_id == 100
        assert call_kw["selector"].civitai.version_id == 200
        assert call_kw["selector"].civitai.file_id == 300

    def test_fingerprint_changes_with_real_pack(self):
        """Pack fingerprint is deterministic and changes when pack changes."""
        pack1, _ = self._make_real_pack()

        # Second pack with different dep
        dep2 = PackDependency(
            id="vae-sdxl",
            kind=AssetKind.VAE,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                civitai=CivitaiSelector(model_id=500, version_id=600, file_id=700),
            ),
            expose=ExposeConfig(filename="sdxl_vae.safetensors"),
        )
        pack2 = Pack(
            name="test-sdxl-pack",
            pack_type=AssetKind.CHECKPOINT,
            source=PackSource(provider=ProviderName.CIVITAI, model_id=999),
            dependencies=[dep2],
        )

        from src.store.resolve_service import _compute_pack_fingerprint
        fp1 = _compute_pack_fingerprint(pack1)
        fp2 = _compute_pack_fingerprint(pack2)

        assert len(fp1) == 16
        assert len(fp2) == 16
        assert fp1 != fp2  # Different packs = different fingerprint

        # Same pack = same fingerprint (deterministic)
        assert fp1 == _compute_pack_fingerprint(pack1)
