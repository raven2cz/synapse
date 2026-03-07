"""
Preview metadata extractor — sidecar JSON reader + PNG tEXt parser.

Extracts model hints from preview images for dependency resolution.
Based on PLAN-Resolve-Model.md v0.7.1 sections 2e, Phase 0 item 8.

Sources:
- Civitai API sidecar .json: meta.Model, meta.resources[]
- PNG tEXt chunks: A1111 parameters, ComfyUI workflow JSON
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.store.models import AssetKind
from src.store.resolve_models import PreviewModelHint

logger = logging.getLogger(__name__)

# ComfyUI node types → AssetKind mapping
COMFYUI_NODE_KIND: Dict[str, AssetKind] = {
    "CheckpointLoaderSimple": AssetKind.CHECKPOINT,
    "CheckpointLoader": AssetKind.CHECKPOINT,
    "LoraLoader": AssetKind.LORA,
    "LoRALoader": AssetKind.LORA,
    "LoraLoaderModelOnly": AssetKind.LORA,
    "VAELoader": AssetKind.VAE,
    "ControlNetLoader": AssetKind.CONTROLNET,
    "UpscaleModelLoader": AssetKind.UPSCALER,
}

# Civitai resource type → AssetKind
RESOURCE_TYPE_KIND: Dict[str, AssetKind] = {
    "model": AssetKind.CHECKPOINT,
    "checkpoint": AssetKind.CHECKPOINT,
    "lora": AssetKind.LORA,
    "vae": AssetKind.VAE,
    "controlnet": AssetKind.CONTROLNET,
    "embedding": AssetKind.EMBEDDING,
    "textualinversion": AssetKind.EMBEDDING,
    "upscaler": AssetKind.UPSCALER,
}


def extract_preview_hints(
    pack_path: Path,
    preview_filenames: List[str],
) -> List[PreviewModelHint]:
    """Extract model hints from preview images.

    Reads sidecar .json files and (if available) PNG tEXt metadata.

    Args:
        pack_path: Path to the pack directory.
        preview_filenames: List of preview image filenames (e.g., ["001.png"]).

    Returns:
        List of PreviewModelHint with provenance tags.
    """
    hints: List[PreviewModelHint] = []

    for filename in preview_filenames:
        # Source 1: Sidecar JSON (Civitai API meta)
        sidecar_hints = _extract_from_sidecar(pack_path, filename)
        hints.extend(sidecar_hints)

        # Source 2: PNG tEXt chunks (if .png file exists)
        if filename.lower().endswith(".png"):
            png_hints = _extract_from_png(pack_path, filename)
            hints.extend(png_hints)

    return hints


def _extract_from_sidecar(
    pack_path: Path,
    image_filename: str,
) -> List[PreviewModelHint]:
    """Extract hints from Civitai API sidecar JSON.

    Sidecar files are stored as <image_filename>.json (e.g., 001.png.json).
    """
    sidecar_path = pack_path / f"{image_filename}.json"
    if not sidecar_path.exists():
        return []

    try:
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read sidecar %s: %s", sidecar_path, e)
        return []

    return _parse_sidecar_meta(data, image_filename)


def _parse_sidecar_meta(
    data: Dict[str, Any],
    source_image: str,
) -> List[PreviewModelHint]:
    """Parse Civitai API meta from sidecar JSON."""
    hints: List[PreviewModelHint] = []
    meta = data.get("meta") or {}

    # meta.Model or meta.model_name → checkpoint hint
    model_name = meta.get("Model") or meta.get("model_name")
    if model_name and isinstance(model_name, str):
        hints.append(PreviewModelHint(
            filename=_normalize_filename(model_name),
            kind=AssetKind.CHECKPOINT,
            source_image=source_image,
            source_type="api_meta",
            raw_value=model_name,
        ))

    # meta.resources[] → additional model hints
    resources = meta.get("resources")
    if isinstance(resources, list):
        for res in resources:
            if not isinstance(res, dict):
                continue
            hint = _parse_resource(res, source_image)
            if hint:
                hints.append(hint)

    return hints


def _parse_resource(
    resource: Dict[str, Any],
    source_image: str,
) -> Optional[PreviewModelHint]:
    """Parse a single resource entry from meta.resources[]."""
    name = resource.get("name")
    if not name or not isinstance(name, str):
        return None

    res_type = (resource.get("type") or "").lower()
    kind = RESOURCE_TYPE_KIND.get(res_type)

    return PreviewModelHint(
        filename=_normalize_filename(name),
        kind=kind,
        source_image=source_image,
        source_type="api_meta",
        raw_value=name,
    )


def _extract_from_png(
    pack_path: Path,
    image_filename: str,
) -> List[PreviewModelHint]:
    """Extract hints from PNG tEXt chunks (A1111/ComfyUI metadata)."""
    png_path = pack_path / image_filename
    if not png_path.exists():
        return []

    try:
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo
    except ImportError:
        logger.debug("PIL not available, skipping PNG metadata extraction")
        return []

    try:
        with Image.open(png_path) as img:
            text_data = getattr(img, "text", {}) or {}
    except Exception as e:
        logger.warning("Failed to read PNG metadata from %s: %s", png_path, e)
        return []

    hints: List[PreviewModelHint] = []

    # A1111: tEXt[parameters] → "Model: dreamshaper_8, ..."
    parameters = text_data.get("parameters", "")
    if parameters:
        a1111_hints = _parse_a1111_parameters(parameters, image_filename)
        hints.extend(a1111_hints)

    # ComfyUI: tEXt[prompt] → JSON workflow
    prompt = text_data.get("prompt", "")
    if prompt:
        comfy_hints = _parse_comfyui_workflow(prompt, image_filename)
        hints.extend(comfy_hints)

    return hints


def _parse_a1111_parameters(
    parameters: str,
    source_image: str,
) -> List[PreviewModelHint]:
    """Parse A1111 parameters string for model references."""
    hints: List[PreviewModelHint] = []

    # "Model: dreamshaper_8" or "Model: illustriousXL_v060"
    model_match = re.search(r"Model:\s*([^\s,]+)", parameters)
    if model_match:
        model_name = model_match.group(1)
        hints.append(PreviewModelHint(
            filename=_normalize_filename(model_name),
            kind=AssetKind.CHECKPOINT,
            source_image=source_image,
            source_type="png_embedded",
            raw_value=model_name,
        ))

    # LoRA references: "<lora:name:weight>"
    lora_matches = re.findall(r"<lora:([^:>]+):[^>]+>", parameters)
    for lora_name in lora_matches:
        hints.append(PreviewModelHint(
            filename=_normalize_filename(lora_name),
            kind=AssetKind.LORA,
            source_image=source_image,
            source_type="png_embedded",
            raw_value=lora_name,
        ))

    return hints


def _parse_comfyui_workflow(
    prompt_json: str,
    source_image: str,
) -> List[PreviewModelHint]:
    """Parse ComfyUI workflow JSON for model references."""
    try:
        workflow = json.loads(prompt_json)
    except json.JSONDecodeError:
        return []

    if not isinstance(workflow, dict):
        return []

    hints: List[PreviewModelHint] = []

    for _node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue

        class_type = node.get("class_type", "")
        kind = COMFYUI_NODE_KIND.get(class_type)
        if kind is None:
            continue

        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue

        # CheckpointLoaderSimple → ckpt_name
        # LoraLoader → lora_name
        # VAELoader → vae_name
        # ControlNetLoader → control_net_name
        # UpscaleModelLoader → model_name
        name_keys = ["ckpt_name", "lora_name", "vae_name",
                      "control_net_name", "model_name"]

        for key in name_keys:
            value = inputs.get(key)
            if value and isinstance(value, str):
                hints.append(PreviewModelHint(
                    filename=_normalize_filename(value),
                    kind=kind,
                    source_image=source_image,
                    source_type="png_embedded",
                    raw_value=value,
                ))
                break  # One name per node

    return hints


def _normalize_filename(name: str) -> str:
    """Normalize a model name to a filename-like form.

    Strips path prefixes and ensures .safetensors extension if none present.
    """
    # Strip path prefixes (ComfyUI often stores "checkpoints/model.safetensors")
    name = name.replace("\\", "/")
    if "/" in name:
        name = name.rsplit("/", 1)[-1]

    return name


def filter_hints_by_kind(
    hints: List[PreviewModelHint],
    kind: AssetKind,
) -> List[PreviewModelHint]:
    """Filter hints to only those matching the target AssetKind.

    Hints with kind=None are included (unknown kind, could match anything).
    """
    return [h for h in hints if h.kind is None or h.kind == kind]
