"""
Tests for preview_meta_extractor.py — sidecar JSON + PNG tEXt parsing.

Covers:
- BUG 7 fix: flat vs wrapped sidecar format
- BUG 8 fix: sidecar path resolution (tested via integration)
- Enhanced sidecar parsing: hash, weight, LoRA tags from prompt
- ComfyUI node registry: multi-model nodes, new node types
- analyze_pack_previews() function
"""

import json
import pytest
from pathlib import Path
from typing import Dict
from unittest.mock import patch, MagicMock

from src.store.models import AssetKind
from src.utils.preview_meta_extractor import (
    COMFYUI_NODE_REGISTRY,
    ComfyUINodeDef,
    _PNG_SIGNATURE,
    _read_png_text_chunks,
    analyze_pack_previews,
    extract_preview_hints,
    filter_hints_by_kind,
    _normalize_filename,
    _parse_a1111_parameters,
    _parse_comfyui_workflow,
    _parse_power_lora_loader,
    _parse_sidecar_meta,
    _extract_generation_params,
    _extract_generation_params_from_data,
    _sanitize_filename,
)


# =============================================================================
# Security: Path traversal prevention
# =============================================================================

class TestSanitizeFilename:
    def test_normal_filename(self):
        assert _sanitize_filename("001.jpeg") == "001.jpeg"

    def test_rejects_path_traversal(self):
        assert _sanitize_filename("../../etc/passwd") is None

    def test_rejects_forward_slash(self):
        assert _sanitize_filename("subdir/file.json") is None

    def test_rejects_backslash(self):
        assert _sanitize_filename("subdir\\file.json") is None

    def test_rejects_dotdot(self):
        assert _sanitize_filename("..") is None

    def test_rejects_empty(self):
        assert _sanitize_filename("") is None

    def test_path_traversal_in_extract_hints(self, tmp_path):
        """Path traversal filename returns empty hints, no crash."""
        previews = tmp_path / "previews"
        previews.mkdir()
        hints = extract_preview_hints(previews, ["../../etc/passwd"])
        assert hints == []


# =============================================================================
# BUG 9: PNG files with .jpeg extension
# =============================================================================

class TestPngMagicBytesDetection:
    """BUG 9: Civitai serves PNG files with .jpeg extension."""

    def _make_png_with_text(self, path: Path, text_chunks: Dict[str, str]):
        """Create a minimal PNG file with tEXt chunks."""
        import struct
        import zlib

        with open(path, "wb") as f:
            # PNG signature
            f.write(_PNG_SIGNATURE)

            # IHDR chunk (1x1 RGB)
            ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
            f.write(struct.pack(">I", len(ihdr_data)))
            f.write(b"IHDR")
            f.write(ihdr_data)
            f.write(struct.pack(">I", ihdr_crc))

            # tEXt chunks
            for key, value in text_chunks.items():
                text_data = key.encode("latin-1") + b"\x00" + value.encode("utf-8")
                text_crc = zlib.crc32(b"tEXt" + text_data) & 0xFFFFFFFF
                f.write(struct.pack(">I", len(text_data)))
                f.write(b"tEXt")
                f.write(text_data)
                f.write(struct.pack(">I", text_crc))

            # IEND chunk
            iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
            f.write(struct.pack(">I", 0))
            f.write(b"IEND")
            f.write(struct.pack(">I", iend_crc))

    def test_reads_png_text_chunks(self, tmp_path):
        """Basic PNG tEXt chunk reading."""
        png = tmp_path / "test.png"
        self._make_png_with_text(png, {"parameters": "Model: test_model"})
        chunks = _read_png_text_chunks(png)
        assert "parameters" in chunks
        assert "test_model" in chunks["parameters"]

    def test_jpeg_extension_png_content(self, tmp_path):
        """PNG file with .jpeg extension — tEXt chunks still read."""
        jpeg_path = tmp_path / "image.jpeg"
        self._make_png_with_text(jpeg_path, {"parameters": "Model: hidden_model, Model hash: abc123"})
        chunks = _read_png_text_chunks(jpeg_path)
        assert "parameters" in chunks
        assert "hidden_model" in chunks["parameters"]

    def test_real_jpeg_returns_empty(self, tmp_path):
        """Actual JPEG file (not PNG) returns empty dict."""
        jpeg_path = tmp_path / "real.jpeg"
        # JPEG starts with FF D8 FF
        jpeg_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        chunks = _read_png_text_chunks(jpeg_path)
        assert chunks == {}

    def test_extract_hints_from_jpeg_extension_png(self, tmp_path):
        """Full extract_preview_hints works on PNG-with-.jpeg-extension."""
        previews = tmp_path / "previews"
        previews.mkdir()

        # Create a PNG file with .jpeg extension containing A1111 params
        self._make_png_with_text(
            previews / "001.jpeg",
            {"parameters": "Model: illustriousXL, Model hash: abc123\nSteps: 20"}
        )

        hints = extract_preview_hints(previews, ["001.jpeg"])
        # Should find the checkpoint from PNG tEXt even though extension is .jpeg
        png_hints = [h for h in hints if h.source_type == "png_embedded"]
        assert len(png_hints) >= 1
        assert any(h.filename == "illustriousXL" and h.kind == AssetKind.CHECKPOINT for h in png_hints)

    def test_comfyui_workflow_from_jpeg_extension(self, tmp_path):
        """ComfyUI workflow extracted from PNG-with-.jpeg-extension."""
        previews = tmp_path / "previews"
        previews.mkdir()

        workflow = json.dumps({"1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "model.safetensors"},
        }})
        self._make_png_with_text(previews / "002.jpeg", {"prompt": workflow})

        hints = extract_preview_hints(previews, ["002.jpeg"])
        assert len(hints) >= 1
        assert any(h.filename == "model.safetensors" and h.source_type == "png_embedded" for h in hints)

    def test_nonexistent_file_returns_empty(self, tmp_path):
        """Missing file returns empty chunks, no crash."""
        chunks = _read_png_text_chunks(tmp_path / "nope.png")
        assert chunks == {}


# =============================================================================
# Power Lora Loader (rgthree)
# =============================================================================

class TestPowerLoraLoader:
    """Power Lora Loader from rgthree ComfyUI Impact Pack."""

    def test_enabled_lora_extracted(self):
        """Enabled LoRA is extracted with weight."""
        inputs = {
            "lora_1": {"on": True, "lora": "my_lora.safetensors", "strength": 0.8},
        }
        hints = _parse_power_lora_loader(inputs, "test.png")
        assert len(hints) == 1
        assert hints[0].filename == "my_lora.safetensors"
        assert hints[0].kind == AssetKind.LORA
        assert hints[0].weight == 0.8

    def test_disabled_lora_skipped(self):
        """Disabled LoRA (on=false) is not extracted."""
        inputs = {
            "lora_1": {"on": False, "lora": "disabled.safetensors", "strength": 1.0},
        }
        hints = _parse_power_lora_loader(inputs, "test.png")
        assert len(hints) == 0

    def test_multiple_loras_mixed(self):
        """Multiple LoRAs — only enabled ones extracted."""
        inputs = {
            "lora_1": {"on": False, "lora": "off.safetensors", "strength": 1.0},
            "lora_2": {"on": True, "lora": "on.safetensors", "strength": 0.6},
            "lora_3": {"on": True, "lora": "also_on.safetensors", "strength": 1.0},
            "model": ["1", 0],  # Non-lora input, should be ignored
        }
        hints = _parse_power_lora_loader(inputs, "test.png")
        assert len(hints) == 2
        names = {h.filename for h in hints}
        assert "on.safetensors" in names
        assert "also_on.safetensors" in names

    def test_path_prefix_stripped(self):
        """Path prefix in lora name is normalized."""
        inputs = {
            "lora_1": {"on": True, "lora": "My_Own\\style_lora.safetensors", "strength": 1.0},
        }
        hints = _parse_power_lora_loader(inputs, "test.png")
        assert hints[0].filename == "style_lora.safetensors"

    def test_workflow_integration(self):
        """Power Lora Loader detected in full workflow parse."""
        workflow = json.dumps({
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "62": {
                "class_type": "Power Lora Loader (rgthree)",
                "inputs": {
                    "lora_1": {"on": True, "lora": "my_lora.safetensors", "strength": 0.8},
                    "lora_2": {"on": False, "lora": "off.safetensors", "strength": 1.0},
                    "model": ["1", 0],
                },
            },
        })
        hints = _parse_comfyui_workflow(workflow, "test.png")
        assert len(hints) == 2  # checkpoint + 1 enabled LoRA
        ckpts = [h for h in hints if h.kind == AssetKind.CHECKPOINT]
        loras = [h for h in hints if h.kind == AssetKind.LORA]
        assert len(ckpts) == 1
        assert len(loras) == 1
        assert loras[0].weight == 0.8


class TestNormalizeFilename:
    def test_simple_name(self):
        assert _normalize_filename("model.safetensors") == "model.safetensors"

    def test_strip_path_prefix(self):
        assert _normalize_filename("checkpoints/model.safetensors") == "model.safetensors"

    def test_strip_windows_path(self):
        assert _normalize_filename("models\\checkpoints\\model.safetensors") == "model.safetensors"

    def test_name_without_extension(self):
        assert _normalize_filename("dreamshaper_8") == "dreamshaper_8"

    def test_nested_path(self):
        assert _normalize_filename("sd/xl/model.safetensors") == "model.safetensors"


# =============================================================================
# BUG 7: Flat vs Wrapped Sidecar Format
# =============================================================================

class TestSidecarFormatBug:
    """BUG 7: Flat format sidecar parsing."""

    def test_flat_format_model(self):
        """Top-level Model field extracted (real Civitai sidecar format)."""
        data = {"Model": "juggernaut_xl", "resources": []}
        hints = _parse_sidecar_meta(data, "test.jpeg")
        assert len(hints) == 1
        assert hints[0].kind == AssetKind.CHECKPOINT
        assert hints[0].filename == "juggernaut_xl"

    def test_flat_format_with_resources(self):
        """Flat format: Model + resources[] at top level."""
        data = {
            "Model": "illustriousXL_v060",
            "resources": [
                {"name": "detail_tweaker_xl", "type": "lora", "weight": 0.5},
            ],
        }
        hints = _parse_sidecar_meta(data, "001.jpeg")
        assert len(hints) == 2
        ckpt = [h for h in hints if h.kind == AssetKind.CHECKPOINT]
        lora = [h for h in hints if h.kind == AssetKind.LORA]
        assert len(ckpt) == 1
        assert len(lora) == 1
        assert lora[0].weight == 0.5

    def test_wrapped_format_still_works(self):
        """Legacy {meta: {...}} format still supported."""
        data = {"meta": {"Model": "test_model"}}
        hints = _parse_sidecar_meta(data, "test.jpeg")
        assert len(hints) == 1
        assert hints[0].filename == "test_model"

    def test_both_flat_and_wrapped_prefers_meta(self):
        """If meta dict exists, it takes precedence over flat keys."""
        data = {"meta": {"Model": "from_meta"}, "Model": "from_top"}
        hints = _parse_sidecar_meta(data, "test.jpeg")
        assert hints[0].raw_value == "from_meta"

    def test_meta_is_not_dict_uses_flat(self):
        """If meta key exists but is not a dict, use flat format."""
        data = {"meta": "not a dict", "Model": "flat_model"}
        hints = _parse_sidecar_meta(data, "test.jpeg")
        assert len(hints) == 1
        assert hints[0].raw_value == "flat_model"

    def test_meta_is_none_uses_flat(self):
        """If meta is None, use flat format."""
        data = {"meta": None, "Model": "flat_model"}
        hints = _parse_sidecar_meta(data, "test.jpeg")
        assert len(hints) == 1
        assert hints[0].raw_value == "flat_model"


# =============================================================================
# Enhanced Sidecar: Hash + Weight + LoRA from Prompt
# =============================================================================

class TestEnhancedSidecarParsing:
    """New fields: hash, weight, LoRA tags from prompt."""

    def test_model_hash_extracted(self):
        """Model hash field added to checkpoint hint."""
        data = {"Model": "juggernaut_xl", "Model hash": "d91d35736d"}
        hints = _parse_sidecar_meta(data, "test.jpeg")
        assert hints[0].hash == "d91d35736d"

    def test_resource_hash_extracted(self):
        """Resource hash field added to resource hint."""
        data = {
            "resources": [
                {"name": "some_lora", "type": "lora", "hash": "abcdef1234"},
            ],
        }
        hints = _parse_sidecar_meta(data, "test.jpeg")
        assert len(hints) == 1
        assert hints[0].hash == "abcdef1234"

    def test_resource_weight_extracted(self):
        """Resource weight field added to resource hint."""
        data = {
            "resources": [
                {"name": "some_lora", "type": "lora", "weight": 0.75},
            ],
        }
        hints = _parse_sidecar_meta(data, "test.jpeg")
        assert hints[0].weight == 0.75

    def test_lora_from_prompt_text(self):
        """LoRA tags in prompt field extracted."""
        data = {
            "prompt": "1girl <lora:tifa_lockhart:0.6> <lora:style_enhancer:1.0>",
        }
        hints = _parse_sidecar_meta(data, "test.jpeg")
        loras = [h for h in hints if h.kind == AssetKind.LORA]
        assert len(loras) == 2
        assert loras[0].filename == "tifa_lockhart"
        assert loras[0].weight == 0.6
        assert loras[1].filename == "style_enhancer"
        assert loras[1].weight == 1.0

    def test_lora_dedup_prompt_vs_resources(self):
        """LoRA from resources takes precedence; prompt duplicate skipped."""
        data = {
            "resources": [
                {"name": "tifa_lockhart", "type": "lora", "weight": 0.6, "hash": "abc123"},
            ],
            "prompt": "1girl <lora:tifa_lockhart:0.8>",  # Same LoRA
        }
        hints = _parse_sidecar_meta(data, "test.jpeg")
        loras = [h for h in hints if h.kind == AssetKind.LORA]
        assert len(loras) == 1  # Deduplicated
        assert loras[0].hash == "abc123"  # From resources, not prompt
        assert loras[0].weight == 0.6  # From resources

    def test_lora_dedup_case_insensitive(self):
        """Dedup is case-insensitive for filenames."""
        data = {
            "resources": [
                {"name": "Detail_Tweaker", "type": "lora"},
            ],
            "prompt": "test <lora:detail_tweaker:0.5>",
        }
        hints = _parse_sidecar_meta(data, "test.jpeg")
        loras = [h for h in hints if h.kind == AssetKind.LORA]
        assert len(loras) == 1

    def test_checkpoint_dedup_model_vs_resources(self):
        """Checkpoint from resources[] with same name as Model field is deduped."""
        data = {
            "Model": "illustriousXL_v060",
            "Model hash": "abc123",
            "resources": [
                {"name": "illustriousXL_v060", "type": "model", "hash": "abc123"},
            ],
        }
        hints = _parse_sidecar_meta(data, "test.jpeg")
        ckpts = [h for h in hints if h.kind == AssetKind.CHECKPOINT]
        assert len(ckpts) == 1  # Deduplicated
        assert ckpts[0].hash == "abc123"

    def test_checkpoint_no_dedup_different_names(self):
        """Checkpoint from resources[] with different name is kept."""
        data = {
            "Model": "Juggernaut_XL_Final",
            "resources": [
                {"name": "Juggernaut_XL", "type": "model"},
            ],
        }
        hints = _parse_sidecar_meta(data, "test.jpeg")
        ckpts = [h for h in hints if h.kind == AssetKind.CHECKPOINT]
        assert len(ckpts) == 2  # Different names, both kept

    def test_no_hash_when_missing(self):
        """Hash is None when not in sidecar."""
        data = {"Model": "test_model"}
        hints = _parse_sidecar_meta(data, "test.jpeg")
        assert hints[0].hash is None

    def test_a1111_model_hash_extracted(self):
        """A1111 parameters: Model hash extracted."""
        params = "Model: dreamshaper_8, Model hash: e4b17ce185, Steps: 20"
        hints = _parse_a1111_parameters(params, "test.png")
        assert hints[0].hash == "e4b17ce185"

    def test_a1111_lora_weight_extracted(self):
        """A1111 parameters: LoRA weight extracted."""
        params = "test <lora:my_lora:0.75>\nModel: test"
        hints = _parse_a1111_parameters(params, "test.png")
        loras = [h for h in hints if h.kind == AssetKind.LORA]
        assert len(loras) == 1
        assert loras[0].weight == 0.75


# =============================================================================
# Real Data Integration Tests
# =============================================================================

class TestRealSidecarParsing:
    """Integration tests with real sidecar JSON patterns from production."""

    def test_juggernaut_xl_sidecar(self):
        """Real Juggernaut XL sidecar: Model + resources + hashes."""
        data = {
            "Model": "Juggernaut_X_RunDiffusionPhoto_NSFW_Final",
            "Model hash": "d91d35736d",
            "hashes": {"model": "d91d35736d"},
            "resources": [
                {"hash": "d91d35736d", "name": "Juggernaut_X_RunDiffusionPhoto", "type": "model"}
            ],
            "prompt": "beautiful lady, (freckles), big smile",
            "sampler": "DPM++ 2M",
            "steps": 35,
        }
        hints = _parse_sidecar_meta(data, "10269273.jpeg")
        assert any(h.kind == AssetKind.CHECKPOINT for h in hints)
        ckpts = [h for h in hints if h.kind == AssetKind.CHECKPOINT]
        assert ckpts[0].hash == "d91d35736d"

    def test_lora_pack_with_prompt_tags(self):
        """Real LoRA pack: resources + <lora:name:weight> in prompt."""
        data = {
            "resources": [{"name": "tifa_lockhart", "type": "lora", "weight": 0.6}],
            "prompt": "1girl, long hair <lora:tifa_lockhart_offset:1>",
            "Model hash": "e4b17ce185",
        }
        hints = _parse_sidecar_meta(data, "65658.jpeg")
        lora_hints = [h for h in hints if h.kind == AssetKind.LORA]
        # tifa_lockhart from resources + tifa_lockhart_offset from prompt (different name)
        assert len(lora_hints) == 2

    def test_embedding_pack_no_model(self):
        """Real embedding pack: no Model field, only Model hash."""
        data = {
            "seed": 1834928170,
            "Model hash": "d289dfa4ed",
            "sampler": "DPM++ 2M Karras",
        }
        hints = _parse_sidecar_meta(data, "45380.jpeg")
        # No Model field → no checkpoint hint
        assert len(hints) == 0

    def test_video_sidecar_prompt_only(self):
        """Real video sidecar: only prompt, no model data."""
        data = {"prompt": "Close-up video of person walking"}
        hints = _parse_sidecar_meta(data, "117604134.mp4")
        assert len(hints) == 0  # No LoRA tags, no model

    def test_full_civitai_sidecar_all_fields(self):
        """Comprehensive sidecar with all field types."""
        data = {
            "Model": "illustriousXL_v060",
            "Model hash": "abc123def",
            "resources": [
                {"name": "illustriousXL_v060", "type": "model", "hash": "abc123def"},
                {"name": "detail_tweaker_xl", "type": "lora", "weight": 0.5, "hash": "fed321cba"},
                {"name": "kl-f8-anime2", "type": "vae"},
            ],
            "prompt": "1girl, masterpiece <lora:style_boost:0.3>",
            "negativePrompt": "bad quality",
            "sampler": "Euler a",
            "steps": 25,
            "cfgScale": 7,
            "seed": 42,
        }
        hints = _parse_sidecar_meta(data, "001.jpeg")
        # Model + 2 non-dup resources (LoRA + VAE) + 1 LoRA from prompt = 4
        # (resources[type=model] deduped against Model field)
        assert len(hints) == 4
        assert any(h.kind == AssetKind.VAE for h in hints)
        prompt_loras = [h for h in hints if h.raw_value == "style_boost"]
        assert len(prompt_loras) == 1
        assert prompt_loras[0].weight == 0.3


# =============================================================================
# Original Tests (preserved, adapted for new API)
# =============================================================================

class TestParseSidecarMeta:
    def test_extracts_model_name(self):
        data = {"meta": {"Model": "illustriousXL_v060"}}
        hints = _parse_sidecar_meta(data, "001.png")
        assert len(hints) == 1
        assert hints[0].filename == "illustriousXL_v060"
        assert hints[0].kind == AssetKind.CHECKPOINT
        assert hints[0].source_type == "api_meta"
        assert hints[0].source_image == "001.png"

    def test_extracts_model_name_alt_key(self):
        data = {"meta": {"model_name": "dreamshaper_8"}}
        hints = _parse_sidecar_meta(data, "002.png")
        assert len(hints) == 1
        assert hints[0].filename == "dreamshaper_8"

    def test_extracts_resources(self):
        data = {
            "meta": {
                "Model": "illustriousXL_v060",
                "resources": [
                    {"name": "detail_tweaker_xl", "type": "lora", "weight": 0.5},
                    {"name": "kl-f8-anime2", "type": "vae"},
                ],
            },
        }
        hints = _parse_sidecar_meta(data, "001.png")
        assert len(hints) == 3  # Model + 2 resources
        lora = [h for h in hints if h.kind == AssetKind.LORA]
        assert len(lora) == 1
        assert lora[0].filename == "detail_tweaker_xl"
        vae = [h for h in hints if h.kind == AssetKind.VAE]
        assert len(vae) == 1

    def test_empty_meta(self):
        assert _parse_sidecar_meta({}, "001.png") == []
        assert _parse_sidecar_meta({"meta": {}}, "001.png") == []

    def test_missing_resource_name_skipped(self):
        data = {"meta": {"resources": [{"type": "lora"}]}}
        hints = _parse_sidecar_meta(data, "001.png")
        assert hints == []

    def test_resource_unknown_type(self):
        data = {"meta": {"resources": [{"name": "something", "type": "unknown_type"}]}}
        hints = _parse_sidecar_meta(data, "001.png")
        assert len(hints) == 1
        assert hints[0].kind is None  # Unknown type

    def test_groups_by_provenance_per_image(self):
        """All hints from same sidecar share source_image."""
        data = {
            "meta": {
                "Model": "model_a",
                "resources": [{"name": "lora_b", "type": "lora"}],
            },
        }
        hints = _parse_sidecar_meta(data, "preview_003.png")
        assert all(h.source_image == "preview_003.png" for h in hints)


class TestParseA1111Parameters:
    def test_model_reference(self):
        params = "beautiful girl, 1girl\nNegative prompt: bad\nSteps: 20, Sampler: Euler, Model: dreamshaper_8, Seed: 12345"
        hints = _parse_a1111_parameters(params, "001.png")
        models = [h for h in hints if h.kind == AssetKind.CHECKPOINT]
        assert len(models) == 1
        assert models[0].filename == "dreamshaper_8"
        assert models[0].source_type == "png_embedded"

    def test_lora_references(self):
        params = "a girl <lora:detail_tweaker:0.5> <lora:add_more_details:0.3>\nModel: sd_xl"
        hints = _parse_a1111_parameters(params, "001.png")
        loras = [h for h in hints if h.kind == AssetKind.LORA]
        assert len(loras) == 2
        assert loras[0].filename == "detail_tweaker"
        assert loras[1].filename == "add_more_details"

    def test_no_model_reference(self):
        params = "a beautiful landscape\nSteps: 20"
        hints = _parse_a1111_parameters(params, "001.png")
        assert hints == []


# =============================================================================
# ComfyUI Node Registry Tests
# =============================================================================

class TestComfyUINodeRegistry:
    def test_registry_has_standard_nodes(self):
        """All standard nodes are in the registry."""
        assert "CheckpointLoaderSimple" in COMFYUI_NODE_REGISTRY
        assert "LoraLoader" in COMFYUI_NODE_REGISTRY
        assert "VAELoader" in COMFYUI_NODE_REGISTRY

    def test_registry_has_new_nodes(self):
        """New node types added by the redesign."""
        assert "DualCLIPLoader" in COMFYUI_NODE_REGISTRY
        assert "IPAdapterModelLoader" in COMFYUI_NODE_REGISTRY
        assert "UNETLoader" in COMFYUI_NODE_REGISTRY
        assert "DiffControlNetLoader" in COMFYUI_NODE_REGISTRY

    def test_checkpoint_loader(self):
        workflow = json.dumps({
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "illustriousXL_v060.safetensors"},
            },
        })
        hints = _parse_comfyui_workflow(workflow, "001.png")
        assert len(hints) == 1
        assert hints[0].filename == "illustriousXL_v060.safetensors"
        assert hints[0].kind == AssetKind.CHECKPOINT
        assert hints[0].source_type == "png_embedded"

    def test_lora_loader(self):
        workflow = json.dumps({
            "2": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "detail_tweaker_xl.safetensors", "strength_model": 0.5},
            },
        })
        hints = _parse_comfyui_workflow(workflow, "001.png")
        assert len(hints) == 1
        assert hints[0].kind == AssetKind.LORA

    def test_vae_loader(self):
        workflow = json.dumps({
            "3": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "kl-f8-anime2.safetensors"},
            },
        })
        hints = _parse_comfyui_workflow(workflow, "001.png")
        assert len(hints) == 1
        assert hints[0].kind == AssetKind.VAE

    def test_dual_clip_loader_multi_model(self):
        """DualCLIPLoader extracts two model references."""
        workflow = json.dumps({"1": {
            "class_type": "DualCLIPLoader",
            "inputs": {"clip_name1": "clip_l.safetensors", "clip_name2": "clip_g.safetensors"},
        }})
        hints = _parse_comfyui_workflow(workflow, "test.png")
        assert len(hints) == 2
        assert all(h.kind == AssetKind.EMBEDDING for h in hints)
        filenames = {h.filename for h in hints}
        assert "clip_l.safetensors" in filenames
        assert "clip_g.safetensors" in filenames

    def test_ipadapter_loader(self):
        """IPAdapterModelLoader extracted as LoRA."""
        workflow = json.dumps({"1": {
            "class_type": "IPAdapterModelLoader",
            "inputs": {"ipadapter_file": "ip-adapter_sd15.bin"},
        }})
        hints = _parse_comfyui_workflow(workflow, "test.png")
        assert len(hints) == 1
        assert hints[0].kind == AssetKind.LORA
        assert hints[0].filename == "ip-adapter_sd15.bin"

    def test_unet_loader(self):
        """UNETLoader extracted as checkpoint."""
        workflow = json.dumps({"1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "flux_dev.safetensors"},
        }})
        hints = _parse_comfyui_workflow(workflow, "test.png")
        assert len(hints) == 1
        assert hints[0].kind == AssetKind.CHECKPOINT

    def test_controlnet_diff_loader(self):
        """DiffControlNetLoader uses 'model' key."""
        workflow = json.dumps({"1": {
            "class_type": "DiffControlNetLoader",
            "inputs": {"model": "control_v11p_sd15_canny.pth"},
        }})
        hints = _parse_comfyui_workflow(workflow, "test.png")
        assert len(hints) == 1
        assert hints[0].kind == AssetKind.CONTROLNET

    def test_unknown_node_ignored(self):
        """Custom nodes not in registry are silently skipped."""
        workflow = json.dumps({
            "1": {
                "class_type": "MyCustomNode",
                "inputs": {"model": "custom.safetensors"},
            },
        })
        hints = _parse_comfyui_workflow(workflow, "test.png")
        assert hints == []

    def test_complex_workflow_multiple_nodes(self):
        """Full workflow with checkpoint + 2 LoRAs + VAE + ControlNet."""
        workflow = json.dumps({
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd15.safetensors"}},
            "2": {"class_type": "LoraLoader", "inputs": {"lora_name": "lora1.safetensors"}},
            "3": {"class_type": "LoRALoader", "inputs": {"lora_name": "lora2.safetensors"}},
            "4": {"class_type": "VAELoader", "inputs": {"vae_name": "vae.safetensors"}},
            "5": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": "canny.safetensors"}},
            "6": {"class_type": "KSampler", "inputs": {"seed": 42}},  # Not a model loader
        })
        hints = _parse_comfyui_workflow(workflow, "test.png")
        assert len(hints) == 5
        kinds = [h.kind for h in hints]
        assert kinds.count(AssetKind.CHECKPOINT) == 1
        assert kinds.count(AssetKind.LORA) == 2
        assert kinds.count(AssetKind.VAE) == 1
        assert kinds.count(AssetKind.CONTROLNET) == 1

    def test_multiple_nodes(self):
        workflow = json.dumps({
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "2": {
                "class_type": "LoraLoader",
                "inputs": {"lora_name": "lora.safetensors"},
            },
            "3": {
                "class_type": "KSampler",  # Not a model loader
                "inputs": {"seed": 42},
            },
        })
        hints = _parse_comfyui_workflow(workflow, "001.png")
        assert len(hints) == 2

    def test_path_prefix_stripped(self):
        workflow = json.dumps({
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "checkpoints/illustriousXL_v060.safetensors"},
            },
        })
        hints = _parse_comfyui_workflow(workflow, "001.png")
        assert hints[0].filename == "illustriousXL_v060.safetensors"

    def test_invalid_json(self):
        hints = _parse_comfyui_workflow("not json", "001.png")
        assert hints == []

    def test_non_dict_workflow(self):
        hints = _parse_comfyui_workflow(json.dumps([1, 2, 3]), "001.png")
        assert hints == []


# =============================================================================
# extract_preview_hints (integration with file system)
# =============================================================================

class TestExtractPreviewHints:
    def test_reads_sidecar_json(self, tmp_path):
        sidecar = {
            "meta": {"Model": "test_model", "resources": []},
        }
        (tmp_path / "001.png.json").write_text(json.dumps(sidecar))

        hints = extract_preview_hints(tmp_path, ["001.png"])
        assert len(hints) == 1
        assert hints[0].filename == "test_model"

    def test_reads_flat_sidecar_json(self, tmp_path):
        """BUG 7: Flat format sidecar read from disk."""
        sidecar = {"Model": "juggernaut_xl", "resources": []}
        (tmp_path / "001.jpeg.json").write_text(json.dumps(sidecar))

        hints = extract_preview_hints(tmp_path, ["001.jpeg"])
        assert len(hints) == 1
        assert hints[0].filename == "juggernaut_xl"

    def test_no_sidecar_returns_empty(self, tmp_path):
        hints = extract_preview_hints(tmp_path, ["001.png"])
        assert hints == []

    def test_invalid_sidecar_json(self, tmp_path):
        (tmp_path / "001.png.json").write_text("not json")
        hints = extract_preview_hints(tmp_path, ["001.png"])
        assert hints == []

    def test_marks_unresolvable_for_private_models(self):
        """PreviewModelHint defaults to resolvable=True; caller marks unresolvable."""
        data = {"meta": {"Model": "my_custom_merge_v3"}}
        hints = _parse_sidecar_meta(data, "001.png")
        assert hints[0].resolvable is True


# =============================================================================
# Generation Params Extraction
# =============================================================================

class TestExtractGenerationParams:
    def test_extracts_params_from_sidecar(self, tmp_path):
        sidecar = {
            "sampler": "DPM++ 2M",
            "steps": 35,
            "cfgScale": 7,
            "seed": 42,
            "prompt": "beautiful lady",
        }
        (tmp_path / "001.jpeg.json").write_text(json.dumps(sidecar))
        params = _extract_generation_params(tmp_path, "001.jpeg")
        assert params is not None
        assert params["sampler"] == "DPM++ 2M"
        assert params["steps"] == 35
        assert params["seed"] == 42

    def test_extracts_from_wrapped_meta(self, tmp_path):
        sidecar = {"meta": {"sampler": "Euler", "steps": 20}}
        (tmp_path / "001.png.json").write_text(json.dumps(sidecar))
        params = _extract_generation_params(tmp_path, "001.png")
        assert params is not None
        assert params["sampler"] == "Euler"

    def test_no_sidecar_returns_none(self, tmp_path):
        params = _extract_generation_params(tmp_path, "nonexistent.jpeg")
        assert params is None

    def test_empty_sidecar_returns_none(self, tmp_path):
        (tmp_path / "001.jpeg.json").write_text(json.dumps({"unrelated_key": 123}))
        params = _extract_generation_params(tmp_path, "001.jpeg")
        assert params is None


# =============================================================================
# analyze_pack_previews
# =============================================================================

class TestAnalyzePackPreviews:
    def _make_preview(self, filename, media_type="image", width=512, height=768, nsfw=False, url=None):
        """Create a mock preview object."""
        p = MagicMock()
        p.filename = filename
        p.media_type = media_type
        p.width = width
        p.height = height
        p.nsfw = nsfw
        p.url = url
        p.thumbnail_url = None
        return p

    def test_basic_analysis(self, tmp_path):
        sidecar = {"Model": "test_model", "sampler": "Euler", "steps": 20}
        (tmp_path / "001.jpeg.json").write_text(json.dumps(sidecar))

        previews = [self._make_preview("001.jpeg")]
        results = analyze_pack_previews(tmp_path, previews)

        assert len(results) == 1
        assert results[0].filename == "001.jpeg"
        assert len(results[0].hints) == 1
        assert results[0].generation_params is not None
        assert results[0].generation_params["sampler"] == "Euler"

    def test_multiple_previews(self, tmp_path):
        sidecar1 = {"Model": "model_a"}
        sidecar2 = {"Model": "model_b"}
        (tmp_path / "001.jpeg.json").write_text(json.dumps(sidecar1))
        (tmp_path / "002.jpeg.json").write_text(json.dumps(sidecar2))

        previews = [
            self._make_preview("001.jpeg"),
            self._make_preview("002.jpeg"),
        ]
        results = analyze_pack_previews(tmp_path, previews)
        assert len(results) == 2
        assert results[0].hints[0].raw_value == "model_a"
        assert results[1].hints[0].raw_value == "model_b"

    def test_preview_without_sidecar(self, tmp_path):
        previews = [self._make_preview("001.jpeg")]
        results = analyze_pack_previews(tmp_path, previews)
        assert len(results) == 1
        assert results[0].hints == []
        assert results[0].generation_params is None

    def test_preserves_preview_metadata(self, tmp_path):
        previews = [self._make_preview(
            "001.jpeg", media_type="video", width=1920, height=1080, nsfw=True, url="https://example.com/001.mp4"
        )]
        results = analyze_pack_previews(tmp_path, previews)
        assert results[0].media_type == "video"
        assert results[0].width == 1920
        assert results[0].height == 1080
        assert results[0].nsfw is True
        assert results[0].url == "https://example.com/001.mp4"

    def test_skips_previews_without_filename(self, tmp_path):
        preview = MagicMock()
        preview.filename = None
        results = analyze_pack_previews(tmp_path, [preview])
        assert results == []


class TestFilterHintsByKind:
    def test_filters_by_kind(self):
        from src.store.resolve_models import PreviewModelHint

        hints = [
            PreviewModelHint(filename="ckpt.safetensors", kind=AssetKind.CHECKPOINT,
                             source_image="001.png", source_type="api_meta", raw_value="ckpt"),
            PreviewModelHint(filename="lora.safetensors", kind=AssetKind.LORA,
                             source_image="001.png", source_type="api_meta", raw_value="lora"),
            PreviewModelHint(filename="unknown.safetensors", kind=None,
                             source_image="001.png", source_type="api_meta", raw_value="unknown"),
        ]
        checkpoint_hints = filter_hints_by_kind(hints, AssetKind.CHECKPOINT)
        assert len(checkpoint_hints) == 2  # CHECKPOINT + None (unknown)
        lora_hints = filter_hints_by_kind(hints, AssetKind.LORA)
        assert len(lora_hints) == 2  # LORA + None (unknown)
