"""
Tests for GenerationParameters Pydantic model.

Verifies:
- No ghost values (hires_fix=False when not set)
- Proper serialization with model_dump()
- Custom serializer excludes None values
"""

import pytest
from src.store.models import GenerationParameters, Pack, PackSource, AssetKind


def make_test_pack(**kwargs) -> Pack:
    """Helper to create a test Pack with required fields."""
    defaults = {
        "name": "test-pack",
        "pack_type": AssetKind.LORA,
        "source": PackSource(provider="local"),
    }
    defaults.update(kwargs)
    return Pack(**defaults)


class TestGenerationParametersModel:
    """Tests for Pydantic GenerationParameters model."""

    def test_default_values_are_none(self):
        """Test that all default values are None."""
        params = GenerationParameters()

        assert params.sampler is None
        assert params.scheduler is None
        assert params.steps is None
        assert params.cfg_scale is None
        assert params.clip_skip is None
        assert params.denoise is None
        assert params.width is None
        assert params.height is None
        assert params.seed is None
        assert params.hires_fix is None
        assert params.hires_upscaler is None
        assert params.hires_steps is None
        assert params.hires_denoise is None

    def test_serialization_excludes_none_values(self):
        """Test that model_dump() excludes None values via custom serializer."""
        params = GenerationParameters(
            steps=20,
            cfg_scale=7.0,
        )

        d = params.model_dump()

        # Only set values should be in output
        assert d == {"steps": 20, "cfg_scale": 7.0}
        assert "hires_fix" not in d
        assert "sampler" not in d

    def test_hires_fix_none_not_serialized(self):
        """Test that hires_fix=None is NOT included in serialized output."""
        params = GenerationParameters(steps=20)

        d = params.model_dump()

        assert "hires_fix" not in d, "hires_fix=None should NOT appear in output"

    def test_hires_fix_true_serialized(self):
        """Test that hires_fix=True IS included."""
        params = GenerationParameters(
            steps=20,
            hires_fix=True,
        )

        d = params.model_dump()

        assert "hires_fix" in d
        assert d["hires_fix"] is True

    def test_hires_fix_false_serialized(self):
        """Test that hires_fix=False IS included (explicit value)."""
        params = GenerationParameters(
            steps=20,
            hires_fix=False,
        )

        d = params.model_dump()

        assert "hires_fix" in d
        assert d["hires_fix"] is False

    def test_no_ghost_parameters_in_empty_object(self):
        """Test that empty GenerationParameters serializes to empty dict."""
        params = GenerationParameters()

        d = params.model_dump()

        assert d == {}

    def test_all_hires_params_when_set(self):
        """Test all hires parameters are serialized when explicitly set."""
        params = GenerationParameters(
            hires_fix=True,
            hires_upscaler="4x-UltraSharp",
            hires_steps=15,
            hires_denoise=0.45,
        )

        d = params.model_dump()

        assert d["hires_fix"] is True
        assert d["hires_upscaler"] == "4x-UltraSharp"
        assert d["hires_steps"] == 15
        assert d["hires_denoise"] == 0.45

    def test_json_serialization(self):
        """Test JSON serialization via model_dump(mode='json')."""
        params = GenerationParameters(
            steps=20,
            cfg_scale=7.5,
            hires_fix=True,
        )

        d = params.model_dump(mode="json")

        assert d == {"steps": 20, "cfg_scale": 7.5, "hires_fix": True}


class TestPackWithParameters:
    """Tests for Pack model with GenerationParameters."""

    def test_pack_parameters_serialization(self):
        """Test that Pack with parameters serializes correctly."""
        pack = make_test_pack(
            parameters=GenerationParameters(
                steps=20,
                cfg_scale=7.0,
            ),
        )

        d = pack.model_dump()

        # Parameters should not contain None values
        assert "parameters" in d
        assert d["parameters"] == {"steps": 20, "cfg_scale": 7.0}
        assert "hires_fix" not in d["parameters"]

    def test_pack_no_ghost_hires_fix(self):
        """Test that Pack doesn't have ghost hires_fix after save/load simulation."""
        pack = make_test_pack(
            pack_type=AssetKind.CHECKPOINT,
            parameters=GenerationParameters(
                sampler="Euler a",
                steps=30,
            ),
        )

        # Simulate save: convert to dict
        saved = pack.model_dump(by_alias=True)

        # hires_fix should NOT be in the saved data
        assert "hires_fix" not in saved["parameters"]

        # Simulate load: validate from dict
        loaded = Pack.model_validate(saved)

        # After load, hires_fix should be None
        assert loaded.parameters is not None
        assert loaded.parameters.hires_fix is None

    def test_pack_with_explicit_hires_fix(self):
        """Test Pack with explicitly set hires_fix."""
        pack = make_test_pack(
            name="hires-pack",
            pack_type=AssetKind.CHECKPOINT,
            parameters=GenerationParameters(
                steps=30,
                hires_fix=True,
                hires_upscaler="Latent",
            ),
        )

        d = pack.model_dump()

        assert d["parameters"]["hires_fix"] is True
        assert d["parameters"]["hires_upscaler"] == "Latent"

    def test_pack_null_parameters(self):
        """Test Pack with null parameters."""
        pack = make_test_pack(
            parameters=None,
        )

        d = pack.model_dump()

        assert d["parameters"] is None


class TestGenerationParametersRoundTrip:
    """Tests for round-trip serialization/deserialization."""

    def test_roundtrip_with_all_values(self):
        """Test round-trip with all values set."""
        original = GenerationParameters(
            sampler="DPM++ 2M",
            scheduler="karras",
            steps=25,
            cfg_scale=7.5,
            clip_skip=2,
            denoise=1.0,
            width=512,
            height=768,
            seed=12345,
            hires_fix=True,
            hires_upscaler="4x-UltraSharp",
            hires_steps=15,
            hires_denoise=0.5,
        )

        # Serialize
        d = original.model_dump()

        # Deserialize
        loaded = GenerationParameters.model_validate(d)

        # Verify all values
        assert loaded.sampler == original.sampler
        assert loaded.scheduler == original.scheduler
        assert loaded.steps == original.steps
        assert loaded.cfg_scale == original.cfg_scale
        assert loaded.clip_skip == original.clip_skip
        assert loaded.denoise == original.denoise
        assert loaded.width == original.width
        assert loaded.height == original.height
        assert loaded.seed == original.seed
        assert loaded.hires_fix == original.hires_fix
        assert loaded.hires_upscaler == original.hires_upscaler
        assert loaded.hires_steps == original.hires_steps
        assert loaded.hires_denoise == original.hires_denoise

    def test_roundtrip_with_minimal_values(self):
        """Test round-trip with minimal values."""
        original = GenerationParameters(steps=20)

        d = original.model_dump()
        loaded = GenerationParameters.model_validate(d)

        assert loaded.steps == 20
        assert loaded.hires_fix is None

    def test_roundtrip_preserves_empty(self):
        """Test that empty params stay empty after round-trip."""
        original = GenerationParameters()

        d = original.model_dump()
        loaded = GenerationParameters.model_validate(d)

        # All should be None
        assert loaded.steps is None
        assert loaded.hires_fix is None
