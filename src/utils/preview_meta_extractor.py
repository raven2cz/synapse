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
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.store.models import AssetKind
from src.store.resolve_models import PreviewAnalysisResult, PreviewModelHint

logger = logging.getLogger(__name__)


# =============================================================================
# ComfyUI Node Registry
# =============================================================================

@dataclass
class ComfyUINodeDef:
    """Definition of a ComfyUI node type for model extraction."""
    kind: AssetKind
    input_keys: List[str] = field(default_factory=list)


COMFYUI_NODE_REGISTRY: Dict[str, ComfyUINodeDef] = {
    # Checkpoints
    "CheckpointLoaderSimple": ComfyUINodeDef(AssetKind.CHECKPOINT, ["ckpt_name"]),
    "CheckpointLoader": ComfyUINodeDef(AssetKind.CHECKPOINT, ["ckpt_name"]),
    "UNETLoader": ComfyUINodeDef(AssetKind.CHECKPOINT, ["unet_name"]),

    # LoRA
    "LoraLoader": ComfyUINodeDef(AssetKind.LORA, ["lora_name"]),
    "LoRALoader": ComfyUINodeDef(AssetKind.LORA, ["lora_name"]),
    "LoraLoaderModelOnly": ComfyUINodeDef(AssetKind.LORA, ["lora_name"]),

    # VAE
    "VAELoader": ComfyUINodeDef(AssetKind.VAE, ["vae_name"]),

    # ControlNet
    "ControlNetLoader": ComfyUINodeDef(AssetKind.CONTROLNET, ["control_net_name"]),
    "DiffControlNetLoader": ComfyUINodeDef(AssetKind.CONTROLNET, ["model"]),

    # CLIP
    "CLIPLoader": ComfyUINodeDef(AssetKind.EMBEDDING, ["clip_name"]),
    "DualCLIPLoader": ComfyUINodeDef(AssetKind.EMBEDDING, ["clip_name1", "clip_name2"]),
    "CLIPVisionLoader": ComfyUINodeDef(AssetKind.EMBEDDING, ["clip_name"]),

    # Upscaler
    "UpscaleModelLoader": ComfyUINodeDef(AssetKind.UPSCALER, ["model_name"]),
    "ImageUpscaleWithModel": ComfyUINodeDef(AssetKind.UPSCALER, ["model_name"]),

    # IPAdapter / Style
    "IPAdapterModelLoader": ComfyUINodeDef(AssetKind.LORA, ["ipadapter_file"]),
    "StyleModelLoader": ComfyUINodeDef(AssetKind.LORA, ["style_model_name"]),

    # AnimateDiff
    "ADE_AnimateDiffLoaderWithContext": ComfyUINodeDef(AssetKind.CHECKPOINT, ["model_name"]),

    # HighRes-Fix Script (has control_net_name + pixel_upscaler)
    "HighRes-Fix Script": ComfyUINodeDef(AssetKind.CONTROLNET, ["control_net_name"]),
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

# Generation param keys to extract from sidecar meta
_GEN_PARAM_KEYS = frozenset({
    "prompt", "negativePrompt", "sampler", "steps", "cfgScale",
    "seed", "Size", "Model hash", "Clip skip", "Denoising strength",
})


def extract_preview_hints(
    previews_path: Path,
    preview_filenames: List[str],
) -> List[PreviewModelHint]:
    """Extract model hints from preview images.

    Reads sidecar .json files and (if available) PNG tEXt metadata.

    Args:
        previews_path: Path to the previews directory (resources/previews/).
        preview_filenames: List of preview image filenames (e.g., ["001.png"]).

    Returns:
        List of PreviewModelHint with provenance tags.
    """
    hints: List[PreviewModelHint] = []

    for filename in preview_filenames:
        # Source 1: Sidecar JSON (Civitai API meta)
        sidecar_hints = _extract_from_sidecar(previews_path, filename)
        hints.extend(sidecar_hints)

        # Source 2: PNG tEXt chunks (check magic bytes, not extension —
        # Civitai often serves PNG files with .jpeg extension)
        png_hints = _extract_from_png(previews_path, filename)
        hints.extend(png_hints)

    return hints


def analyze_pack_previews(
    previews_path: Path,
    previews: List[Any],
) -> List[PreviewAnalysisResult]:
    """Full analysis: extract hints + generation params for each preview.

    Args:
        previews_path: Path to previews directory.
        previews: Pack.previews list (PreviewInfo objects).

    Returns:
        List of PreviewAnalysisResult with hints and generation params.
    """
    results: List[PreviewAnalysisResult] = []

    for preview in previews:
        filename = getattr(preview, "filename", None)
        if not filename:
            continue

        # Read sidecar once, extract both hints and gen params
        sidecar_data = _read_sidecar(previews_path, filename)
        hints: List[PreviewModelHint] = []
        gen_params: Optional[Dict[str, Any]] = None

        if sidecar_data is not None:
            hints.extend(_parse_sidecar_meta(sidecar_data, filename))
            gen_params = _extract_generation_params_from_data(sidecar_data)

        # PNG tEXt (check magic bytes, not extension)
        hints.extend(_extract_from_png(previews_path, filename))

        results.append(PreviewAnalysisResult(
            filename=filename,
            url=getattr(preview, "url", None),
            thumbnail_url=getattr(preview, "thumbnail_url", None),
            media_type=getattr(preview, "media_type", "image"),
            width=getattr(preview, "width", None),
            height=getattr(preview, "height", None),
            nsfw=getattr(preview, "nsfw", False),
            hints=hints,
            generation_params=gen_params,
        ))

    return results


def _sanitize_filename(filename: str) -> Optional[str]:
    """Validate and sanitize a preview filename to prevent path traversal.

    Returns None if the filename is unsafe (contains path separators or ..).
    """
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return None
    return filename


def _read_sidecar(
    previews_path: Path,
    image_filename: str,
) -> Optional[Dict[str, Any]]:
    """Read and parse a sidecar JSON file. Returns None if missing or invalid."""
    safe_name = _sanitize_filename(image_filename)
    if safe_name is None:
        logger.warning("Unsafe filename rejected: %s", image_filename)
        return None
    sidecar_path = previews_path / f"{safe_name}.json"
    if not sidecar_path.exists():
        return None

    try:
        return json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read sidecar %s: %s", sidecar_path, e)
        return None


def _extract_generation_params(
    previews_path: Path,
    image_filename: str,
) -> Optional[Dict[str, Any]]:
    """Extract raw generation parameters from sidecar JSON."""
    data = _read_sidecar(previews_path, image_filename)
    if data is None:
        return None
    return _extract_generation_params_from_data(data)


def _extract_generation_params_from_data(
    data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Extract generation parameters from already-parsed sidecar data."""
    # Support both formats: {"meta": {...}} wrapper and flat {...}
    meta = data.get("meta")
    if not isinstance(meta, dict):
        meta = data

    params: Dict[str, Any] = {}
    for key in _GEN_PARAM_KEYS:
        if key in meta:
            params[key] = meta[key]

    # Also collect these common variants
    if "cfg_scale" in meta:
        params["cfgScale"] = meta["cfg_scale"]
    if "negative_prompt" in meta:
        params["negativePrompt"] = meta["negative_prompt"]

    return params if params else None


def _extract_from_sidecar(
    previews_path: Path,
    image_filename: str,
) -> List[PreviewModelHint]:
    """Extract hints from Civitai API sidecar JSON.

    Sidecar files are stored as <image_filename>.json (e.g., 001.png.json).
    """
    data = _read_sidecar(previews_path, image_filename)
    if data is None:
        return []
    return _parse_sidecar_meta(data, image_filename)


def _parse_sidecar_meta(
    data: Dict[str, Any],
    source_image: str,
) -> List[PreviewModelHint]:
    """Parse Civitai API meta from sidecar JSON.

    Supports both formats:
    - Wrapped: {"meta": {"Model": "...", "resources": [...]}}
    - Flat: {"Model": "...", "resources": [...]} (real Civitai sidecars)
    """
    hints: List[PreviewModelHint] = []

    # BUG 7 fix: Support both wrapped and flat sidecar formats
    meta = data.get("meta")
    if not isinstance(meta, dict):
        meta = data  # Flat format (real Civitai sidecars)

    # Extract short hash for checkpoint hints
    model_hash = meta.get("Model hash")
    if isinstance(model_hash, str):
        model_hash = model_hash.strip()
    else:
        model_hash = None

    # meta.Model or meta.model_name → checkpoint hint
    model_name = meta.get("Model") or meta.get("model_name")
    model_name_normalized: Optional[str] = None
    if model_name and isinstance(model_name, str):
        model_name_normalized = _normalize_filename(model_name).lower()
        hints.append(PreviewModelHint(
            filename=_normalize_filename(model_name),
            kind=AssetKind.CHECKPOINT,
            source_image=source_image,
            source_type="api_meta",
            raw_value=model_name,
            hash=model_hash,
        ))

    # meta.resources[] → additional model hints (dedup against Model field)
    resources = meta.get("resources")
    seen_resource_names: set[str] = set()
    if isinstance(resources, list):
        for res in resources:
            if not isinstance(res, dict):
                continue
            hint = _parse_resource(res, source_image)
            if hint:
                # Skip if this resource duplicates the Model field checkpoint
                if (model_name_normalized
                        and hint.kind == AssetKind.CHECKPOINT
                        and hint.filename.lower() == model_name_normalized):
                    continue
                seen_resource_names.add(hint.filename.lower())
                hints.append(hint)

    # Extract LoRA tags from prompt text (dedup against resources)
    prompt_text = meta.get("prompt")
    if isinstance(prompt_text, str):
        lora_matches = re.findall(r"<lora:([^:>]+):([^>]+)>", prompt_text)
        for lora_name, weight_str in lora_matches:
            normalized = _normalize_filename(lora_name)
            if normalized.lower() in seen_resource_names:
                continue  # Already found in resources[]
            weight = _parse_float(weight_str)
            hints.append(PreviewModelHint(
                filename=normalized,
                kind=AssetKind.LORA,
                source_image=source_image,
                source_type="api_meta",
                raw_value=lora_name,
                weight=weight,
            ))

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

    # Extract hash and weight from resource
    res_hash = resource.get("hash")
    if not isinstance(res_hash, str):
        res_hash = None
    weight = resource.get("weight")
    if not isinstance(weight, (int, float)):
        weight = None
    else:
        weight = float(weight)

    return PreviewModelHint(
        filename=_normalize_filename(name),
        kind=kind,
        source_image=source_image,
        source_type="api_meta",
        raw_value=name,
        hash=res_hash,
        weight=weight,
    )


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _read_png_text_chunks(file_path: Path) -> Dict[str, str]:
    """Read tEXt chunks from a PNG file. Returns empty dict if not PNG.

    Checks magic bytes — works regardless of file extension.
    Civitai often serves PNG files with .jpeg extension.
    """
    try:
        with open(file_path, "rb") as f:
            sig = f.read(8)
            if sig != _PNG_SIGNATURE:
                return {}

            chunks: Dict[str, str] = {}
            while True:
                header = f.read(8)
                if len(header) < 8:
                    break
                length = struct.unpack(">I", header[:4])[0]
                chunk_type = header[4:8]

                # Only read tEXt chunks, skip everything else efficiently
                if chunk_type == b"tEXt":
                    chunk_data = f.read(length)
                    f.read(4)  # CRC
                    null_pos = chunk_data.find(b"\x00")
                    if null_pos != -1:
                        key = chunk_data[:null_pos].decode("latin-1")
                        value = chunk_data[null_pos + 1 :].decode("utf-8", errors="replace")
                        chunks[key] = value
                elif chunk_type == b"IEND":
                    break
                else:
                    # Skip chunk data + CRC without reading into memory
                    f.seek(length + 4, 1)

            return chunks
    except OSError as e:
        logger.warning("Failed to read PNG chunks from %s: %s", file_path, e)
        return {}


def _extract_from_png(
    previews_path: Path,
    image_filename: str,
) -> List[PreviewModelHint]:
    """Extract hints from PNG tEXt chunks (A1111/ComfyUI metadata).

    Checks PNG magic bytes, not file extension — handles Civitai's
    PNG-with-.jpeg-extension files correctly.
    """
    safe_name = _sanitize_filename(image_filename)
    if safe_name is None:
        return []
    file_path = previews_path / safe_name
    if not file_path.exists():
        return []

    text_data = _read_png_text_chunks(file_path)
    if not text_data:
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
        # Extract model hash if present
        hash_match = re.search(r"Model hash:\s*([0-9a-fA-F]+)", parameters)
        model_hash = hash_match.group(1) if hash_match else None
        hints.append(PreviewModelHint(
            filename=_normalize_filename(model_name),
            kind=AssetKind.CHECKPOINT,
            source_image=source_image,
            source_type="png_embedded",
            raw_value=model_name,
            hash=model_hash,
        ))

    # LoRA references: "<lora:name:weight>"
    lora_matches = re.findall(r"<lora:([^:>]+):([^>]+)>", parameters)
    for lora_name, weight_str in lora_matches:
        weight = _parse_float(weight_str)
        hints.append(PreviewModelHint(
            filename=_normalize_filename(lora_name),
            kind=AssetKind.LORA,
            source_image=source_image,
            source_type="png_embedded",
            raw_value=lora_name,
            weight=weight,
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
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue

        # Special: Power Lora Loader (rgthree) — nested lora_N dicts
        if "power lora loader" in class_type.lower():
            hints.extend(_parse_power_lora_loader(inputs, source_image))
            continue

        node_def = COMFYUI_NODE_REGISTRY.get(class_type)
        if not node_def:
            continue

        # Check ALL input keys (supports multi-model nodes like DualCLIPLoader)
        for key in node_def.input_keys:
            value = inputs.get(key)
            if value and isinstance(value, str):
                hints.append(PreviewModelHint(
                    filename=_normalize_filename(value),
                    kind=node_def.kind,
                    source_image=source_image,
                    source_type="png_embedded",
                    raw_value=value,
                ))

    return hints


def _parse_power_lora_loader(
    inputs: Dict[str, Any],
    source_image: str,
) -> List[PreviewModelHint]:
    """Parse Power Lora Loader (rgthree) inputs.

    Structure: lora_1: {on: bool, lora: "path.safetensors", strength: float}
    Only extracts LoRAs that are enabled (on=true).
    """
    hints: List[PreviewModelHint] = []
    for key, value in inputs.items():
        if not key.startswith("lora_") or not isinstance(value, dict):
            continue
        if not value.get("on", False):
            continue
        lora_path = value.get("lora")
        if not lora_path or not isinstance(lora_path, str):
            continue
        weight = value.get("strength")
        if not isinstance(weight, (int, float)):
            weight = None
        else:
            weight = float(weight)
        hints.append(PreviewModelHint(
            filename=_normalize_filename(lora_path),
            kind=AssetKind.LORA,
            source_image=source_image,
            source_type="png_embedded",
            raw_value=lora_path,
            weight=weight,
        ))
    return hints


def _normalize_filename(name: str) -> str:
    """Normalize a model name to a filename-like form.

    Strips path prefixes (e.g., "checkpoints/model.safetensors" → "model.safetensors").
    """
    # Strip path prefixes (ComfyUI often stores "checkpoints/model.safetensors")
    name = name.replace("\\", "/")
    if "/" in name:
        name = name.rsplit("/", 1)[-1]

    return name


def _parse_float(s: str) -> Optional[float]:
    """Safely parse a float string, returning None on failure."""
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def filter_hints_by_kind(
    hints: List[PreviewModelHint],
    kind: AssetKind,
) -> List[PreviewModelHint]:
    """Filter hints to only those matching the target AssetKind.

    Hints with kind=None are included (unknown kind, could match anything).
    """
    return [h for h in hints if h.kind is None or h.kind == kind]
