"""
Integration tests for AI parameter extraction flow.

Tests the complete flow from AI response → GenerationParameters → Pack
to ensure no data is lost and normalization works correctly.
"""

import pytest
import json
from pathlib import Path


class TestAIParameterExtractionIntegration:
    """Integration tests for parameter extraction normalization."""

    def test_cache_data_through_generation_parameters(self):
        """Test that cached AI responses are properly normalized.

        This reproduces the bug where clip_skip: [1, 2] and hires_fix: [{...}]
        from cache caused validation errors.
        """
        from src.store.models import GenerationParameters

        # Simulated cache data (actual format from Gemini)
        cache_result = {
            "sampler": ["DPM++ series"],
            "steps": {"min": 20, "max": 30},
            "cfg_scale": {"min": 5, "max": 7, "recommended": 7},
            "hires_fix": [
                {"upscale_by": 2, "denoising_strength": {"min": 0.4, "max": 0.5}},
                {"upscale_by": 1.5, "denoising_strength": {"min": 0.5, "max": 0.65}},
            ],
            "clip_skip": [1, 2],
            "vae": ["kl-f8-anime2", "vae-ft-mse-840000-ema-pruned"],
            "negative_embeddings": ["ng_deepnegative_v1_75t", "easynegative"],
            "_extracted_by": "gemini",
        }

        # This should NOT raise validation error
        params = GenerationParameters(**cache_result)

        # Verify normalization worked
        assert params.clip_skip == 1, "clip_skip should be first element of list"
        assert params.hires_fix is True, "hires_fix should be True from dict"
        assert params.sampler == "DPM++ series", "sampler should be first element"
        assert params.steps == 30, "steps should be max from range dict"
        assert params.cfg_scale == 7, "cfg_scale should be recommended"

        # Verify extra fields preserved
        assert params.__pydantic_extra__ is not None
        assert "vae" in params.__pydantic_extra__
        assert "_extracted_by" in params.__pydantic_extra__

    def test_unconvertible_values_preserved(self):
        """Test that values which can't be converted don't cause errors."""
        from src.store.models import GenerationParameters

        data = {
            "sampler": "Euler a",
            "steps": 20,
            "clip_skip": "varies by model",  # Can't convert to int
            "cfg_scale": "between 5 and 8",  # Can't convert to float
        }

        # Should NOT raise
        params = GenerationParameters(**data)

        assert params.sampler == "Euler a"
        assert params.steps == 20
        assert params.clip_skip is None  # Can't convert, removed
        assert params.cfg_scale is None  # Can't convert, removed

        # Original values preserved in _raw_ fields
        assert params.__pydantic_extra__.get("_raw_clip_skip") == "varies by model"
        assert params.__pydantic_extra__.get("_raw_cfg_scale") == "between 5 and 8"

    def test_complex_hires_fix_normalization(self):
        """Test hires_fix normalization with nested dicts."""
        from src.store.models import GenerationParameters

        # AI returns list of hires configs
        data = {
            "steps": 20,
            "hires_fix": [
                {
                    "upscale_by": 2,
                    "denoising_strength": 0.5,
                    "steps": 15,
                }
            ],
        }

        params = GenerationParameters(**data)

        assert params.hires_fix is True
        assert params.hires_denoise == 0.5
        assert params.hires_steps == 15

    def test_full_flow_with_task_result(self):
        """Test full flow from TaskResult to Pack parameters."""
        from src.store.models import GenerationParameters
        from src.ai.tasks.base import TaskResult

        # Simulate TaskResult from AIService
        output = {
            "sampler": ["DPM++ 2M Karras", "Euler a"],
            "steps": {"min": 15, "max": 30, "recommended": 20},
            "cfg_scale": [7.0, 8.0],
            "clip_skip": [1, 2],
            "hires_fix": [{"upscale_by": 2, "denoising_strength": 0.5}],
            "compatibility": "Works best with SD 1.5",
            "warnings": "May produce artifacts at high CFG",
            "_extracted_by": "gemini",
        }

        result = TaskResult(
            success=True,
            output=output,
            provider_id="gemini",
            model="gemini-1.5-flash",
        )

        # This is what pack_service.py does
        assert result.success and result.output

        # Create GenerationParameters (this was failing before fix)
        params = GenerationParameters(**result.output)

        # Verify all values normalized correctly
        assert params.sampler == "DPM++ 2M Karras"
        assert params.steps == 20
        assert params.cfg_scale == 7.0
        assert params.clip_skip == 1
        assert params.hires_fix is True
        assert params.hires_denoise == 0.5

        # Verify AI notes preserved
        assert params.__pydantic_extra__.get("compatibility") == "Works best with SD 1.5"
        assert params.__pydantic_extra__.get("warnings") == "May produce artifacts at high CFG"
        assert params.__pydantic_extra__.get("_extracted_by") == "gemini"

    def test_serialization_roundtrip(self):
        """Test that normalized parameters can be serialized and loaded."""
        from src.store.models import GenerationParameters

        # Create params from AI-like data
        data = {
            "sampler": ["DPM++ 2M"],
            "steps": 20,
            "clip_skip": [1, 2],
            "compatibility": "SD 1.5",
        }

        params = GenerationParameters(**data)

        # Serialize using Pydantic
        serialized = params.model_dump(exclude_none=True)

        # Should have normalized values
        assert serialized["sampler"] == "DPM++ 2M"
        assert serialized["clip_skip"] == 1
        assert "compatibility" in serialized  # Extra field preserved

        # Can recreate from serialized (no lists anymore)
        params2 = GenerationParameters(**serialized)
        assert params2.sampler == "DPM++ 2M"
        assert params2.clip_skip == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
