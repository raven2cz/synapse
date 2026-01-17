"""
Dependency Resolver

Resolves dependencies from workflow scans:
- Maps custom node types to git repositories
- Maps asset names to download sources
- Integrates with ComfyUI-Manager registry
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

from ..core.models import (
    AssetDependency, AssetType, AssetSource,
    CustomNodeDependency, ASSET_TYPE_FOLDERS
)
from ..workflows.scanner import WorkflowScanResult, ScannedAsset


@dataclass
class NodePackInfo:
    """Information about a custom node package."""
    name: str
    git_url: str
    description: Optional[str] = None
    pip_requirements: List[str] = field(default_factory=list)
    node_types: List[str] = field(default_factory=list)


class NodeRegistry:
    """
    Registry of custom nodes and their sources.
    
    Can be loaded from:
    - ComfyUI-Manager's custom-node-list.json
    - Local cache
    - Online registry
    """
    
    def __init__(self):
        self._node_to_pack: Dict[str, NodePackInfo] = {}
        self._packs: Dict[str, NodePackInfo] = {}
    
    def load_from_manager_json(self, path: Path) -> None:
        """Load from ComfyUI-Manager's custom-node-list.json format."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Format: {"custom_nodes": [{"author": ..., "title": ..., "reference": ..., ...}]}
        for entry in data.get("custom_nodes", []):
            pack_info = NodePackInfo(
                name=entry.get("title", entry.get("author", "Unknown")),
                git_url=entry.get("reference", ""),
                description=entry.get("description"),
                pip_requirements=entry.get("pip", []) if isinstance(entry.get("pip"), list) else [],
            )
            
            # Extract node types from files if available
            if "files" in entry:
                for file_url in entry["files"]:
                    # Files are typically git URLs
                    pass
            
            # Store by git URL
            if pack_info.git_url:
                self._packs[pack_info.git_url] = pack_info
                self._packs[pack_info.name.lower()] = pack_info
    
    def load_from_extension_map(self, path: Path) -> None:
        """Load from ComfyUI-Manager's extension-node-map.json format."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Format: {"git_url": [["node_type1", "node_type2", ...], {...info}]}
        for git_url, entry_data in data.items():
            if not isinstance(entry_data, list) or len(entry_data) < 1:
                continue
            
            node_types = entry_data[0] if isinstance(entry_data[0], list) else []
            
            pack_info = NodePackInfo(
                name=git_url.split("/")[-1].replace(".git", ""),
                git_url=git_url,
                node_types=node_types,
            )
            
            self._packs[git_url] = pack_info
            
            # Map node types to pack
            for node_type in node_types:
                self._node_to_pack[node_type] = pack_info
    
    def find_pack_for_node(self, node_type: str) -> Optional[NodePackInfo]:
        """Find the pack that provides a node type."""
        # Direct lookup
        if node_type in self._node_to_pack:
            return self._node_to_pack[node_type]
        
        # Check CNR ID format (cnr:pack_name)
        if node_type.startswith("cnr:"):
            cnr_id = node_type[4:]
            # Try to find by CNR ID
            for pack in self._packs.values():
                if cnr_id.lower() in pack.name.lower():
                    return pack
        
        return None
    
    def get_pack(self, identifier: str) -> Optional[NodePackInfo]:
        """Get pack by name or URL."""
        return self._packs.get(identifier) or self._packs.get(identifier.lower())


class DependencyResolver:
    """
    Resolves workflow dependencies to downloadable sources.
    
    Features:
    - Maps custom nodes to git repositories
    - Suggests asset sources based on naming patterns
    - Integrates with Civitai/HuggingFace for model resolution
    """
    
    # Known model naming patterns and their likely sources
    MODEL_PATTERNS = {
        # HuggingFace patterns
        r".*fp8.*scaled.*": AssetSource.HUGGINGFACE,
        r"umt5_.*": AssetSource.HUGGINGFACE,
        r".*diffusion_pytorch_model.*": AssetSource.HUGGINGFACE,
        
        # Civitai patterns  
        r".*pony.*v\d+.*": AssetSource.CIVITAI,
        r".*_v\d+\.safetensors": AssetSource.CIVITAI,
        
        # GGUF patterns (often from HF)
        r".*\.gguf": AssetSource.HUGGINGFACE,
    }
    
    # Known HuggingFace model mappings
    KNOWN_HF_MODELS = {
        "umt5_xxl_fp8_e4m3fn_scaled.safetensors": {
            "repo_id": "Comfy-Org/Wan_2.1_ComfyUI_repackaged",
            "filename": "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        },
        "wan_2.1_vae.safetensors": {
            "repo_id": "Comfy-Org/Wan_2.2_ComfyUI_Repackaged",
            "filename": "split_files/vae/wan_2.1_vae.safetensors",
        },
        "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors": {
            "repo_id": "Comfy-Org/Wan_2.2_ComfyUI_Repackaged",
            "filename": "split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
        },
        "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors": {
            "repo_id": "Comfy-Org/Wan_2.2_ComfyUI_Repackaged",
            "filename": "split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
        },
        "z_image_turbo_bf16.safetensors": {
            "repo_id": "Comfy-Org/z_image_turbo",
            "filename": "split_files/diffusion_models/z_image_turbo_bf16.safetensors",
        },
        "qwen_3_4b.safetensors": {
            "repo_id": "Comfy-Org/z_image_turbo",
            "filename": "split_files/text_encoders/qwen_3_4b.safetensors",
        },
        "ae.safetensors": {
            "repo_id": "Comfy-Org/z_image_turbo",
            "filename": "split_files/vae/ae.safetensors",
        },
    }
    
    # Known custom node mappings
    KNOWN_CUSTOM_NODES = {
        "VHS_VideoCombine": {
            "name": "ComfyUI-VideoHelperSuite",
            "git_url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite",
        },
        "ReAuraPatcher": {
            "name": "RES4LYF",
            "git_url": "https://github.com/ClownsharkBatwing/RES4LYF",
        },
        "ClownsharKSampler_Beta": {
            "name": "RES4LYF",
            "git_url": "https://github.com/ClownsharkBatwing/RES4LYF",
        },
        "ClownsharkChainsampler_Beta": {
            "name": "RES4LYF",
            "git_url": "https://github.com/ClownsharkBatwing/RES4LYF",
        },
        "ModelSamplingAdvancedResolution": {
            "name": "RES4LYF",
            "git_url": "https://github.com/ClownsharkBatwing/RES4LYF",
        },
        "UnetLoaderGGUF": {
            "name": "ComfyUI-GGUF",
            "git_url": "https://github.com/city96/ComfyUI-GGUF",
        },
        "LoaderGGUF": {
            "name": "ComfyUI-GGUF",
            "git_url": "https://github.com/city96/ComfyUI-GGUF",
        },
        "PonyNoise": {
            "name": "ComfyUI_PonyNoise",
            "git_url": "https://huggingface.co/purplesmartai/pony-v7-base/blob/main/comfy_nodes/ComfyUI_PonyNoise.zip",
        },
        "VantageProject": {
            "name": "VantageLongWanVideo",
            "git_url": "https://github.com/vantagewithai/VantageLongWanVideo",
        },
        "VantageI2VDualLooper": {
            "name": "VantageLongWanVideo",
            "git_url": "https://github.com/vantagewithai/VantageLongWanVideo",
        },
    }
    
    def __init__(self, node_registry: Optional[NodeRegistry] = None):
        self.node_registry = node_registry or NodeRegistry()
    
    def resolve_custom_nodes(
        self,
        node_types: Set[str],
    ) -> List[CustomNodeDependency]:
        """Resolve custom node types to git repositories."""
        dependencies = []
        seen_urls = set()
        
        for node_type in node_types:
            # Skip CNR IDs for now (handled separately)
            if node_type.startswith("cnr:"):
                continue
            
            # Check known mappings first
            if node_type in self.KNOWN_CUSTOM_NODES:
                info = self.KNOWN_CUSTOM_NODES[node_type]
                if info["git_url"] not in seen_urls:
                    seen_urls.add(info["git_url"])
                    dependencies.append(CustomNodeDependency(
                        name=info["name"],
                        git_url=info["git_url"],
                    ))
                continue
            
            # Check registry
            pack = self.node_registry.find_pack_for_node(node_type)
            if pack and pack.git_url not in seen_urls:
                seen_urls.add(pack.git_url)
                dependencies.append(CustomNodeDependency(
                    name=pack.name,
                    git_url=pack.git_url,
                    pip_requirements=pack.pip_requirements,
                ))
        
        return dependencies
    
    def suggest_asset_source(self, asset: ScannedAsset) -> AssetSource:
        """Suggest the likely source for an asset based on patterns."""
        name = asset.name.lower()
        
        # Check known HF models
        if asset.name in self.KNOWN_HF_MODELS:
            return AssetSource.HUGGINGFACE
        
        # Check patterns
        for pattern, source in self.MODEL_PATTERNS.items():
            if re.match(pattern, name):
                return source
        
        # Default to local (needs manual resolution)
        return AssetSource.LOCAL
    
    def enrich_asset_dependency(
        self,
        asset: ScannedAsset,
    ) -> AssetDependency:
        """
        Enrich a scanned asset with source information.
        
        Tries to find the download source for the asset.
        """
        from ..core.models import HuggingFaceSource
        
        dep = asset.to_dependency()
        
        # Check known HF models
        if asset.name in self.KNOWN_HF_MODELS:
            hf_info = self.KNOWN_HF_MODELS[asset.name]
            dep.source = AssetSource.HUGGINGFACE
            dep.huggingface = HuggingFaceSource(
                repo_id=hf_info["repo_id"],
                filename=hf_info["filename"],
            )
            return dep
        
        # Suggest source based on patterns
        dep.source = self.suggest_asset_source(asset)
        
        return dep
    
    def resolve_workflow_dependencies(
        self,
        scan_result: WorkflowScanResult,
    ) -> tuple[List[AssetDependency], List[CustomNodeDependency]]:
        """
        Resolve all dependencies from a workflow scan.
        
        Returns:
            Tuple of (asset_dependencies, custom_node_dependencies)
        """
        # Resolve assets
        asset_deps = []
        seen_assets = set()
        
        for asset in scan_result.assets:
            key = (asset.name, asset.asset_type)
            if key not in seen_assets:
                seen_assets.add(key)
                enriched = self.enrich_asset_dependency(asset)
                asset_deps.append(enriched)
        
        # Resolve custom nodes
        node_deps = self.resolve_custom_nodes(scan_result.custom_node_types)
        
        return asset_deps, node_deps


def create_resolver() -> DependencyResolver:
    """Factory function to create a configured DependencyResolver."""
    return DependencyResolver()
