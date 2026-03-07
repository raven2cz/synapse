"""
Tests for preview_meta_extractor.py — sidecar JSON + PNG tEXt parsing.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.store.models import AssetKind
from src.utils.preview_meta_extractor import (
    extract_preview_hints,
    filter_hints_by_kind,
    _normalize_filename,
    _parse_a1111_parameters,
    _parse_comfyui_workflow,
    _parse_sidecar_meta,
)


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


class TestParseComfyUIWorkflow:
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


class TestExtractPreviewHints:
    def test_reads_sidecar_json(self, tmp_path):
        sidecar = {
            "meta": {"Model": "test_model", "resources": []},
        }
        (tmp_path / "001.png.json").write_text(json.dumps(sidecar))

        hints = extract_preview_hints(tmp_path, ["001.png"])
        assert len(hints) == 1
        assert hints[0].filename == "test_model"

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
        # By default resolvable=True — the resolve service marks unresolvable later
        assert hints[0].resolvable is True


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
