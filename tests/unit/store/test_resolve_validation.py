"""
Tests for resolve_validation.py — per-strategy field checks and cross-kind validation.
"""

import pytest

from src.store.models import (
    AssetKind,
    CivitaiSelector,
    DependencySelector,
    HuggingFaceSelector,
    SelectorStrategy,
)
from src.store.resolve_validation import (
    STRATEGY_REQUIREMENTS,
    validate_before_apply,
    validate_candidate,
    validate_selector_fields,
)


class TestStrategyRequirements:
    def test_all_strategies_covered(self):
        """Every SelectorStrategy should have requirements defined."""
        for strategy in SelectorStrategy:
            assert strategy in STRATEGY_REQUIREMENTS, (
                f"Missing requirements for {strategy}"
            )

    def test_civitai_file_requires_three_ids(self):
        reqs = STRATEGY_REQUIREMENTS[SelectorStrategy.CIVITAI_FILE]
        fields = [r[0] for r in reqs]
        assert "civitai.model_id" in fields
        assert "civitai.version_id" in fields
        assert "civitai.file_id" in fields

    def test_huggingface_requires_repo_and_filename(self):
        reqs = STRATEGY_REQUIREMENTS[SelectorStrategy.HUGGINGFACE_FILE]
        fields = [r[0] for r in reqs]
        assert "huggingface.repo_id" in fields
        assert "huggingface.filename" in fields

    def test_local_file_requires_path(self):
        reqs = STRATEGY_REQUIREMENTS[SelectorStrategy.LOCAL_FILE]
        fields = [r[0] for r in reqs]
        assert "local_path" in fields

    def test_url_download_requires_url(self):
        reqs = STRATEGY_REQUIREMENTS[SelectorStrategy.URL_DOWNLOAD]
        fields = [r[0] for r in reqs]
        assert "url" in fields

    def test_base_model_hint_requires_base_model(self):
        reqs = STRATEGY_REQUIREMENTS[SelectorStrategy.BASE_MODEL_HINT]
        fields = [r[0] for r in reqs]
        assert "base_model" in fields


class TestValidateSelectorFields:
    def test_valid_civitai_file(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=123, version_id=456, file_id=789),
        )
        result = validate_selector_fields(sel)
        assert result.success is True

    def test_civitai_file_missing_file_id(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=123, version_id=456),
        )
        result = validate_selector_fields(sel)
        assert result.success is False
        assert "file ID" in result.message

    def test_civitai_file_missing_all(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
        )
        result = validate_selector_fields(sel)
        assert result.success is False
        # Should report the first missing field
        assert "model ID" in result.message

    def test_civitai_model_latest_valid(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
            civitai=CivitaiSelector(model_id=123),
        )
        result = validate_selector_fields(sel)
        assert result.success is True

    def test_civitai_model_latest_missing(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_MODEL_LATEST,
        )
        result = validate_selector_fields(sel)
        assert result.success is False

    def test_huggingface_valid(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.HUGGINGFACE_FILE,
            huggingface=HuggingFaceSelector(
                repo_id="stabilityai/sdxl", filename="model.safetensors"
            ),
        )
        result = validate_selector_fields(sel)
        assert result.success is True

    def test_huggingface_missing_selector(self):
        """HuggingFace strategy without huggingface selector at all."""
        sel = DependencySelector(
            strategy=SelectorStrategy.HUGGINGFACE_FILE,
        )
        result = validate_selector_fields(sel)
        assert result.success is False
        assert "repo ID" in result.message

    def test_local_file_valid(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.LOCAL_FILE,
            local_path="/models/test.safetensors",
        )
        result = validate_selector_fields(sel)
        assert result.success is True

    def test_local_file_missing_path(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.LOCAL_FILE,
        )
        result = validate_selector_fields(sel)
        assert result.success is False

    def test_local_file_empty_path(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.LOCAL_FILE,
            local_path="",
        )
        result = validate_selector_fields(sel)
        assert result.success is False

    def test_url_download_valid(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.URL_DOWNLOAD,
            url="https://example.com/model.safetensors",
        )
        result = validate_selector_fields(sel)
        assert result.success is True

    def test_url_download_missing(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.URL_DOWNLOAD,
        )
        result = validate_selector_fields(sel)
        assert result.success is False

    def test_base_model_hint_valid(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.BASE_MODEL_HINT,
            base_model="SDXL",
        )
        result = validate_selector_fields(sel)
        assert result.success is True

    def test_base_model_hint_missing(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.BASE_MODEL_HINT,
        )
        result = validate_selector_fields(sel)
        assert result.success is False


class TestValidateCandidate:
    def test_valid_civitai_compatible(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=1, version_id=2, file_id=3),
        )
        result = validate_candidate(sel, AssetKind.LORA, "SDXL", "SDXL")
        assert result.success is True
        assert result.compatibility_warnings == []

    def test_valid_civitai_incompatible_warns(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=1, version_id=2, file_id=3),
        )
        result = validate_candidate(sel, AssetKind.LORA, "SDXL", "SD 1.5")
        assert result.success is True  # Warnings don't block
        assert len(result.compatibility_warnings) == 1
        assert "mismatch" in result.compatibility_warnings[0].lower()

    def test_invalid_selector_blocks(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
        )
        result = validate_candidate(sel, AssetKind.LORA, "SDXL", "SDXL")
        assert result.success is False
        assert result.compatibility_warnings == []  # Never reached

    def test_checkpoint_no_compat_check(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=1, version_id=2, file_id=3),
        )
        result = validate_candidate(sel, AssetKind.CHECKPOINT, "SDXL", "SD 1.5")
        assert result.success is True
        assert result.compatibility_warnings == []

    def test_unknown_base_models_no_warning(self):
        sel = DependencySelector(
            strategy=SelectorStrategy.LOCAL_FILE,
            local_path="/models/test.safetensors",
        )
        result = validate_candidate(sel, AssetKind.LORA, None, None)
        assert result.success is True
        assert result.compatibility_warnings == []


class TestValidateBeforeApply:
    def test_is_alias_for_validate_candidate(self):
        """validate_before_apply should produce the same result as validate_candidate."""
        sel = DependencySelector(
            strategy=SelectorStrategy.CIVITAI_FILE,
            civitai=CivitaiSelector(model_id=1, version_id=2, file_id=3),
        )
        r1 = validate_candidate(sel, AssetKind.LORA, "SDXL", "SDXL")
        r2 = validate_before_apply(sel, AssetKind.LORA, "SDXL", "SDXL")
        assert r1.success == r2.success
        assert r1.message == r2.message
        assert r1.compatibility_warnings == r2.compatibility_warnings
