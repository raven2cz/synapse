"""
Workflow Generator

Generates default ComfyUI workflows for packs based on:
- Asset type (LoRA, Checkpoint, etc.)
- Base model architecture
- Generation parameters from Civitai
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from ..core.models import (
    Pack, AssetType, AssetDependency, GenerationParameters,
    WorkflowInfo, DependencyStatus
)


# Sampler name mapping from Civitai to ComfyUI
SAMPLER_MAPPING = {
    "Euler": "euler",
    "Euler a": "euler_ancestral",
    "DPM++ 2M": "dpmpp_2m",
    "DPM++ 2M Karras": "dpmpp_2m",
    "DPM++ 2M SDE": "dpmpp_2m_sde",
    "DPM++ 2M SDE Karras": "dpmpp_2m_sde",
    "DPM++ 3M SDE": "dpmpp_3m_sde",
    "DPM++ 3M SDE Karras": "dpmpp_3m_sde",
    "DPM++ 3M SDE Exponential": "dpmpp_3m_sde",
    "DPM++ SDE": "dpmpp_sde",
    "DPM++ SDE Karras": "dpmpp_sde",
    "DDIM": "ddim",
    "LMS": "lms",
    "LMS Karras": "lms",
    "Heun": "heun",
    "DPM2": "dpm_2",
    "DPM2 a": "dpm_2_ancestral",
    "UniPC": "uni_pc",
    "PLMS": "plms",
}

# Scheduler mapping
SCHEDULER_MAPPING = {
    "Euler": "normal",
    "Euler a": "normal",
    "DPM++ 2M": "normal",
    "DPM++ 2M Karras": "karras",
    "DPM++ 2M SDE": "normal",
    "DPM++ 2M SDE Karras": "karras",
    "DPM++ 3M SDE": "normal",
    "DPM++ 3M SDE Karras": "karras",
    "DPM++ 3M SDE Exponential": "exponential",
    "DPM++ SDE": "normal",
    "DPM++ SDE Karras": "karras",
    "DDIM": "ddim_uniform",
    "LMS": "normal",
    "LMS Karras": "karras",
    "Heun": "normal",
    "DPM2": "normal",
    "DPM2 a": "normal",
    "UniPC": "normal",
    "PLMS": "normal",
}

# Base model to architecture mapping
BASE_MODEL_ARCHITECTURE = {
    "SD 1.5": "sd15",
    "SD 1.4": "sd15",
    "SD 2.0": "sd20",
    "SD 2.1": "sd21",
    "SDXL 1.0": "sdxl",
    "SDXL": "sdxl",
    "SDXL Turbo": "sdxl",
    "SDXL Lightning": "sdxl",
    "Pony": "sdxl",
    "Illustrious": "sdxl",
    "NoobAI": "sdxl",
    "Flux.1 D": "flux",
    "Flux.1 S": "flux",
    "Flux": "flux",
    "AuraFlow": "auraflow",
}


class NodeBuilder:
    """Helper to build ComfyUI nodes with proper structure."""
    
    def __init__(self):
        self.nodes: List[Dict] = []
        self.links: List[List] = []
        self._node_id: int = 0
        self._link_id: int = 0
    
    def add_node(
        self,
        node_type: str,
        widgets_values: List[Any],
        inputs_spec: List[Dict],
        outputs_spec: List[Dict],
        pos: List[int] = None,
        title: str = None,
        order: int = None,
    ) -> int:
        """Add a node and return its ID."""
        self._node_id += 1
        node_id = self._node_id
        
        if pos is None:
            col = (node_id - 1) % 3
            row = (node_id - 1) // 3
            pos = [100 + col * 350, 100 + row * 250]
        
        # Build inputs with link references
        inputs = []
        for inp in inputs_spec:
            input_def = {
                "name": inp["name"],
                "type": inp["type"],
                "link": None,
            }
            if inp["type"] in ("INT", "FLOAT", "STRING", "COMBO"):
                input_def["widget"] = {"name": inp["name"]}
            inputs.append(input_def)
        
        # Build outputs
        outputs = []
        for i, out in enumerate(outputs_spec):
            outputs.append({
                "name": out["name"],
                "type": out["type"],
                "links": [],
                "slot_index": i,
            })
        
        node = {
            "id": node_id,
            "type": node_type,
            "pos": pos,
            "size": [300, 150],
            "flags": {},
            "order": order if order is not None else node_id - 1,
            "mode": 0,
            "inputs": inputs,
            "outputs": outputs,
            "properties": {"Node name for S&R": node_type},
            "widgets_values": widgets_values,
        }
        
        if title:
            node["title"] = title
        
        self.nodes.append(node)
        return node_id
    
    def connect(
        self,
        from_node: int,
        from_slot: int,
        to_node: int,
        to_slot: int,
        link_type: str,
    ) -> int:
        """Create a connection between nodes. Returns link ID."""
        self._link_id += 1
        link_id = self._link_id
        
        # Add link: [link_id, from_node, from_slot, to_node, to_slot, type]
        self.links.append([link_id, from_node, from_slot, to_node, to_slot, link_type])
        
        # Update source node's output links
        for node in self.nodes:
            if node["id"] == from_node and from_slot < len(node["outputs"]):
                node["outputs"][from_slot]["links"].append(link_id)
        
        # Update target node's input link
        for node in self.nodes:
            if node["id"] == to_node and to_slot < len(node["inputs"]):
                node["inputs"][to_slot]["link"] = link_id
        
        return link_id
    
    def build(self, pack_name: str) -> Dict:
        """Build final workflow JSON."""
        return {
            "last_node_id": self._node_id,
            "last_link_id": self._link_id,
            "nodes": self.nodes,
            "links": self.links,
            "groups": [],
            "config": {},
            "extra": {
                "ds": {"scale": 1.0, "offset": [0, 0]},
                "synapse": {
                    "pack_name": pack_name,
                    "generated": True,
                }
            },
            "version": 0.4
        }


class WorkflowGenerator:
    """Generates ComfyUI workflows for packs."""
    
    def generate_default_workflow(
        self,
        pack: Pack,
        output_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Generate a default workflow for a pack."""
        architecture = self._detect_architecture(pack)
        params = pack.parameters or GenerationParameters()
        checkpoint_asset = self._get_checkpoint_asset(pack)
        lora_assets = self._get_lora_assets(pack)
        
        workflow = self._build_sd_workflow(
            pack, architecture, params, checkpoint_asset, lora_assets
        )
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(workflow, f, indent=2)
        
        return workflow
    
    def _detect_architecture(self, pack: Pack) -> str:
        """Detect architecture from pack's base model."""
        if pack.model_info and pack.model_info.base_model:
            base = pack.model_info.base_model
            for key, arch in BASE_MODEL_ARCHITECTURE.items():
                if key.lower() in base.lower():
                    return arch
        
        for dep in pack.dependencies:
            if dep.asset_type == AssetType.BASE_MODEL:
                if dep.base_model_hint:
                    for key, arch in BASE_MODEL_ARCHITECTURE.items():
                        if key.lower() in dep.base_model_hint.lower():
                            return arch
                if dep.name:
                    for key, arch in BASE_MODEL_ARCHITECTURE.items():
                        if key.lower() in dep.name.lower():
                            return arch
        
        return "sd15"
    
    def _get_checkpoint_asset(self, pack: Pack) -> Optional[AssetDependency]:
        """Get the checkpoint/base model asset."""
        for dep in pack.dependencies:
            if dep.asset_type == AssetType.BASE_MODEL:
                return dep
        for dep in pack.dependencies:
            if dep.asset_type == AssetType.CHECKPOINT:
                return dep
        return None
    
    def _get_lora_assets(self, pack: Pack) -> List[AssetDependency]:
        """Get all LoRA assets."""
        return [dep for dep in pack.dependencies if dep.asset_type == AssetType.LORA]
    
    def _map_sampler(self, civitai_sampler: Optional[str]) -> str:
        if not civitai_sampler:
            return "euler"
        return SAMPLER_MAPPING.get(civitai_sampler, "euler")
    
    def _map_scheduler(self, civitai_sampler: Optional[str]) -> str:
        if not civitai_sampler:
            return "normal"
        return SCHEDULER_MAPPING.get(civitai_sampler, "normal")
    
    def _build_sd_workflow(
        self,
        pack: Pack,
        architecture: str,
        params: GenerationParameters,
        checkpoint_asset: Optional[AssetDependency],
        lora_assets: List[AssetDependency],
    ) -> Dict[str, Any]:
        """Build SD/SDXL style workflow with proper ComfyUI format."""
        builder = NodeBuilder()
        
        # Dimensions based on architecture
        if architecture == "sdxl":
            default_width, default_height = 1024, 1024
        else:
            default_width, default_height = 512, 512
        
        width = params.width or default_width
        height = params.height or default_height
        sampler = self._map_sampler(params.sampler)
        scheduler = self._map_scheduler(params.sampler)
        steps = params.steps or 20
        cfg = params.cfg_scale or 7.0
        seed = params.seed if params.seed and params.seed >= 0 else 0
        
        # Get checkpoint filename from pack dependency
        ckpt_filename = "model.safetensors"
        if checkpoint_asset:
            if checkpoint_asset.local_path:
                ckpt_filename = Path(checkpoint_asset.local_path).name
            elif checkpoint_asset.filename:
                ckpt_filename = checkpoint_asset.filename
        
        # 1. CheckpointLoaderSimple
        ckpt_id = builder.add_node(
            node_type="CheckpointLoaderSimple",
            widgets_values=[ckpt_filename],
            inputs_spec=[{"name": "ckpt_name", "type": "COMBO"}],
            outputs_spec=[
                {"name": "MODEL", "type": "MODEL"},
                {"name": "CLIP", "type": "CLIP"},
                {"name": "VAE", "type": "VAE"},
            ],
            pos=[50, 100],
            title="Load Checkpoint",
            order=0,
        )
        
        current_model_node, current_model_slot = ckpt_id, 0
        current_clip_node, current_clip_slot = ckpt_id, 1
        vae_node, vae_slot = ckpt_id, 2
        
        # 2. LoRA Loaders
        for i, lora in enumerate(lora_assets):
            lora_filename = lora.filename if lora.filename else f"{lora.name}.safetensors"
            if lora.local_path:
                lora_filename = Path(lora.local_path).name
            
            strength = 1.0
            if pack.model_info and pack.model_info.strength_recommended:
                strength = pack.model_info.strength_recommended
            
            lora_id = builder.add_node(
                node_type="LoraLoader",
                widgets_values=[lora_filename, strength, strength],
                inputs_spec=[
                    {"name": "model", "type": "MODEL"},
                    {"name": "clip", "type": "CLIP"},
                    {"name": "lora_name", "type": "COMBO"},
                    {"name": "strength_model", "type": "FLOAT"},
                    {"name": "strength_clip", "type": "FLOAT"},
                ],
                outputs_spec=[
                    {"name": "MODEL", "type": "MODEL"},
                    {"name": "CLIP", "type": "CLIP"},
                ],
                pos=[400, 100 + i * 200],
                title=f"Load LoRA: {lora.name}",
                order=i + 1,
            )
            
            builder.connect(current_model_node, current_model_slot, lora_id, 0, "MODEL")
            builder.connect(current_clip_node, current_clip_slot, lora_id, 1, "CLIP")
            
            current_model_node, current_model_slot = lora_id, 0
            current_clip_node, current_clip_slot = lora_id, 1
        
        # 3. CLIP Set Last Layer (for clip_skip) - ONLY if explicitly set in parameters
        # clip_skip is NOT defaulted based on architecture - user must set it explicitly
        clip_skip = params.clip_skip
        
        # Only add CLIPSetLastLayer if clip_skip is explicitly set and > 1
        if clip_skip is not None and clip_skip > 1:
            clip_skip_id = builder.add_node(
                node_type="CLIPSetLastLayer",
                widgets_values=[-clip_skip],  # stop_at_clip_layer = -N for clip_skip N
                inputs_spec=[
                    {"name": "clip", "type": "CLIP"},
                    {"name": "stop_at_clip_layer", "type": "INT"},
                ],
                outputs_spec=[{"name": "CLIP", "type": "CLIP"}],
                pos=[600, 200],
                title=f"CLIP Skip {clip_skip}",
                order=len(lora_assets) + 1,
            )
            builder.connect(current_clip_node, current_clip_slot, clip_skip_id, 0, "CLIP")
            current_clip_node, current_clip_slot = clip_skip_id, 0
        
        # 4. Build prompts
        trigger_words = ""
        if pack.model_info and pack.model_info.trigger_words:
            trigger_words = ", ".join(pack.model_info.trigger_words) + ", "
        
        positive_prompt = f"{trigger_words}masterpiece, best quality, "
        negative_prompt = "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry"
        
        base_order = len(lora_assets) + (2 if clip_skip and clip_skip > 1 else 1)
        
        # 5. CLIP Text Encode (Positive)
        pos_id = builder.add_node(
            node_type="CLIPTextEncode",
            widgets_values=[positive_prompt],
            inputs_spec=[
                {"name": "clip", "type": "CLIP"},
                {"name": "text", "type": "STRING"},
            ],
            outputs_spec=[{"name": "CONDITIONING", "type": "CONDITIONING"}],
            pos=[750, 100],
            title="Positive Prompt",
            order=base_order,
        )
        builder.connect(current_clip_node, current_clip_slot, pos_id, 0, "CLIP")
        
        # 6. CLIP Text Encode (Negative)
        neg_id = builder.add_node(
            node_type="CLIPTextEncode",
            widgets_values=[negative_prompt],
            inputs_spec=[
                {"name": "clip", "type": "CLIP"},
                {"name": "text", "type": "STRING"},
            ],
            outputs_spec=[{"name": "CONDITIONING", "type": "CONDITIONING"}],
            pos=[750, 350],
            title="Negative Prompt",
            order=base_order + 1,
        )
        builder.connect(current_clip_node, current_clip_slot, neg_id, 0, "CLIP")
        
        # 6. Empty Latent Image
        latent_id = builder.add_node(
            node_type="EmptyLatentImage",
            widgets_values=[width, height, 1],
            inputs_spec=[
                {"name": "width", "type": "INT"},
                {"name": "height", "type": "INT"},
                {"name": "batch_size", "type": "INT"},
            ],
            outputs_spec=[{"name": "LATENT", "type": "LATENT"}],
            pos=[750, 550],
            title="Empty Latent Image",
            order=base_order + 2,
        )
        
        # 7. KSampler
        sampler_id = builder.add_node(
            node_type="KSampler",
            widgets_values=[seed, "randomize", steps, cfg, sampler, scheduler, 1.0],
            inputs_spec=[
                {"name": "model", "type": "MODEL"},
                {"name": "positive", "type": "CONDITIONING"},
                {"name": "negative", "type": "CONDITIONING"},
                {"name": "latent_image", "type": "LATENT"},
                {"name": "seed", "type": "INT"},
                {"name": "steps", "type": "INT"},
                {"name": "cfg", "type": "FLOAT"},
                {"name": "sampler_name", "type": "COMBO"},
                {"name": "scheduler", "type": "COMBO"},
                {"name": "denoise", "type": "FLOAT"},
            ],
            outputs_spec=[{"name": "LATENT", "type": "LATENT"}],
            pos=[1100, 200],
            title="KSampler",
            order=base_order + 3,
        )
        builder.connect(current_model_node, current_model_slot, sampler_id, 0, "MODEL")
        builder.connect(pos_id, 0, sampler_id, 1, "CONDITIONING")
        builder.connect(neg_id, 0, sampler_id, 2, "CONDITIONING")
        builder.connect(latent_id, 0, sampler_id, 3, "LATENT")
        
        # 8. VAE Decode
        decode_id = builder.add_node(
            node_type="VAEDecode",
            widgets_values=[],
            inputs_spec=[
                {"name": "samples", "type": "LATENT"},
                {"name": "vae", "type": "VAE"},
            ],
            outputs_spec=[{"name": "IMAGE", "type": "IMAGE"}],
            pos=[1450, 200],
            title="VAE Decode",
            order=base_order + 4,
        )
        builder.connect(sampler_id, 0, decode_id, 0, "LATENT")
        builder.connect(vae_node, vae_slot, decode_id, 1, "VAE")
        
        # 9. Preview Image
        preview_id = builder.add_node(
            node_type="PreviewImage",
            widgets_values=[],
            inputs_spec=[{"name": "images", "type": "IMAGE"}],
            outputs_spec=[],
            pos=[1450, 400],
            title="Preview",
            order=base_order + 5,
        )
        builder.connect(decode_id, 0, preview_id, 0, "IMAGE")
        
        # 10. Save Image
        save_prefix = f"synapse/{pack.metadata.name}"
        save_id = builder.add_node(
            node_type="SaveImage",
            widgets_values=[save_prefix],
            inputs_spec=[
                {"name": "images", "type": "IMAGE"},
                {"name": "filename_prefix", "type": "STRING"},
            ],
            outputs_spec=[],
            pos=[1450, 550],
            title="Save Image",
            order=base_order + 6,
        )
        builder.connect(decode_id, 0, save_id, 0, "IMAGE")
        
        return builder.build(pack.metadata.name)


def create_workflow_generator() -> WorkflowGenerator:
    """Factory function."""
    return WorkflowGenerator()


def generate_pack_workflow(pack: Pack, output_path: Path) -> WorkflowInfo:
    """Convenience function to generate and register a workflow for a pack."""
    generator = WorkflowGenerator()
    generator.generate_default_workflow(pack, output_path)
    
    return WorkflowInfo(
        name=f"Default - {pack.metadata.name}",
        filename=output_path.name,
        description="Auto-generated default workflow",
        is_default=True,
    )
