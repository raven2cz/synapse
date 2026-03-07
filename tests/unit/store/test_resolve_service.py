"""
Tests for resolve_service.py — ResolveService orchestration, candidate cache.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.store.models import AssetKind, CivitaiSelector, DependencySelector, SelectorStrategy
from src.store.resolve_models import (
    ApplyResult,
    EvidenceGroup,
    EvidenceHit,
    EvidenceItem,
    CandidateSeed,
    ManualResolveData,
    PreviewModelHint,
    ProviderResult,
    ResolutionCandidate,
    SuggestOptions,
    SuggestResult,
)
from src.store.resolve_service import (
    InMemoryCandidateCache,
    ResolveService,
)


def _make_pack(name="test_pack", base_model="SDXL", dependencies=None):
    pack = MagicMock()
    pack.name = name
    pack.base_model = base_model
    pack.dependencies = dependencies or []
    pack.model_dump.return_value = {"name": name, "base_model": base_model}
    return pack


def _make_dep(dep_id="dep_001", kind=AssetKind.CHECKPOINT, filename="model.safetensors"):
    dep = MagicMock()
    dep.id = dep_id
    dep.kind = kind
    dep.filename = filename
    dep.name = filename
    dep.base_model = None
    dep.lock = None
    dep._preview_hints = []
    return dep


def _make_provider(tier=1, supports=True, hits=None, error=None):
    provider = MagicMock()
    provider.tier = tier
    provider.supports.return_value = supports
    provider.gather.return_value = ProviderResult(
        hits=hits or [],
        error=error,
    )
    return provider


def _make_hit(key="civitai:1:2", provenance="hash:abc", source="hash_match", confidence=0.95):
    return EvidenceHit(
        candidate=CandidateSeed(
            key=key,
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                civitai=CivitaiSelector(model_id=1, version_id=2, file_id=3),
            ),
            display_name="Test Model",
            provider_name="civitai",
        ),
        provenance=provenance,
        item=EvidenceItem(source=source, description="test", confidence=confidence),
    )


class TestInMemoryCandidateCache:
    def test_store_and_get(self):
        cache = InMemoryCandidateCache()
        c = ResolutionCandidate(
            confidence=0.95, tier=1,
            strategy=SelectorStrategy.CIVITAI_FILE,
            display_name="test",
        )
        cache.store("req1", "fp1", [c])
        result = cache.get("req1", c.candidate_id)
        assert result is not None
        assert result.confidence == 0.95

    def test_get_nonexistent(self):
        cache = InMemoryCandidateCache()
        assert cache.get("req1", "nonexistent") is None

    def test_expired_returns_none(self):
        cache = InMemoryCandidateCache(ttl=0.01)
        c = ResolutionCandidate(
            confidence=0.95, tier=1,
            strategy=SelectorStrategy.CIVITAI_FILE,
            display_name="test",
        )
        cache.store("req1", "fp1", [c])
        time.sleep(0.02)
        assert cache.get("req1", c.candidate_id) is None

    def test_check_fingerprint(self):
        cache = InMemoryCandidateCache()
        cache.store("req1", "fp1", [])
        assert cache.check_fingerprint("req1", "fp1") is True
        assert cache.check_fingerprint("req1", "fp_wrong") is False
        assert cache.check_fingerprint("req_missing", "fp1") is False

    def test_cleanup_expired(self):
        cache = InMemoryCandidateCache(ttl=0.01)
        cache.store("req1", "fp1", [])
        cache.store("req2", "fp2", [])
        time.sleep(0.02)
        cache.cleanup_expired()
        assert len(cache._store) == 0


class TestResolveServiceSuggest:
    def test_suggest_with_no_deps(self):
        pack = _make_pack(dependencies=[])
        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"test": _make_provider()},
        )
        result = service.suggest(pack, "dep_001")
        assert isinstance(result, SuggestResult)
        assert "not found" in result.warnings[0]

    def test_suggest_returns_candidates(self):
        dep = _make_dep()
        pack = _make_pack(dependencies=[dep])

        hit = _make_hit()
        provider = _make_provider(tier=1, hits=[hit])

        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"hash": provider},
        )
        result = service.suggest(pack, "dep_001")

        assert len(result.candidates) == 1
        assert result.candidates[0].confidence == pytest.approx(0.95)
        assert result.candidates[0].tier == 1
        assert result.candidates[0].rank == 1

    def test_suggest_skips_unsupported_providers(self):
        dep = _make_dep()
        pack = _make_pack(dependencies=[dep])

        p1 = _make_provider(tier=1, supports=False)
        p2 = _make_provider(tier=2, supports=True, hits=[_make_hit(
            key="preview:1", provenance="preview:001.png",
            source="preview_api_meta", confidence=0.82,
        )])

        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"hash": p1, "preview": p2},
        )
        result = service.suggest(pack, "dep_001")

        p1.gather.assert_not_called()
        assert len(result.candidates) == 1

    def test_suggest_skips_ai_by_default(self):
        dep = _make_dep()
        pack = _make_pack(dependencies=[dep])

        ai_provider = _make_provider(tier=2, supports=True, hits=[
            _make_hit(source="ai_analysis", confidence=0.80),
        ])

        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"ai": ai_provider},
        )
        result = service.suggest(pack, "dep_001")

        # AI should be skipped when include_ai=False (default)
        ai_provider.gather.assert_not_called()
        assert len(result.candidates) == 0

    def test_suggest_includes_ai_when_requested(self):
        dep = _make_dep()
        pack = _make_pack(dependencies=[dep])

        ai_provider = _make_provider(tier=2, supports=True, hits=[
            _make_hit(key="ai:1", source="ai_analysis", confidence=0.80),
        ])

        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"ai": ai_provider},
        )
        result = service.suggest(pack, "dep_001", SuggestOptions(include_ai=True))

        ai_provider.gather.assert_called_once()
        assert len(result.candidates) == 1

    def test_suggest_merges_same_candidate(self):
        dep = _make_dep()
        pack = _make_pack(dependencies=[dep])

        hit1 = _make_hit(key="civitai:1:2", provenance="hash:abc",
                         source="hash_match", confidence=0.95)
        hit2 = _make_hit(key="civitai:1:2", provenance="preview:001.png",
                         source="preview_api_meta", confidence=0.82)

        p1 = _make_provider(tier=1, hits=[hit1])
        p2 = _make_provider(tier=2, hits=[hit2])

        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"hash": p1, "preview": p2},
        )
        result = service.suggest(pack, "dep_001")

        # Should merge into one candidate with combined score
        assert len(result.candidates) == 1
        assert result.candidates[0].confidence > 0.95  # Noisy-OR combined

    def test_suggest_provider_error_as_warning(self):
        dep = _make_dep()
        pack = _make_pack(dependencies=[dep])

        provider = _make_provider(tier=1, error="Something failed")

        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"broken": provider},
        )
        result = service.suggest(pack, "dep_001")
        assert any("Something failed" in w for w in result.warnings)

    def test_suggest_caches_result(self):
        dep = _make_dep()
        pack = _make_pack(dependencies=[dep])

        hit = _make_hit()
        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"hash": _make_provider(tier=1, hits=[hit])},
        )
        result = service.suggest(pack, "dep_001")

        # Verify candidate is in cache
        cached = service._cache.get(result.request_id, result.candidates[0].candidate_id)
        assert cached is not None

    def test_suggest_max_candidates(self):
        dep = _make_dep()
        pack = _make_pack(dependencies=[dep])

        hits = [
            _make_hit(key=f"civitai:{i}:{i}", confidence=0.40 + i * 0.01)
            for i in range(20)
        ]
        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
            providers={"source": _make_provider(tier=4, hits=hits)},
        )
        result = service.suggest(pack, "dep_001", SuggestOptions(max_candidates=5))
        assert len(result.candidates) == 5


class TestResolveServiceApply:
    def test_apply_candidate_not_found(self):
        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
        )
        result = service.apply("pack", "dep", "nonexistent_id")
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_apply_success(self):
        dep = _make_dep()
        pack = _make_pack(dependencies=[dep])
        ps = MagicMock()
        ps.layout.load_pack.return_value = pack
        ps.apply_dependency_resolution = MagicMock()

        service = ResolveService(
            layout=MagicMock(),
            pack_service=ps,
            providers={"hash": _make_provider(tier=1, hits=[_make_hit()])},
        )

        # First suggest to cache candidates
        suggest_result = service.suggest(pack, "dep_001")
        assert len(suggest_result.candidates) > 0

        cid = suggest_result.candidates[0].candidate_id
        apply_result = service.apply(
            "test_pack", "dep_001", cid,
            request_id=suggest_result.request_id,
        )
        assert apply_result.success is True

    def test_apply_manual_success(self):
        ps = MagicMock()
        ps.apply_dependency_resolution = MagicMock()

        service = ResolveService(
            layout=MagicMock(),
            pack_service=ps,
        )

        manual = ManualResolveData(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=1, version_id=2, file_id=3),
            display_name="Manual pick",
        )
        result = service.apply_manual("pack", "dep_001", manual)
        assert result.success is True

    def test_apply_manual_invalid_selector(self):
        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
        )
        manual = ManualResolveData(
            strategy=SelectorStrategy.CIVITAI_FILE,
            # Missing civitai data
        )
        result = service.apply_manual("pack", "dep_001", manual)
        assert result.success is False


class TestResolveServiceLazyProviders:
    def test_lazy_init_providers(self):
        service = ResolveService(
            layout=MagicMock(),
            pack_service=MagicMock(),
        )
        assert service._providers is None
        service._ensure_providers()
        assert service._providers is not None
        assert "hash_match" in service._providers
        assert "preview_meta" in service._providers
        assert "file_meta" in service._providers
        assert "alias" in service._providers
        assert "source_meta" in service._providers
        assert "ai" in service._providers
