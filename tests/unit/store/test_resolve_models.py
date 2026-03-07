"""
Tests for resolve_models.py — DTOs for dependency resolution.
"""

import pytest
from uuid import UUID

from src.store.models import (
    AssetKind,
    CanonicalSource,
    CivitaiSelector,
    DependencySelector,
    SelectorStrategy,
)
from src.store.resolve_models import (
    ApplyResult,
    CandidateSeed,
    EvidenceGroup,
    EvidenceHit,
    EvidenceItem,
    ManualResolveData,
    PreviewModelHint,
    ProviderResult,
    ResolveContext,
    ResolutionCandidate,
    SuggestOptions,
    SuggestResult,
)


class TestEvidenceItem:
    def test_create_hash_match(self):
        item = EvidenceItem(
            source="hash_match",
            description="SHA256 found on Civitai",
            confidence=0.95,
            raw_value="abc123",
        )
        assert item.source == "hash_match"
        assert item.confidence == 0.95

    def test_create_all_sources(self):
        sources = [
            "hash_match", "preview_embedded", "preview_api_meta",
            "source_metadata", "file_metadata", "alias_config", "ai_analysis",
        ]
        for src in sources:
            item = EvidenceItem(source=src, description="test", confidence=0.5)
            assert item.source == src


class TestEvidenceGroup:
    def test_provenance_grouping(self):
        group = EvidenceGroup(
            provenance="preview:001.png",
            items=[
                EvidenceItem(source="preview_embedded", description="ComfyUI", confidence=0.85),
                EvidenceItem(source="preview_api_meta", description="API", confidence=0.82),
            ],
            combined_confidence=0.85,
        )
        assert len(group.items) == 2
        assert group.combined_confidence == 0.85


class TestCandidateSeed:
    def test_civitai_candidate(self):
        seed = CandidateSeed(
            key="civitai:123:456",
            selector=DependencySelector(
                strategy=SelectorStrategy.CIVITAI_FILE,
                civitai=CivitaiSelector(model_id=123, version_id=456, file_id=789),
            ),
            display_name="Illustrious XL v0.6",
            provider_name="civitai",
        )
        assert seed.key == "civitai:123:456"
        assert seed.provider_name == "civitai"

    def test_local_candidate(self):
        seed = CandidateSeed(
            key="local:/models/model.safetensors",
            selector=DependencySelector(
                strategy=SelectorStrategy.LOCAL_FILE,
                local_path="/models/model.safetensors",
            ),
            display_name="model.safetensors",
            provider_name="local",
        )
        assert seed.provider_name == "local"


class TestResolutionCandidate:
    def test_auto_uuid(self):
        c = ResolutionCandidate(
            confidence=0.95,
            tier=1,
            strategy=SelectorStrategy.CIVITAI_FILE,
            display_name="test",
        )
        # Should be a valid UUID
        UUID(c.candidate_id)

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            ResolutionCandidate(confidence=1.5, tier=1, strategy=SelectorStrategy.CIVITAI_FILE, display_name="x")

        with pytest.raises(Exception):
            ResolutionCandidate(confidence=-0.1, tier=1, strategy=SelectorStrategy.CIVITAI_FILE, display_name="x")

    def test_tier_bounds(self):
        with pytest.raises(Exception):
            ResolutionCandidate(confidence=0.5, tier=0, strategy=SelectorStrategy.CIVITAI_FILE, display_name="x")

        with pytest.raises(Exception):
            ResolutionCandidate(confidence=0.5, tier=5, strategy=SelectorStrategy.CIVITAI_FILE, display_name="x")


class TestPreviewModelHint:
    def test_api_meta_hint(self):
        hint = PreviewModelHint(
            filename="illustriousXL_v060.safetensors",
            kind=AssetKind.CHECKPOINT,
            source_image="preview_001.png",
            source_type="api_meta",
            raw_value="Illustrious XL v0.6",
        )
        assert hint.resolvable is True
        assert hint.kind == AssetKind.CHECKPOINT

    def test_unresolvable_hint(self):
        hint = PreviewModelHint(
            filename="my_custom_merge_v3.safetensors",
            source_image="preview_002.png",
            source_type="png_embedded",
            raw_value="my_custom_merge_v3",
            resolvable=False,
        )
        assert hint.resolvable is False
        assert hint.kind is None


class TestProviderResult:
    def test_empty_result(self):
        result = ProviderResult()
        assert result.hits == []
        assert result.warnings == []
        assert result.error is None

    def test_error_result(self):
        result = ProviderResult(error="Scanner not available")
        assert result.error == "Scanner not available"


class TestSuggestOptions:
    def test_defaults(self):
        opts = SuggestOptions()
        assert opts.include_ai is False  # R5: OFF by default
        assert opts.analyze_previews is True
        assert opts.max_candidates == 10


class TestSuggestResult:
    def test_auto_request_id(self):
        result = SuggestResult()
        UUID(result.request_id)  # Should be valid UUID

    def test_with_candidates(self):
        c = ResolutionCandidate(
            confidence=0.95, tier=1,
            strategy=SelectorStrategy.CIVITAI_FILE,
            display_name="test",
        )
        result = SuggestResult(candidates=[c])
        assert len(result.candidates) == 1


class TestApplyResult:
    def test_success(self):
        r = ApplyResult(success=True, message="Applied")
        assert r.success is True
        assert r.compatibility_warnings == []

    def test_failure_with_warnings(self):
        r = ApplyResult(
            success=True,
            message="Applied",
            compatibility_warnings=["Base model mismatch"],
        )
        assert len(r.compatibility_warnings) == 1


class TestManualResolveData:
    def test_civitai_manual(self):
        data = ManualResolveData(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=123, version_id=456, file_id=789),
            display_name="My Model",
        )
        assert data.strategy == SelectorStrategy.CIVITAI_FILE

    def test_local_manual(self):
        data = ManualResolveData(
            strategy=SelectorStrategy.LOCAL_FILE,
            local_path="/models/test.safetensors",
        )
        assert data.local_path is not None


class TestCanonicalSource:
    def test_civitai_source(self):
        cs = CanonicalSource(
            provider="civitai",
            model_id=123,
            version_id=456,
            file_id=789,
            sha256="deadbeef",
        )
        assert cs.provider == "civitai"
        assert cs.model_id == 123

    def test_huggingface_source(self):
        cs = CanonicalSource(
            provider="huggingface",
            repo_id="stabilityai/sdxl",
            filename="model.safetensors",
            subfolder="unet",
            revision="main",
        )
        assert cs.provider == "huggingface"
        assert cs.subfolder == "unet"

    def test_canonical_source_on_selector(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.LOCAL_FILE,
            local_path="/models/test.safetensors",
            canonical_source=CanonicalSource(
                provider="civitai",
                model_id=123,
            ),
        )
        assert sel.canonical_source is not None
        assert sel.canonical_source.provider == "civitai"
