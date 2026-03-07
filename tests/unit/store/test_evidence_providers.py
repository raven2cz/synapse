"""
Tests for evidence_providers.py — 6 evidence providers for dependency resolution.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.store.models import AssetKind, DependencySelector, SelectorStrategy
from src.store.resolve_models import (
    EvidenceHit,
    PreviewModelHint,
    ProviderResult,
    ResolveContext,
)
from src.store.evidence_providers import (
    AIEvidenceProvider,
    AliasEvidenceProvider,
    EvidenceProvider,
    FileMetaEvidenceProvider,
    HashEvidenceProvider,
    PreviewMetaEvidenceProvider,
    SourceMetaEvidenceProvider,
    _extract_stem,
)


def _make_context(**kwargs) -> ResolveContext:
    """Create a minimal ResolveContext for testing."""
    defaults = {
        "pack": MagicMock(name="test_pack"),
        "dependency": MagicMock(name="test_dep"),
        "dep_id": "dep_001",
        "kind": AssetKind.CHECKPOINT,
    }
    defaults.update(kwargs)
    return ResolveContext(**defaults)


class TestEvidenceProviderProtocol:
    def test_hash_is_provider(self):
        p = HashEvidenceProvider(lambda: None)
        assert isinstance(p, EvidenceProvider)

    def test_preview_is_provider(self):
        p = PreviewMetaEvidenceProvider()
        assert isinstance(p, EvidenceProvider)

    def test_file_meta_is_provider(self):
        p = FileMetaEvidenceProvider()
        assert isinstance(p, EvidenceProvider)

    def test_alias_is_provider(self):
        p = AliasEvidenceProvider(lambda: None)
        assert isinstance(p, EvidenceProvider)

    def test_source_meta_is_provider(self):
        p = SourceMetaEvidenceProvider()
        assert isinstance(p, EvidenceProvider)

    def test_ai_is_provider(self):
        p = AIEvidenceProvider(lambda: None)
        assert isinstance(p, EvidenceProvider)


class TestHashEvidenceProvider:
    def test_tier_is_1(self):
        assert HashEvidenceProvider(lambda: None).tier == 1

    def test_supports_always_true(self):
        p = HashEvidenceProvider(lambda: None)
        ctx = _make_context()
        assert p.supports(ctx) is True

    def test_no_sha256_returns_empty(self):
        dep = MagicMock()
        dep.lock = None
        p = HashEvidenceProvider(lambda: None)
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)
        assert result.hits == []

    def test_hash_match_returns_hit(self):
        dep = MagicMock()
        dep.lock = MagicMock()
        dep.lock.sha256 = "abc123def456"

        civitai = MagicMock()
        civitai.get_model_by_hash.return_value = {
            "modelId": 100,
            "id": 200,
            "model": {"name": "Test Model"},
            "files": [{"id": 300, "hashes": {"SHA256": "abc123def456"}}],
        }

        ps = MagicMock()
        ps.civitai = civitai

        p = HashEvidenceProvider(lambda: ps)
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].item.source == "hash_match"
        assert result.hits[0].item.confidence == 0.95
        assert result.hits[0].candidate.key == "civitai:100:200"

    def test_civitai_lookup_failure_warns(self):
        dep = MagicMock()
        dep.lock = MagicMock()
        dep.lock.sha256 = "abc123"

        civitai = MagicMock()
        civitai.get_model_by_hash.side_effect = Exception("API error")

        ps = MagicMock()
        ps.civitai = civitai

        p = HashEvidenceProvider(lambda: ps)
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)

        assert result.hits == []
        assert len(result.warnings) == 1
        assert "API error" in result.warnings[0]


class TestPreviewMetaEvidenceProvider:
    def test_tier_is_2(self):
        assert PreviewMetaEvidenceProvider().tier == 2

    def test_supports_with_hints(self):
        p = PreviewMetaEvidenceProvider()
        hint = PreviewModelHint(
            filename="model.safetensors", source_image="001.png",
            source_type="api_meta", raw_value="model",
        )
        ctx = _make_context(preview_hints=[hint])
        assert p.supports(ctx) is True

    def test_supports_without_hints(self):
        p = PreviewMetaEvidenceProvider()
        ctx = _make_context(preview_hints=[])
        assert p.supports(ctx) is False

    def test_gather_produces_hits(self):
        p = PreviewMetaEvidenceProvider()
        hints = [
            PreviewModelHint(
                filename="illustriousXL_v060.safetensors",
                kind=AssetKind.CHECKPOINT,
                source_image="001.png",
                source_type="api_meta",
                raw_value="illustriousXL_v060",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        hit = result.hits[0]
        assert hit.item.source == "preview_api_meta"
        assert hit.item.confidence == 0.82
        assert hit.provenance == "preview:001.png"

    def test_png_embedded_higher_confidence(self):
        p = PreviewMetaEvidenceProvider()
        hints = [
            PreviewModelHint(
                filename="model.safetensors",
                source_image="001.png",
                source_type="png_embedded",
                raw_value="model",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)

        assert result.hits[0].item.confidence == 0.85
        assert result.hits[0].item.source == "preview_embedded"

    def test_unresolvable_hints_skipped(self):
        p = PreviewMetaEvidenceProvider()
        hints = [
            PreviewModelHint(
                filename="private_model.safetensors",
                source_image="001.png",
                source_type="api_meta",
                raw_value="private",
                resolvable=False,
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        result = p.gather(ctx)
        assert result.hits == []


class TestFileMetaEvidenceProvider:
    def test_tier_is_3(self):
        assert FileMetaEvidenceProvider().tier == 3

    def test_extracts_from_filename(self):
        dep = MagicMock()
        dep.filename = "illustriousXL_v060.safetensors"
        dep.name = None

        p = FileMetaEvidenceProvider()
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].item.source == "file_metadata"
        assert result.hits[0].item.confidence == 0.60

    def test_no_filename_returns_empty(self):
        dep = MagicMock()
        dep.filename = None
        dep.name = None

        p = FileMetaEvidenceProvider()
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)
        assert result.hits == []


class TestExtractStem:
    def test_safetensors(self):
        assert _extract_stem("model.safetensors") == "model"

    def test_ckpt(self):
        assert _extract_stem("model.ckpt") == "model"

    def test_no_extension(self):
        assert _extract_stem("model") == "model"

    def test_empty(self):
        assert _extract_stem(".safetensors") is None


class TestSourceMetaEvidenceProvider:
    def test_tier_is_4(self):
        assert SourceMetaEvidenceProvider().tier == 4

    def test_produces_hint_from_base_model(self):
        dep = MagicMock()
        dep.base_model = "SDXL"

        p = SourceMetaEvidenceProvider()
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].item.source == "source_metadata"
        assert result.hits[0].item.confidence == 0.40

    def test_no_base_model_returns_empty(self):
        dep = MagicMock()
        dep.base_model = None

        p = SourceMetaEvidenceProvider()
        ctx = _make_context(dependency=dep)
        result = p.gather(ctx)
        assert result.hits == []


class TestAIEvidenceProvider:
    def test_tier_is_2(self):
        assert AIEvidenceProvider(lambda: None).tier == 2

    def test_supports_returns_false_when_avatar_none(self):
        p = AIEvidenceProvider(lambda: None)
        ctx = _make_context()
        assert p.supports(ctx) is False

    def test_supports_returns_true_after_set_avatar(self):
        avatar = MagicMock()
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        assert p.supports(ctx) is True

    def test_gather_returns_error_when_no_avatar(self):
        p = AIEvidenceProvider(lambda: None)
        ctx = _make_context()
        result = p.gather(ctx)
        assert result.error is not None

    def test_caps_confidence_at_089(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = {
            "candidates": [
                {"key": "test:1", "name": "High conf", "confidence": 0.99,
                 "model_id": 123, "reasoning": "test"},
            ],
        }
        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)

        assert len(result.hits) == 1
        assert result.hits[0].item.confidence == 0.89  # Capped

    def test_gather_calls_dependency_resolution_task(self):
        avatar = MagicMock()
        avatar.execute_task.return_value = {"candidates": []}

        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        p.gather(ctx)

        avatar.execute_task.assert_called_once()
        call_args = avatar.execute_task.call_args
        assert call_args[0][0] == "dependency_resolution"

    def test_gather_handles_exception(self):
        avatar = MagicMock()
        avatar.execute_task.side_effect = Exception("AI crashed")

        p = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = p.gather(ctx)

        assert result.error is not None
        assert "AI crashed" in result.error
