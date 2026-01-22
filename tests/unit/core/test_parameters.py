"""
Unit tests for Pack parameters handling.

Tests cover:
1. Pack model - parameters load/save
2. Parameters serialization/deserialization
3. Workflow generator - parameter usage
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.models import (
    Pack, PackMetadata, GenerationParameters, ModelInfo,
    AssetDependency, AssetType, AssetSource, DependencyStatus
)


class TestGenerationParameters:
    """Test GenerationParameters model."""
    
    def test_create_empty_parameters(self):
        """Test creating parameters with no values."""
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
    
    def test_create_parameters_with_values(self):
        """Test creating parameters with specific values."""
        params = GenerationParameters(
            sampler="euler",
            scheduler="normal",
            steps=20,
            cfg_scale=7.0,
            clip_skip=2,
            denoise=1.0,
            width=512,
            height=768,
            seed=12345
        )
        assert params.sampler == "euler"
        assert params.scheduler == "normal"
        assert params.steps == 20
        assert params.cfg_scale == 7.0
        assert params.clip_skip == 2
        assert params.denoise == 1.0
        assert params.width == 512
        assert params.height == 768
        assert params.seed == 12345
    
    def test_parameters_to_dict(self):
        """Test serialization to dict."""
        params = GenerationParameters(
            sampler="euler",
            steps=20,
            cfg_scale=7.0
        )
        d = params.to_dict()
        
        assert d["sampler"] == "euler"
        assert d["steps"] == 20
        assert d["cfg_scale"] == 7.0
        # None values should not be in dict
        assert "scheduler" not in d or d["scheduler"] is None
    
    def test_parameters_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "sampler": "dpmpp_2m",
            "steps": 30,
            "cfg_scale": 5.5,
            "clip_skip": 2
        }
        params = GenerationParameters.from_dict(data)
        
        assert params.sampler == "dpmpp_2m"
        assert params.steps == 30
        assert params.cfg_scale == 5.5
        assert params.clip_skip == 2
        assert params.scheduler is None
    
    def test_parameters_from_empty_dict(self):
        """Test deserialization from empty dict."""
        params = GenerationParameters.from_dict({})
        assert params.sampler is None
        assert params.steps is None


class TestModelInfo:
    """Test ModelInfo model."""
    
    def test_create_model_info(self):
        """Test creating ModelInfo with strength_recommended."""
        info = ModelInfo(
            model_type="LoRA",
            base_model="SD 1.5",
            strength_recommended=0.8
        )
        assert info.model_type == "LoRA"
        assert info.base_model == "SD 1.5"
        assert info.strength_recommended == 0.8
    
    def test_model_info_to_dict(self):
        """Test serialization."""
        info = ModelInfo(
            model_type="Checkpoint",
            trigger_words=["test", "trigger"],
            strength_recommended=1.0
        )
        d = info.to_dict()
        
        assert d["model_type"] == "Checkpoint"
        assert d["trigger_words"] == ["test", "trigger"]
        assert d["strength_recommended"] == 1.0


class TestPackParameters:
    """Test Pack with parameters."""
    
    def test_pack_with_parameters(self):
        """Test creating pack with parameters."""
        pack = Pack(
            metadata=PackMetadata(name="test-pack", description="Test"),
            parameters=GenerationParameters(
                sampler="euler",
                steps=20,
                cfg_scale=7.0
            )
        )
        
        assert pack.parameters is not None
        assert pack.parameters.sampler == "euler"
        assert pack.parameters.steps == 20
    
    def test_pack_with_model_info(self):
        """Test creating pack with model_info."""
        pack = Pack(
            metadata=PackMetadata(name="test-lora", description="Test LoRA"),
            model_info=ModelInfo(
                model_type="LoRA",
                strength_recommended=0.75
            )
        )
        
        assert pack.model_info is not None
        assert pack.model_info.strength_recommended == 0.75
    
    def test_pack_save_load_with_parameters(self):
        """Test saving and loading pack with parameters."""
        pack = Pack(
            metadata=PackMetadata(name="test-pack", description="Test"),
            parameters=GenerationParameters(
                sampler="dpmpp_2m",
                scheduler="karras",
                steps=25,
                cfg_scale=6.5,
                clip_skip=2
            ),
            model_info=ModelInfo(
                model_type="LoRA",
                strength_recommended=0.8,
                trigger_words=["test_trigger"]
            )
        )
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            json.dump(pack.to_dict(), f, indent=2)
            temp_path = Path(f.name)
        
        try:
            # Load back
            loaded = Pack.load(temp_path)
            
            # Verify parameters
            assert loaded.parameters is not None
            assert loaded.parameters.sampler == "dpmpp_2m"
            assert loaded.parameters.scheduler == "karras"
            assert loaded.parameters.steps == 25
            assert loaded.parameters.cfg_scale == 6.5
            assert loaded.parameters.clip_skip == 2
            
            # Verify model_info
            assert loaded.model_info is not None
            assert loaded.model_info.model_type == "LoRA"
            assert loaded.model_info.strength_recommended == 0.8
            assert loaded.model_info.trigger_words == ["test_trigger"]
        finally:
            temp_path.unlink()
    
    def test_pack_update_parameters(self):
        """Test updating pack parameters."""
        pack = Pack(
            metadata=PackMetadata(name="test", description="Test"),
            parameters=GenerationParameters(steps=20)
        )
        
        # Update parameters
        pack.parameters.sampler = "euler"
        pack.parameters.cfg_scale = 7.5
        
        assert pack.parameters.steps == 20
        assert pack.parameters.sampler == "euler"
        assert pack.parameters.cfg_scale == 7.5
    
    def test_pack_to_dict_parameters_serialization(self):
        """Test that pack.to_dict() correctly serializes parameters."""
        pack = Pack(
            metadata=PackMetadata(name="test", description="Test"),
            parameters=GenerationParameters(
                sampler="euler",
                steps=20,
                clip_skip=2
            )
        )
        
        d = pack.to_dict()
        
        assert "parameters" in d
        assert d["parameters"]["sampler"] == "euler"
        assert d["parameters"]["steps"] == 20
        assert d["parameters"]["clip_skip"] == 2


class TestParametersForWorkflowGenerator:
    """Test parameters in context of workflow generator."""
    
    def test_clip_skip_only_when_set(self):
        """Test that clip_skip is only used when explicitly set."""
        # Pack without clip_skip
        pack1 = Pack(
            metadata=PackMetadata(name="test1", description="Test"),
            parameters=GenerationParameters(steps=20, sampler="euler")
        )
        assert pack1.parameters.clip_skip is None
        
        # Pack with clip_skip
        pack2 = Pack(
            metadata=PackMetadata(name="test2", description="Test"),
            parameters=GenerationParameters(steps=20, clip_skip=2)
        )
        assert pack2.parameters.clip_skip == 2
    
    def test_parameters_defaults_not_assumed(self):
        """Test that None parameters are not assumed to have defaults."""
        pack = Pack(
            metadata=PackMetadata(name="test", description="Test"),
            parameters=GenerationParameters()
        )
        
        # All should be None, not default values
        assert pack.parameters.sampler is None
        assert pack.parameters.steps is None
        assert pack.parameters.cfg_scale is None
        assert pack.parameters.clip_skip is None
    
    def test_strength_from_model_info(self):
        """Test that strength comes from model_info, not parameters."""
        pack = Pack(
            metadata=PackMetadata(name="test-lora", description="Test"),
            model_info=ModelInfo(strength_recommended=0.75),
            parameters=GenerationParameters(steps=20)
        )
        
        # Strength is in model_info, not parameters
        assert pack.model_info.strength_recommended == 0.75
        # Parameters don't have strength (it's separate)
        assert not hasattr(pack.parameters, 'strength')


class TestParametersEdgeCases:
    """Test edge cases for parameters."""
    
    def test_zero_values_are_valid(self):
        """Test that zero is a valid value for numeric parameters."""
        params = GenerationParameters(
            steps=0,  # Edge case
            cfg_scale=0.0,
            clip_skip=0
        )
        assert params.steps == 0
        assert params.cfg_scale == 0.0
        assert params.clip_skip == 0
    
    def test_negative_seed(self):
        """Test handling of negative seed (random seed indicator)."""
        params = GenerationParameters(seed=-1)
        assert params.seed == -1
    
    def test_large_values(self):
        """Test large values for parameters."""
        params = GenerationParameters(
            steps=150,
            cfg_scale=30.0,
            width=2048,
            height=2048,
            seed=999999999999
        )
        assert params.steps == 150
        assert params.width == 2048
        assert params.seed == 999999999999
    
    def test_float_vs_int_cfg_scale(self):
        """Test that cfg_scale can be float or int."""
        params1 = GenerationParameters(cfg_scale=7)
        params2 = GenerationParameters(cfg_scale=7.5)
        
        assert params1.cfg_scale == 7
        assert params2.cfg_scale == 7.5


class TestCivitaiParametersExtraction:
    """Test parameters extraction from Civitai-like metadata."""
    
    def test_extract_from_civitai_meta(self):
        """Test extracting parameters from Civitai image metadata format."""
        # Simulate Civitai meta structure
        civitai_meta = {
            "sampler": "DPM++ 2M Karras",
            "cfgScale": 7,
            "steps": 20,
            "clipSkip": 2,
            "seed": 12345678,
            "Size": "512x768"
        }
        
        # Extract parameters (simulating pack_builder logic)
        params = GenerationParameters(
            sampler=civitai_meta.get("sampler"),
            steps=civitai_meta.get("steps"),
            cfg_scale=civitai_meta.get("cfgScale"),
            clip_skip=civitai_meta.get("clipSkip"),
            seed=civitai_meta.get("seed"),
        )
        
        assert params.sampler == "DPM++ 2M Karras"
        assert params.steps == 20
        assert params.cfg_scale == 7
        assert params.clip_skip == 2
        assert params.seed == 12345678
    
    def test_civitai_meta_with_all_fields(self):
        """Test full Civitai metadata extraction."""
        civitai_meta = {
            "sampler": "Euler a",
            "scheduler": "karras",
            "cfgScale": 5.5,
            "steps": 30,
            "clipSkip": 1,
            "seed": 987654321,
            "width": 1024,
            "height": 1024,
            "denoise": 0.7,
            "hiresFix": True,
            "hiresUpscaler": "4x-UltraSharp",
            "hiresSteps": 15,
            "hiresDenoising": 0.45
        }
        
        params = GenerationParameters(
            sampler=civitai_meta.get("sampler"),
            scheduler=civitai_meta.get("scheduler"),
            steps=civitai_meta.get("steps"),
            cfg_scale=civitai_meta.get("cfgScale"),
            clip_skip=civitai_meta.get("clipSkip"),
            seed=civitai_meta.get("seed"),
            width=civitai_meta.get("width"),
            height=civitai_meta.get("height"),
            denoise=civitai_meta.get("denoise"),
            hires_fix=bool(civitai_meta.get("hiresFix")),
            hires_upscaler=civitai_meta.get("hiresUpscaler"),
            hires_steps=civitai_meta.get("hiresSteps"),
            hires_denoise=civitai_meta.get("hiresDenoising"),
        )
        
        assert params.sampler == "Euler a"
        assert params.scheduler == "karras"
        assert params.cfg_scale == 5.5
        assert params.steps == 30
        assert params.clip_skip == 1
        assert params.width == 1024
        assert params.height == 1024
        assert params.denoise == 0.7
        assert params.hires_fix == True
        assert params.hires_upscaler == "4x-UltraSharp"
        assert params.hires_steps == 15
        assert params.hires_denoise == 0.45
    
    def test_civitai_meta_to_dict_preserves_all(self):
        """Test that to_dict preserves all extracted Civitai parameters."""
        params = GenerationParameters(
            sampler="DPM++ SDE",
            scheduler="normal",
            steps=25,
            cfg_scale=8.0,
            clip_skip=2,
            width=768,
            height=1024,
            seed=555555,
            denoise=1.0,
        )
        
        d = params.to_dict()
        
        assert d["sampler"] == "DPM++ SDE"
        assert d["scheduler"] == "normal"
        assert d["steps"] == 25
        assert d["cfg_scale"] == 8.0
        assert d["clip_skip"] == 2
        assert d["width"] == 768
        assert d["height"] == 1024
        assert d["seed"] == 555555
        assert d["denoise"] == 1.0
    
    def test_save_load_civitai_parameters(self):
        """Test full round-trip: extract -> save -> load -> verify."""
        # Create pack with Civitai-extracted parameters
        pack = Pack(
            metadata=PackMetadata(name="civitai-lora", description="LoRA from Civitai"),
            parameters=GenerationParameters(
                sampler="DPM++ 2M Karras",
                steps=20,
                cfg_scale=7.0,
                clip_skip=2,
                width=512,
                height=768,
                seed=12345678,
            ),
            model_info=ModelInfo(
                model_type="LoRA",
                base_model="SD 1.5",
                strength_recommended=0.8,
                trigger_words=["test_trigger"],
            )
        )
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            json.dump(pack.to_dict(), f, indent=2)
            temp_path = Path(f.name)
        
        try:
            # Load back
            loaded = Pack.load(temp_path)
            
            # Verify ALL parameters were preserved
            assert loaded.parameters is not None
            assert loaded.parameters.sampler == "DPM++ 2M Karras"
            assert loaded.parameters.steps == 20
            assert loaded.parameters.cfg_scale == 7.0
            assert loaded.parameters.clip_skip == 2
            assert loaded.parameters.width == 512
            assert loaded.parameters.height == 768
            assert loaded.parameters.seed == 12345678
            
            # Verify model_info
            assert loaded.model_info is not None
            assert loaded.model_info.strength_recommended == 0.8
            assert loaded.model_info.trigger_words == ["test_trigger"]
        finally:
            temp_path.unlink()
    
    def test_empty_civitai_meta(self):
        """Test handling of empty metadata."""
        params = GenerationParameters.from_dict({})
        
        assert params.sampler is None
        assert params.steps is None
        assert params.cfg_scale is None
        assert params.clip_skip is None
    
    def test_partial_civitai_meta(self):
        """Test partial metadata - only some fields present."""
        partial_meta = {
            "cfgScale": 7,
            "steps": 20
        }
        
        params = GenerationParameters(
            cfg_scale=partial_meta.get("cfgScale"),
            steps=partial_meta.get("steps"),
        )
        
        assert params.cfg_scale == 7
        assert params.steps == 20
        assert params.sampler is None
        assert params.clip_skip is None
        
        # to_dict should only include set values
        d = params.to_dict()
        assert "cfg_scale" in d
        assert "steps" in d
        assert "sampler" not in d or d.get("sampler") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
