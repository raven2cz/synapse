"""
Workflow Scanner

Analyzes ComfyUI workflow JSON files to extract:
- Model dependencies (checkpoints, LoRAs, VAEs, etc.)
- Custom node requirements
- Input/output configurations
- Parameter values
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple
from dataclasses import dataclass, field

from ..core.models import AssetType, AssetDependency, AssetSource, CustomNodeDependency


@dataclass
class WorkflowNode:
    """Parsed node from a ComfyUI workflow."""
    id: int
    type: str
    title: Optional[str]
    inputs: Dict[str, Any]
    outputs: List[Dict[str, Any]]
    widgets_values: List[Any]
    properties: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, node_id: int, data: Dict[str, Any]) -> 'WorkflowNode':
        return cls(
            id=node_id if isinstance(node_id, int) else data.get("id", 0),
            type=data.get("type", "Unknown"),
            title=data.get("title"),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", []),
            widgets_values=data.get("widgets_values", []),
            properties=data.get("properties", {}),
        )


@dataclass
class ScannedAsset:
    """An asset reference found in a workflow."""
    name: str
    asset_type: AssetType
    node_type: str
    node_id: int
    widget_index: Optional[int] = None
    
    def to_dependency(self) -> AssetDependency:
        """Convert to an AssetDependency with local source."""
        from ..core.models import ASSET_TYPE_FOLDERS
        
        folder = ASSET_TYPE_FOLDERS.get(self.asset_type, "unknown")
        return AssetDependency(
            name=self.name,
            asset_type=self.asset_type,
            source=AssetSource.LOCAL,
            filename=self.name,
            local_path=f"{folder}/{self.name}",
            required=True,
        )


@dataclass
class WorkflowScanResult:
    """Result of scanning a workflow for dependencies."""
    assets: List[ScannedAsset] = field(default_factory=list)
    custom_node_types: Set[str] = field(default_factory=set)
    output_nodes: List[WorkflowNode] = field(default_factory=list)
    input_nodes: List[WorkflowNode] = field(default_factory=list)
    all_nodes: List[WorkflowNode] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class WorkflowScanner:
    """
    Scans ComfyUI workflow JSON files to extract dependencies and structure.
    
    Identifies:
    - Checkpoint loaders and their model references
    - LoRA loaders and their model references
    - VAE loaders
    - CLIP loaders / Text encoders
    - ControlNet loaders
    - Upscaler loaders
    - Custom nodes (non-core node types)
    - Output nodes (SaveImage, VHS_VideoCombine, etc.)
    """
    
    # Node types that load models, mapped to asset types
    LOADER_NODE_TYPES: Dict[str, Tuple[AssetType, int]] = {
        # (asset_type, widget_index for model name)
        # Checkpoints
        "CheckpointLoaderSimple": (AssetType.CHECKPOINT, 0),
        "CheckpointLoader": (AssetType.CHECKPOINT, 0),
        "UNETLoader": (AssetType.DIFFUSION_MODEL, 0),
        "UnetLoaderGGUF": (AssetType.DIFFUSION_MODEL, 0),
        "LoaderGGUF": (AssetType.CHECKPOINT, 0),
        
        # LoRAs
        "LoraLoader": (AssetType.LORA, 0),
        "LoraLoaderModelOnly": (AssetType.LORA, 0),
        
        # VAE
        "VAELoader": (AssetType.VAE, 0),
        
        # CLIP / Text Encoders
        "CLIPLoader": (AssetType.TEXT_ENCODER, 0),
        "DualCLIPLoader": (AssetType.TEXT_ENCODER, 0),
        "TripleCLIPLoader": (AssetType.TEXT_ENCODER, 0),
        
        # ControlNet
        "ControlNetLoader": (AssetType.CONTROLNET, 0),
        "DiffControlNetLoader": (AssetType.CONTROLNET, 0),
        
        # Upscalers
        "UpscaleModelLoader": (AssetType.UPSCALER, 0),
        "ImageUpscaleWithModel": (AssetType.UPSCALER, 0),
        
        # Embeddings
        "EmbeddingLoader": (AssetType.EMBEDDING, 0),
    }
    
    # Core ComfyUI node types (not custom nodes)
    CORE_NODE_PREFIXES = {
        "KSampler", "CLIP", "VAE", "Checkpoint", "Load", "Save",
        "Empty", "Preview", "Image", "Latent", "Conditioning",
        "Model", "Control", "Upscale", "Mask", "Note", "Primitive",
        "Reroute", "PrimitiveNode", "PreviewImage", "SaveImage",
    }
    
    # Output node types
    OUTPUT_NODE_TYPES = {
        "SaveImage", "PreviewImage", "VHS_VideoCombine", "SaveVideo",
        "CreateVideo", "SaveAnimatedWEBP", "SaveAnimatedPNG",
    }
    
    # Input node types  
    INPUT_NODE_TYPES = {
        "LoadImage", "LoadImageMask", "LoadVideo", "VHS_LoadVideo",
    }
    
    def __init__(self):
        pass
    
    def scan_file(self, path: Path) -> WorkflowScanResult:
        """Scan a workflow JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            return self.scan_workflow(workflow_data)
        except json.JSONDecodeError as e:
            result = WorkflowScanResult()
            result.errors.append(f"JSON parse error: {e}")
            return result
        except Exception as e:
            result = WorkflowScanResult()
            result.errors.append(f"Error reading file: {e}")
            return result
    
    def scan_workflow(self, workflow_data: Dict[str, Any]) -> WorkflowScanResult:
        """
        Scan a workflow dictionary for dependencies.
        
        Supports both formats:
        - List format: workflow_data["nodes"] is a list
        - Dict format: nodes are indexed by ID
        """
        result = WorkflowScanResult()
        
        # Extract nodes
        nodes_data = workflow_data.get("nodes", [])
        
        if isinstance(nodes_data, list):
            for node_data in nodes_data:
                node = WorkflowNode.from_dict(node_data.get("id", 0), node_data)
                result.all_nodes.append(node)
                self._process_node(node, result)
        elif isinstance(nodes_data, dict):
            for node_id, node_data in nodes_data.items():
                node = WorkflowNode.from_dict(int(node_id), node_data)
                result.all_nodes.append(node)
                self._process_node(node, result)
        
        return result
    
    def _process_node(self, node: WorkflowNode, result: WorkflowScanResult) -> None:
        """Process a single node for assets and metadata."""
        
        # Check for loader nodes
        if node.type in self.LOADER_NODE_TYPES:
            asset_type, widget_index = self.LOADER_NODE_TYPES[node.type]
            
            # Extract model name from widgets_values
            if node.widgets_values and len(node.widgets_values) > widget_index:
                model_name = node.widgets_values[widget_index]
                if model_name and isinstance(model_name, str):
                    result.assets.append(ScannedAsset(
                        name=model_name,
                        asset_type=asset_type,
                        node_type=node.type,
                        node_id=node.id,
                        widget_index=widget_index,
                    ))
        
        # Check for additional LoRA in LoraLoader (multiple LoRAs)
        if node.type == "LoraLoader" and node.widgets_values:
            # LoraLoader typically has: [lora_name, strength_model, strength_clip]
            if len(node.widgets_values) > 0:
                lora_name = node.widgets_values[0]
                if lora_name and isinstance(lora_name, str):
                    # Already added above, but ensure it's there
                    pass
        
        # Check for DualCLIPLoader (has two CLIP models)
        if node.type == "DualCLIPLoader" and node.widgets_values:
            for i, value in enumerate(node.widgets_values[:2]):
                if value and isinstance(value, str) and value.endswith(('.safetensors', '.bin', '.pt')):
                    result.assets.append(ScannedAsset(
                        name=value,
                        asset_type=AssetType.TEXT_ENCODER,
                        node_type=node.type,
                        node_id=node.id,
                        widget_index=i,
                    ))
        
        # Check for custom nodes
        if self._is_custom_node(node.type):
            result.custom_node_types.add(node.type)
            
            # Also check properties for cnr_id (ComfyUI Node Registry)
            if "cnr_id" in node.properties:
                cnr_id = node.properties["cnr_id"]
                if cnr_id and cnr_id != "comfy-core":
                    result.custom_node_types.add(f"cnr:{cnr_id}")
        
        # Check for output nodes
        if node.type in self.OUTPUT_NODE_TYPES:
            result.output_nodes.append(node)
        
        # Check for input nodes
        if node.type in self.INPUT_NODE_TYPES:
            result.input_nodes.append(node)
    
    def _is_custom_node(self, node_type: str) -> bool:
        """Check if a node type is a custom (non-core) node."""
        # Check core prefixes
        for prefix in self.CORE_NODE_PREFIXES:
            if node_type.startswith(prefix):
                return False
        
        # Check for common core patterns
        core_patterns = [
            r"^(Get|Set|Switch|Compare|Math|String|Int|Float|Bool)",
            r"^(Repeat|Loop|Random|Convert|Combine|Split)",
        ]
        
        for pattern in core_patterns:
            if re.match(pattern, node_type):
                return False
        
        return True
    
    def get_unique_assets(self, result: WorkflowScanResult) -> List[ScannedAsset]:
        """Get deduplicated list of assets."""
        seen = set()
        unique = []
        
        for asset in result.assets:
            key = (asset.name, asset.asset_type)
            if key not in seen:
                seen.add(key)
                unique.append(asset)
        
        return unique
    
    def scan_multiple(self, paths: List[Path]) -> Dict[Path, WorkflowScanResult]:
        """Scan multiple workflow files."""
        results = {}
        for path in paths:
            results[path] = self.scan_file(path)
        return results
    
    def merge_results(self, results: List[WorkflowScanResult]) -> WorkflowScanResult:
        """Merge multiple scan results into one."""
        merged = WorkflowScanResult()
        
        seen_assets = set()
        
        for result in results:
            for asset in result.assets:
                key = (asset.name, asset.asset_type)
                if key not in seen_assets:
                    seen_assets.add(key)
                    merged.assets.append(asset)
            
            merged.custom_node_types.update(result.custom_node_types)
            merged.output_nodes.extend(result.output_nodes)
            merged.input_nodes.extend(result.input_nodes)
            merged.all_nodes.extend(result.all_nodes)
            merged.errors.extend(result.errors)
        
        return merged


def scan_workflow_file(path: Path) -> WorkflowScanResult:
    """Convenience function to scan a single workflow file."""
    scanner = WorkflowScanner()
    return scanner.scan_file(path)


def extract_dependencies_from_workflow(path: Path) -> List[AssetDependency]:
    """Extract asset dependencies from a workflow file."""
    scanner = WorkflowScanner()
    result = scanner.scan_file(path)
    unique_assets = scanner.get_unique_assets(result)
    return [asset.to_dependency() for asset in unique_assets]
