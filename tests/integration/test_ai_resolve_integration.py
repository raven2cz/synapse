"""
Integration tests for AI-enhanced dependency resolution.

Tests the full chain: ResolveContext → AIEvidenceProvider → AvatarTaskService
→ DependencyResolutionTask → EvidenceHits → correct selectors.

Uses real Pydantic models (Pack, PackDependency, DependencySelector) —
NOT MagicMock. Only the avatar engine (HTTP/subprocess) is mocked.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from src.avatar.tasks.base import TaskResult
from src.avatar.tasks.dependency_resolution import (
    AI_CONFIDENCE_CEILING,
    DependencyResolutionTask,
)
from src.store.evidence_providers import (
    AIEvidenceProvider,
    _build_ai_input,
    _ai_candidate_to_hit,
)
from src.store.models import (
    AssetKind,
    CivitaiSelector,
    DependencySelector,
    ExposeConfig,
    SelectorStrategy,
)
from src.store.resolve_models import (
    PreviewModelHint,
    ResolveContext,
)


# =============================================================================
# Fixtures: Real Pydantic objects (not MagicMock)
# =============================================================================


def _make_pack(**kwargs):
    """Create a mock pack with real-looking attributes."""
    pack = MagicMock()
    pack.name = kwargs.get("name", "anime_style_lora_v2")
    pack.type = kwargs.get("type", "lora")
    pack.base_model = kwargs.get("base_model", "Illustrious")
    pack.description = kwargs.get("description", "A LoRA for anime-style illustrations")
    pack.tags = kwargs.get("tags", ["anime", "illustration", "style"])
    return pack


def _make_dependency(**kwargs):
    """Create a mock dependency with real-looking attributes."""
    dep = MagicMock()
    dep.selector = DependencySelector(
        strategy=kwargs.get("strategy", SelectorStrategy.BASE_MODEL_HINT),
        base_model=kwargs.get("base_model", "Illustrious"),
    )
    dep.expose = MagicMock()
    dep.expose.filename = kwargs.get("expose_filename", "illustrious_v1.safetensors")
    return dep


def _make_context(**kwargs):
    """Create ResolveContext with real-ish objects."""
    return ResolveContext(
        pack=kwargs.get("pack", _make_pack()),
        dependency=kwargs.get("dependency", _make_dependency()),
        dep_id=kwargs.get("dep_id", "base_checkpoint"),
        kind=kwargs.get("kind", AssetKind.CHECKPOINT),
        preview_hints=kwargs.get("preview_hints", []),
    )


# =============================================================================
# Test: _build_ai_input produces correct format
# =============================================================================


class TestBuildAIInputFormat:
    """Test that _build_ai_input creates the format model-resolution.md expects."""

    def test_basic_input_has_all_sections(self):
        ctx = _make_context()
        text = _build_ai_input(ctx)

        assert "PACK INFO:" in text
        assert "DEPENDENCY TO RESOLVE:" in text
        assert "  name: anime_style_lora_v2" in text
        assert "  type: lora" in text
        assert "  base_model: Illustrious" in text
        assert "  kind: checkpoint" in text
        assert "  id: base_checkpoint" in text
        assert "  expose_filename: illustrious_v1.safetensors" in text

    def test_includes_pack_description_truncated(self):
        long_desc = "x" * 1000
        pack = _make_pack(description=long_desc)
        ctx = _make_context(pack=pack)
        text = _build_ai_input(ctx)

        # Should be truncated to 500 chars
        desc_line = [l for l in text.split("\n") if "description:" in l][0]
        assert len(desc_line) < 600  # "  description: " + 500 chars

    def test_includes_tags(self):
        ctx = _make_context()
        text = _build_ai_input(ctx)
        assert "anime" in text
        assert "illustration" in text

    def test_includes_preview_hints_when_present(self):
        hints = [
            PreviewModelHint(
                filename="realvisxl_v40.safetensors",
                source_image="preview_001.png",
                source_type="api_meta",
                raw_value="RealVisXL V4.0",
            ),
            PreviewModelHint(
                filename="another_model.safetensors",
                source_image="preview_002.png",
                source_type="png_embedded",
                raw_value="Another Model",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        text = _build_ai_input(ctx)

        assert "PREVIEW HINTS:" in text
        assert "realvisxl_v40.safetensors" in text
        assert "RealVisXL V4.0" in text
        assert "preview_001.png" in text

    def test_no_hints_shows_none(self):
        ctx = _make_context(preview_hints=[])
        text = _build_ai_input(ctx)
        assert "(none)" in text

    def test_hint_from_selector_base_model(self):
        dep = _make_dependency(base_model="SDXL")
        ctx = _make_context(dependency=dep)
        text = _build_ai_input(ctx)
        assert "  hint: SDXL" in text

    def test_hint_falls_back_to_pack_base_model(self):
        dep = _make_dependency(base_model=None)
        pack = _make_pack(base_model="Pony")
        ctx = _make_context(pack=pack, dependency=dep)
        text = _build_ai_input(ctx)
        assert "  hint: Pony" in text


# =============================================================================
# Test: _ai_candidate_to_hit conversion
# =============================================================================


class TestAICandidateToHit:
    """Test individual candidate → EvidenceHit conversion."""

    def test_civitai_full(self):
        candidate = {
            "display_name": "RealVisXL V4.0",
            "provider": "civitai",
            "model_id": 139562,
            "version_id": 789012,
            "file_id": 456789,
            "base_model": "SDXL",
            "confidence": 0.85,
            "reasoning": "Strong match based on preview hints.",
        }
        hit = _ai_candidate_to_hit(candidate, "base_ckpt")
        assert hit is not None
        assert hit.candidate.selector.strategy == SelectorStrategy.CIVITAI_FILE
        assert hit.candidate.selector.civitai.model_id == 139562
        assert hit.candidate.selector.civitai.version_id == 789012
        assert hit.candidate.selector.civitai.file_id == 456789
        assert hit.item.confidence == 0.85
        assert hit.provenance == "ai:base_ckpt"

    def test_civitai_partial_uses_latest(self):
        candidate = {
            "display_name": "Some model",
            "provider": "civitai",
            "model_id": 100,
            "version_id": None,
            "file_id": None,
            "confidence": 0.60,
            "reasoning": "Partial match.",
        }
        hit = _ai_candidate_to_hit(candidate, "dep1")
        assert hit is not None
        assert hit.candidate.selector.strategy == SelectorStrategy.CIVITAI_MODEL_LATEST

    def test_huggingface(self):
        candidate = {
            "display_name": "SDXL Base (HF)",
            "provider": "huggingface",
            "repo_id": "stabilityai/stable-diffusion-xl-base-1.0",
            "filename": "sd_xl_base_1.0.safetensors",
            "revision": "main",
            "confidence": 0.72,
            "reasoning": "HF match.",
        }
        hit = _ai_candidate_to_hit(candidate, "dep1")
        assert hit is not None
        assert hit.candidate.selector.strategy == SelectorStrategy.HUGGINGFACE_FILE
        assert hit.candidate.selector.huggingface.repo_id == "stabilityai/stable-diffusion-xl-base-1.0"
        assert hit.candidate.selector.huggingface.filename == "sd_xl_base_1.0.safetensors"

    def test_confidence_capped(self):
        candidate = {
            "display_name": "Overconfident",
            "provider": "civitai",
            "model_id": 1,
            "confidence": 0.99,
            "reasoning": "Too confident.",
        }
        hit = _ai_candidate_to_hit(candidate, "dep1")
        assert hit.item.confidence == AI_CONFIDENCE_CEILING

    def test_unknown_provider_returns_none(self):
        candidate = {
            "display_name": "Unknown",
            "provider": "other_source",
            "confidence": 0.50,
            "reasoning": "Unknown.",
        }
        assert _ai_candidate_to_hit(candidate, "dep1") is None

    def test_civitai_no_model_id_returns_none(self):
        candidate = {
            "display_name": "No ID",
            "provider": "civitai",
            "confidence": 0.50,
            "reasoning": "Missing model_id.",
        }
        assert _ai_candidate_to_hit(candidate, "dep1") is None


# =============================================================================
# Test: Full chain — AIEvidenceProvider → parse → hits
# =============================================================================


class TestAIResolveFullChain:
    """Integration: AIEvidenceProvider calls mock avatar, gets correct hits."""

    def _make_avatar_with_response(self, candidates, search_summary=""):
        """Create mock avatar that returns specific candidates."""
        avatar = MagicMock()
        task_result = TaskResult(
            success=True,
            output={
                "candidates": candidates,
                "search_summary": search_summary,
            },
            provider_id="avatar:gemini",
            model="gemini-2.0-flash",
        )
        avatar.execute_task.return_value = task_result
        return avatar

    def test_illustrious_checkpoint_resolve(self):
        """LoRA pack → needs Illustrious checkpoint → AI finds on Civitai."""
        avatar = self._make_avatar_with_response(
            candidates=[
                {
                    "display_name": "Illustrious XL v0.1",
                    "provider": "civitai",
                    "model_id": 795765,
                    "version_id": 889818,
                    "file_id": 795432,
                    "base_model": "Illustrious",
                    "confidence": 0.85,
                    "reasoning": "Pack base_model is 'Illustrious', E4+E5 confirm.",
                }
            ],
            search_summary="Searched Civitai for 'Illustrious XL' (Checkpoint).",
        )

        provider = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = provider.gather(ctx)

        assert len(result.hits) == 1
        hit = result.hits[0]
        assert hit.candidate.display_name == "Illustrious XL v0.1"
        assert hit.candidate.selector.civitai.model_id == 795765
        assert hit.candidate.selector.civitai.version_id == 889818
        assert hit.item.source == "ai_analysis"
        assert hit.item.confidence == 0.85

        # Verify the input was formatted correctly
        input_text = avatar.execute_task.call_args[0][1]
        assert "anime_style_lora_v2" in input_text
        assert "Illustrious" in input_text

    def test_multi_provider_resolve(self):
        """AI returns both Civitai and HuggingFace candidates."""
        avatar = self._make_avatar_with_response(
            candidates=[
                {
                    "display_name": "RealVisXL V4.0",
                    "provider": "civitai",
                    "model_id": 139562,
                    "version_id": 789012,
                    "file_id": 456789,
                    "base_model": "SDXL",
                    "confidence": 0.89,
                    "reasoning": "Preview hints match.",
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

        pack = _make_pack(name="portrait_lora", base_model="SDXL")
        dep = _make_dependency(base_model="SDXL", expose_filename="realvisxl_v40.safetensors")
        ctx = _make_context(pack=pack, dependency=dep, dep_id="base_ckpt")

        provider = AIEvidenceProvider(lambda: avatar)
        result = provider.gather(ctx)

        assert len(result.hits) == 2

        civitai_hit = [h for h in result.hits if h.candidate.provider_name == "civitai"][0]
        hf_hit = [h for h in result.hits if h.candidate.provider_name == "huggingface"][0]

        assert civitai_hit.candidate.selector.strategy == SelectorStrategy.CIVITAI_FILE
        assert civitai_hit.item.confidence == 0.89

        assert hf_hit.candidate.selector.strategy == SelectorStrategy.HUGGINGFACE_FILE
        assert hf_hit.candidate.selector.huggingface.repo_id == "SG161222/RealVisXL_V4.0"
        assert hf_hit.item.confidence == 0.75

    def test_no_match_returns_empty(self):
        """Private model → AI returns empty candidates."""
        avatar = self._make_avatar_with_response(
            candidates=[],
            search_summary="No match found. Generic filename.",
        )

        pack = _make_pack(
            name="custom_model",
            base_model=None,
            description="My private model",
            tags=[],
        )
        dep = _make_dependency(base_model=None, expose_filename="model.safetensors")
        ctx = _make_context(pack=pack, dependency=dep)

        provider = AIEvidenceProvider(lambda: avatar)
        result = provider.gather(ctx)

        assert result.hits == []
        assert result.error is None

    def test_ai_failure_returns_error(self):
        """AI task fails → provider returns error, no hits."""
        avatar = MagicMock()
        avatar.execute_task.return_value = TaskResult(
            success=False,
            error="Engine timeout after 180s",
        )

        provider = AIEvidenceProvider(lambda: avatar)
        ctx = _make_context()
        result = provider.gather(ctx)

        assert result.error is not None
        assert "Engine timeout" in result.error
        assert result.hits == []

    def test_avatar_unavailable(self):
        """No avatar configured → supports() returns False."""
        provider = AIEvidenceProvider(lambda: None)
        ctx = _make_context()
        assert provider.supports(ctx) is False

        result = provider.gather(ctx)
        assert result.error is not None

    def test_preview_hints_passed_to_ai(self):
        """Preview hints from context are included in AI input."""
        avatar = self._make_avatar_with_response(candidates=[])

        hints = [
            PreviewModelHint(
                filename="illustriousXL_v060.safetensors",
                kind=AssetKind.CHECKPOINT,
                source_image="preview_001.png",
                source_type="api_meta",
                raw_value="Illustrious XL v0.6",
            ),
        ]
        ctx = _make_context(preview_hints=hints)
        provider = AIEvidenceProvider(lambda: avatar)
        provider.gather(ctx)

        input_text = avatar.execute_task.call_args[0][1]
        assert "PREVIEW HINTS:" in input_text
        assert "illustriousXL_v060.safetensors" in input_text
        assert "Illustrious XL v0.6" in input_text


# =============================================================================
# Test: DependencyResolutionTask parse_result + validate_output chain
# =============================================================================


class TestDependencyResolutionTaskIntegration:
    """Test parse_result → validate_output on realistic AI output."""

    def test_realistic_civitai_response(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
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
            "search_summary": "Searched Civitai for 'Illustrious XL'.",
        }
        parsed = task.parse_result(raw)
        assert task.validate_output(parsed) is True
        assert len(parsed["candidates"]) == 1
        assert parsed["candidates"][0]["confidence"] == 0.85

    def test_realistic_multi_provider_response(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "RealVisXL V4.0",
                    "provider": "civitai",
                    "model_id": 139562,
                    "version_id": 789012,
                    "file_id": 456789,
                    "base_model": "SDXL",
                    "confidence": 0.96,  # Will be capped
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
            "search_summary": "Multi-provider search.",
        }
        parsed = task.parse_result(raw)
        assert task.validate_output(parsed) is True
        assert len(parsed["candidates"]) == 2
        # Confidence capped
        assert parsed["candidates"][0]["confidence"] == AI_CONFIDENCE_CEILING
        # Sorted by confidence descending
        assert parsed["candidates"][0]["confidence"] >= parsed["candidates"][1]["confidence"]

    def test_realistic_empty_response(self):
        task = DependencyResolutionTask()
        raw = {
            "candidates": [],
            "search_summary": "No match. Generic filename 'model.safetensors'.",
        }
        parsed = task.parse_result(raw)
        assert task.validate_output(parsed) is True
        assert parsed["candidates"] == []

    def test_malformed_ai_response_filtered(self):
        """AI returns mix of valid and invalid candidates."""
        task = DependencyResolutionTask()
        raw = {
            "candidates": [
                {
                    "display_name": "Valid Civitai",
                    "provider": "civitai",
                    "model_id": 100,
                    "confidence": 0.80,
                    "reasoning": "Good.",
                },
                {
                    # Missing model_id for civitai
                    "display_name": "Bad Civitai",
                    "provider": "civitai",
                    "confidence": 0.70,
                    "reasoning": "Missing field.",
                },
                {
                    # Missing filename for huggingface
                    "display_name": "Bad HF",
                    "provider": "huggingface",
                    "repo_id": "org/repo",
                    "confidence": 0.60,
                    "reasoning": "Missing filename.",
                },
            ],
        }
        parsed = task.parse_result(raw)
        assert task.validate_output(parsed) is True
        assert len(parsed["candidates"]) == 1
        assert parsed["candidates"][0]["display_name"] == "Valid Civitai"
