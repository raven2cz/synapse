"""
Smoke tests for AI-enhanced dependency resolution via ResolveService.

Tests the full flow: ResolveService.suggest(include_ai=True) →
AIEvidenceProvider → mock avatar → merge + score → SuggestResult.

Uses real ResolveService, real providers, real scoring. Only avatar
engine (HTTP/subprocess) is mocked.
"""

import pytest
from unittest.mock import MagicMock

from src.avatar.tasks.base import TaskResult
from src.store.evidence_providers import AIEvidenceProvider
from src.store.models import (
    AssetKind,
    DependencySelector,
    ExposeConfig,
    SelectorStrategy,
)
from src.store.resolve_models import (
    PreviewModelHint,
    SuggestOptions,
)
from src.store.resolve_service import ResolveService


# =============================================================================
# Helpers
# =============================================================================


def _make_pack_mock(**kwargs):
    """Create a mock Pack with real-looking fields."""
    pack = MagicMock()
    pack.name = kwargs.get("name", "anime_lora_v2")
    pack.type = kwargs.get("type", "lora")
    pack.base_model = kwargs.get("base_model", "Illustrious")
    pack.description = kwargs.get("description", "Anime style LoRA for Illustrious")
    pack.tags = kwargs.get("tags", ["anime", "illustrious"])

    # Dependencies
    dep = MagicMock()
    dep.id = kwargs.get("dep_id", "base_checkpoint")
    dep.kind = kwargs.get("dep_kind", AssetKind.CHECKPOINT)
    dep.selector = DependencySelector(
        strategy=SelectorStrategy.BASE_MODEL_HINT,
        base_model=kwargs.get("dep_base_model", "Illustrious"),
    )
    dep.expose = MagicMock()
    dep.expose.filename = kwargs.get("dep_filename", "illustrious_v1.safetensors")
    dep.lock = None  # No hash lock

    pack.dependencies = [dep]
    return pack


def _make_avatar_mock(candidates, search_summary=""):
    """Create a mock avatar that returns specific candidates."""
    avatar = MagicMock()
    avatar.execute_task.return_value = TaskResult(
        success=True,
        output={
            "candidates": candidates,
            "search_summary": search_summary,
        },
        provider_id="avatar:gemini",
        model="gemini-2.0-flash",
    )
    return avatar


def _make_service(avatar=None, **kwargs):
    """Create ResolveService with mock layout and pack_service."""
    layout = MagicMock()
    layout.config_path = None  # No aliases
    pack_service = MagicMock()
    pack_service.civitai = MagicMock()
    pack_service.civitai.get_model_by_hash.return_value = None  # No hash hits

    avatar_getter = lambda: avatar

    # We inject only the AI provider (skip others that need real filesystem)
    providers = {
        "ai": AIEvidenceProvider(avatar_getter),
    }

    return ResolveService(
        layout=layout,
        pack_service=pack_service,
        avatar_getter=avatar_getter,
        providers=providers,
    )


# =============================================================================
# Smoke tests
# =============================================================================


@pytest.mark.integration
class TestAIResolveSmokeFlow:
    """Smoke tests for the complete suggest(include_ai=True) flow."""

    def test_suggest_with_ai_returns_candidates(self):
        """Basic flow: AI returns one candidate → appears in SuggestResult."""
        avatar = _make_avatar_mock(
            candidates=[
                {
                    "display_name": "Illustrious XL v0.1",
                    "provider": "civitai",
                    "model_id": 795765,
                    "version_id": 889818,
                    "file_id": 795432,
                    "base_model": "Illustrious",
                    "confidence": 0.85,
                    "reasoning": "Pack base_model is 'Illustrious', filename hint matches.",
                }
            ],
            search_summary="Searched Civitai for 'Illustrious XL'.",
        )

        service = _make_service(avatar=avatar)
        pack = _make_pack_mock()

        result = service.suggest(
            pack, "base_checkpoint",
            options=SuggestOptions(include_ai=True),
        )

        assert len(result.candidates) >= 1
        top = result.candidates[0]
        assert top.display_name == "Illustrious XL v0.1"
        assert top.confidence > 0
        assert top.confidence <= 0.89
        assert len(top.evidence_groups) >= 1
        assert top.evidence_groups[0].items[0].source == "ai_analysis"

    def test_suggest_without_ai_skips_provider(self):
        """include_ai=False → AI provider skipped, no candidates from AI."""
        avatar = _make_avatar_mock(
            candidates=[
                {
                    "display_name": "Should not appear",
                    "provider": "civitai",
                    "model_id": 1,
                    "confidence": 0.80,
                    "reasoning": "Should be skipped.",
                }
            ],
        )

        service = _make_service(avatar=avatar)
        pack = _make_pack_mock()

        result = service.suggest(
            pack, "base_checkpoint",
            options=SuggestOptions(include_ai=False),
        )

        # AI was skipped, and we only registered AI provider
        assert len(result.candidates) == 0
        avatar.execute_task.assert_not_called()

    def test_suggest_ai_multi_provider(self):
        """AI returns both Civitai and HF → both appear as candidates."""
        avatar = _make_avatar_mock(
            candidates=[
                {
                    "display_name": "RealVisXL V4.0",
                    "provider": "civitai",
                    "model_id": 139562,
                    "version_id": 789012,
                    "file_id": 456789,
                    "base_model": "SDXL",
                    "confidence": 0.89,
                    "reasoning": "Strong match.",
                },
                {
                    "display_name": "RealVisXL V4.0 (HF)",
                    "provider": "huggingface",
                    "repo_id": "SG161222/RealVisXL_V4.0",
                    "filename": "RealVisXL_V4.0.safetensors",
                    "confidence": 0.75,
                    "reasoning": "HF corroboration.",
                },
            ],
            search_summary="Multi-provider search.",
        )

        service = _make_service(avatar=avatar)
        pack = _make_pack_mock(
            name="portrait_lora",
            base_model="SDXL",
            dep_base_model="SDXL",
            dep_filename="realvisxl_v40.safetensors",
        )

        result = service.suggest(
            pack, "base_checkpoint",
            options=SuggestOptions(include_ai=True),
        )

        assert len(result.candidates) >= 2
        providers = {c.provider for c in result.candidates}
        assert "civitai" in providers
        assert "huggingface" in providers
        # Top candidate should be sorted by confidence
        assert result.candidates[0].confidence >= result.candidates[1].confidence

    def test_suggest_ai_empty_result(self):
        """AI finds nothing → empty candidates, no error."""
        avatar = _make_avatar_mock(
            candidates=[],
            search_summary="No match found.",
        )

        service = _make_service(avatar=avatar)
        pack = _make_pack_mock(
            name="custom_model",
            base_model=None,
            dep_base_model=None,
            dep_filename="model.safetensors",
        )

        result = service.suggest(
            pack, "base_checkpoint",
            options=SuggestOptions(include_ai=True),
        )

        assert len(result.candidates) == 0

    def test_suggest_ai_failure_graceful(self):
        """AI task fails → warning in result, no crash."""
        avatar = MagicMock()
        avatar.execute_task.return_value = TaskResult(
            success=False,
            error="Engine timeout",
        )

        service = _make_service(avatar=avatar)
        pack = _make_pack_mock()

        result = service.suggest(
            pack, "base_checkpoint",
            options=SuggestOptions(include_ai=True),
        )

        # No crash, warning present
        assert any("timeout" in w.lower() or "failed" in w.lower() for w in result.warnings)
        assert len(result.candidates) == 0

    def test_suggest_no_avatar_graceful(self):
        """No avatar configured → AI skipped via supports()."""
        service = _make_service(avatar=None)
        pack = _make_pack_mock()

        result = service.suggest(
            pack, "base_checkpoint",
            options=SuggestOptions(include_ai=True),
        )

        # No crash — AI provider's supports() returns False
        assert len(result.candidates) == 0

    def test_suggest_result_has_request_id(self):
        """SuggestResult always has a request_id for apply round-trip."""
        avatar = _make_avatar_mock(
            candidates=[
                {
                    "display_name": "Test Model",
                    "provider": "civitai",
                    "model_id": 100,
                    "confidence": 0.70,
                    "reasoning": "Test.",
                }
            ],
        )

        service = _make_service(avatar=avatar)
        pack = _make_pack_mock()

        result = service.suggest(
            pack, "base_checkpoint",
            options=SuggestOptions(include_ai=True),
        )

        assert result.request_id
        assert len(result.request_id) > 10  # UUID-like
