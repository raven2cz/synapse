"""
Synapse Data Models

Core data structures for packs, assets, workflows, and dependencies.
All serializable to JSON for file-based storage.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from pathlib import Path
from datetime import datetime
import json
import hashlib


class AssetType(Enum):
    """Types of assets that can be managed by Synapse."""
    CHECKPOINT = "checkpoint"
    LORA = "lora"
    VAE = "vae"
    CONTROLNET = "controlnet"
    UPSCALER = "upscaler"
    CLIP = "clip"
    TEXT_ENCODER = "text_encoder"
    DIFFUSION_MODEL = "diffusion_model"
    EMBEDDING = "embedding"
    CUSTOM_NODE = "custom_node"
    WORKFLOW = "workflow"
    BASE_MODEL = "base_model"
    UNKNOWN = "unknown"


class AssetSource(Enum):
    """Source providers for assets."""
    CIVITAI = "civitai"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    URL = "url"
    UNRESOLVED = "unresolved"
    UNKNOWN = "unknown"


class DependencyStatus(Enum):
    """Status of a dependency resolution."""
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    INSTALLED = "installed"
    MISSING = "missing"
    PENDING = "pending"  # Download URL saved, waiting for download


@dataclass
class AssetHash:
    """Hash information for asset verification."""
    sha256: Optional[str] = None
    blake3: Optional[str] = None
    civitai_autov2: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in {
            "sha256": self.sha256,
            "blake3": self.blake3,
            "civitai_autov2": self.civitai_autov2,
        }.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetHash':
        return cls(
            sha256=data.get("sha256"),
            blake3=data.get("blake3"),
            civitai_autov2=data.get("civitai_autov2"),
        )


@dataclass
class CivitaiSource:
    """Civitai-specific source information."""
    model_id: int
    model_version_id: int
    file_id: Optional[int] = None
    model_name: Optional[str] = None
    version_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in {
            "model_id": self.model_id,
            "model_version_id": self.model_version_id,
            "file_id": self.file_id,
            "model_name": self.model_name,
            "version_name": self.version_name,
        }.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CivitaiSource':
        return cls(
            model_id=data["model_id"],
            model_version_id=data["model_version_id"],
            file_id=data.get("file_id"),
            model_name=data.get("model_name"),
            version_name=data.get("version_name"),
        )


@dataclass
class HuggingFaceSource:
    """HuggingFace-specific source information."""
    repo_id: str
    filename: str
    revision: Optional[str] = None
    subfolder: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in {
            "repo_id": self.repo_id,
            "filename": self.filename,
            "revision": self.revision,
            "subfolder": self.subfolder,
        }.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HuggingFaceSource':
        return cls(
            repo_id=data["repo_id"],
            filename=data["filename"],
            revision=data.get("revision"),
            subfolder=data.get("subfolder"),
        )


@dataclass
class AssetDependency:
    """
    Represents a single asset dependency within a pack.
    Contains all information needed to locate, download, and verify the asset.
    """
    name: str
    asset_type: AssetType
    source: AssetSource
    
    civitai: Optional[CivitaiSource] = None
    huggingface: Optional[HuggingFaceSource] = None
    url: Optional[str] = None
    
    filename: str = ""
    file_size: Optional[int] = None
    hash: Optional[AssetHash] = None
    local_path: Optional[str] = None
    description: Optional[str] = None
    required: bool = True
    status: DependencyStatus = DependencyStatus.UNRESOLVED
    base_model_hint: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "asset_type": self.asset_type.value,
            "source": self.source.value,
            "filename": self.filename,
            "required": self.required,
            "status": self.status.value,
        }
        
        if self.civitai:
            result["civitai"] = self.civitai.to_dict()
        if self.huggingface:
            result["huggingface"] = self.huggingface.to_dict()
        if self.url:
            result["url"] = self.url
        if self.file_size:
            result["file_size"] = self.file_size
        if self.hash:
            result["hash"] = self.hash.to_dict()
        if self.local_path:
            result["local_path"] = self.local_path
        if self.description:
            result["description"] = self.description
        if self.base_model_hint:
            result["base_model_hint"] = self.base_model_hint
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssetDependency':
        return cls(
            name=data["name"],
            asset_type=AssetType(data["asset_type"]),
            source=AssetSource(data["source"]),
            civitai=CivitaiSource.from_dict(data["civitai"]) if "civitai" in data else None,
            huggingface=HuggingFaceSource.from_dict(data["huggingface"]) if "huggingface" in data else None,
            url=data.get("url"),
            filename=data.get("filename", ""),
            file_size=data.get("file_size"),
            hash=AssetHash.from_dict(data["hash"]) if "hash" in data else None,
            local_path=data.get("local_path"),
            description=data.get("description"),
            required=data.get("required", True),
            status=DependencyStatus(data.get("status", "unresolved")),
            base_model_hint=data.get("base_model_hint"),
        )


@dataclass
class CustomNodeDependency:
    """Represents a custom node package dependency."""
    name: str
    git_url: str
    commit: Optional[str] = None
    branch: Optional[str] = None
    pip_requirements: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "git_url": self.git_url,
        }
        if self.commit:
            result["commit"] = self.commit
        if self.branch:
            result["branch"] = self.branch
        if self.pip_requirements:
            result["pip_requirements"] = self.pip_requirements
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CustomNodeDependency':
        return cls(
            name=data["name"],
            git_url=data["git_url"],
            commit=data.get("commit"),
            branch=data.get("branch"),
            pip_requirements=data.get("pip_requirements", []),
        )


@dataclass
class PreviewImage:
    """
    Preview media (image or video) with NSFW flag for blur toggle support.
    
    Supports both images and videos from Civitai and other sources.
    The `media_type` field indicates whether this is an image or video.
    """
    filename: str
    url: Optional[str] = None
    local_path: Optional[str] = None
    nsfw: bool = False
    width: Optional[int] = None
    height: Optional[int] = None
    
    # Media type: 'image', 'video', or 'unknown'
    # Default is 'image' for backward compatibility
    media_type: Literal['image', 'video', 'unknown'] = 'image'
    
    # Video-specific fields
    duration: Optional[float] = None  # Duration in seconds
    has_audio: Optional[bool] = None  # Whether video has audio track
    thumbnail_url: Optional[str] = None  # Thumbnail/poster image URL for video
    
    # Generation metadata (raw dictionary from Civitai)
    meta: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "filename": self.filename,
            "nsfw": self.nsfw,
            "media_type": self.media_type,
        }
        if self.url:
            result["url"] = self.url
        if self.local_path:
            result["local_path"] = self.local_path
        if self.width:
            result["width"] = self.width
        if self.height:
            result["height"] = self.height
            
        # Video fields
        if self.duration is not None:
            result["duration"] = self.duration
        if self.has_audio is not None:
            result["has_audio"] = self.has_audio
        if self.thumbnail_url:
            result["thumbnail_url"] = self.thumbnail_url
            
        # Metadata
        if self.meta:
            result["meta"] = self.meta
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PreviewImage':
        return cls(
            filename=data["filename"],
            url=data.get("url"),
            local_path=data.get("local_path"),
            nsfw=data.get("nsfw", False),
            width=data.get("width"),
            height=data.get("height"),
            media_type=data.get("media_type", "image"),
            duration=data.get("duration"),
            has_audio=data.get("has_audio"),
            thumbnail_url=data.get("thumbnail_url"),
            meta=data.get("meta"),
        )
    
    @property
    def is_video(self) -> bool:
        """Check if this preview is a video."""
        return self.media_type == 'video'
    
    @property  
    def is_image(self) -> bool:
        """Check if this preview is an image."""
        return self.media_type == 'image'


@dataclass
class WorkflowInfo:
    """Information about an included workflow."""
    name: str
    filename: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    is_default: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "filename": self.filename,
            "is_default": self.is_default,
        }
        if self.description:
            result["description"] = self.description
        if self.source_url:
            result["source_url"] = self.source_url
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowInfo':
        return cls(
            name=data["name"],
            filename=data["filename"],
            description=data.get("description"),
            source_url=data.get("source_url"),
            is_default=data.get("is_default", False),
        )


@dataclass
class GenerationParameters:
    """
    Default generation parameters extracted from Civitai or user-defined.

    All fields are Optional to avoid "ghost" values in JSON serialization.
    Use to_dict() which excludes None values.
    """
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    clip_skip: Optional[int] = None
    denoise: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    seed: Optional[int] = None
    # HiRes parameters - all Optional to avoid ghost values
    hires_fix: Optional[bool] = None
    hires_upscaler: Optional[str] = None
    hires_steps: Optional[int] = None
    hires_denoise: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding None values."""
        result = {}
        if self.sampler is not None:
            result["sampler"] = self.sampler
        if self.scheduler is not None:
            result["scheduler"] = self.scheduler
        if self.steps is not None:
            result["steps"] = self.steps
        if self.cfg_scale is not None:
            result["cfg_scale"] = self.cfg_scale
        if self.clip_skip is not None:
            result["clip_skip"] = self.clip_skip
        if self.denoise is not None:
            result["denoise"] = self.denoise
        if self.width is not None:
            result["width"] = self.width
        if self.height is not None:
            result["height"] = self.height
        if self.seed is not None:
            result["seed"] = self.seed
        if self.hires_fix is not None:
            result["hires_fix"] = self.hires_fix
        if self.hires_upscaler is not None:
            result["hires_upscaler"] = self.hires_upscaler
        if self.hires_steps is not None:
            result["hires_steps"] = self.hires_steps
        if self.hires_denoise is not None:
            result["hires_denoise"] = self.hires_denoise
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenerationParameters':
        return cls(
            sampler=data.get("sampler"),
            scheduler=data.get("scheduler"),
            steps=data.get("steps"),
            cfg_scale=data.get("cfg_scale"),
            clip_skip=data.get("clip_skip"),
            denoise=data.get("denoise"),
            width=data.get("width"),
            height=data.get("height"),
            seed=data.get("seed"),
            hires_fix=data.get("hires_fix"),  # None if not present
            hires_upscaler=data.get("hires_upscaler"),
            hires_steps=data.get("hires_steps"),
            hires_denoise=data.get("hires_denoise"),
        )


@dataclass
class ModelInfo:
    """Extended model information table (like Civitai details panel)."""
    model_type: Optional[str] = None
    base_model: Optional[str] = None
    trigger_words: List[str] = field(default_factory=list)
    trained_words: List[str] = field(default_factory=list)
    usage_tips: Optional[str] = None
    hash_autov2: Optional[str] = None
    hash_sha256: Optional[str] = None
    civitai_air: Optional[str] = None
    download_count: Optional[int] = None
    rating: Optional[float] = None
    published_at: Optional[str] = None
    strength_recommended: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.model_type:
            result["model_type"] = self.model_type
        if self.base_model:
            result["base_model"] = self.base_model
        if self.trigger_words:
            result["trigger_words"] = self.trigger_words
        if self.trained_words:
            result["trained_words"] = self.trained_words
        if self.usage_tips:
            result["usage_tips"] = self.usage_tips
        if self.hash_autov2:
            result["hash_autov2"] = self.hash_autov2
        if self.hash_sha256:
            result["hash_sha256"] = self.hash_sha256
        if self.civitai_air:
            result["civitai_air"] = self.civitai_air
        if self.download_count:
            result["download_count"] = self.download_count
        if self.rating:
            result["rating"] = self.rating
        if self.published_at:
            result["published_at"] = self.published_at
        if self.strength_recommended is not None:
            result["strength_recommended"] = self.strength_recommended
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelInfo':
        return cls(
            model_type=data.get("model_type"),
            base_model=data.get("base_model"),
            trigger_words=data.get("trigger_words", []),
            trained_words=data.get("trained_words", []),
            usage_tips=data.get("usage_tips"),
            hash_autov2=data.get("hash_autov2"),
            hash_sha256=data.get("hash_sha256"),
            civitai_air=data.get("civitai_air"),
            download_count=data.get("download_count"),
            rating=data.get("rating"),
            published_at=data.get("published_at"),
            strength_recommended=data.get("strength_recommended"),
        )


@dataclass
class PackMetadata:
    """Metadata about a pack for display and organization."""
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    user_tags: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    source_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "version": self.version,
        }
        if self.description:
            result["description"] = self.description
        if self.author:
            result["author"] = self.author
        if self.tags:
            result["tags"] = self.tags
        if self.user_tags:
            result["user_tags"] = self.user_tags
        if self.created_at:
            result["created_at"] = self.created_at
        if self.updated_at:
            result["updated_at"] = self.updated_at
        if self.source_url:
            result["source_url"] = self.source_url
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PackMetadata':
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description"),
            author=data.get("author"),
            tags=data.get("tags", []),
            user_tags=data.get("user_tags", []),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            source_url=data.get("source_url"),
        )


@dataclass
class Pack:
    """
    Main Pack structure - the central concept in Synapse.
    """
    metadata: PackMetadata
    dependencies: List[AssetDependency] = field(default_factory=list)
    custom_nodes: List[CustomNodeDependency] = field(default_factory=list)
    workflows: List[WorkflowInfo] = field(default_factory=list)
    previews: List[PreviewImage] = field(default_factory=list)
    docs: Dict[str, str] = field(default_factory=dict)
    parameters: Optional[GenerationParameters] = None
    model_info: Optional[ModelInfo] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "metadata": self.metadata.to_dict(),
            "dependencies": [d.to_dict() for d in self.dependencies],
            "custom_nodes": [n.to_dict() for n in self.custom_nodes],
            "workflows": [w.to_dict() for w in self.workflows],
            "previews": [p.to_dict() for p in self.previews],
            "docs": self.docs,
        }
        if self.parameters:
            params_dict = self.parameters.to_dict()
            if params_dict:  # Only include if not empty
                result["parameters"] = params_dict
        if self.model_info:
            result["model_info"] = self.model_info.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Pack':
        return cls(
            metadata=PackMetadata.from_dict(data["metadata"]),
            dependencies=[AssetDependency.from_dict(d) for d in data.get("dependencies", [])],
            custom_nodes=[CustomNodeDependency.from_dict(n) for n in data.get("custom_nodes", [])],
            workflows=[WorkflowInfo.from_dict(w) for w in data.get("workflows", [])],
            previews=[PreviewImage.from_dict(p) for p in data.get("previews", [])],
            docs=data.get("docs", {}),
            parameters=GenerationParameters.from_dict(data["parameters"]) if "parameters" in data else None,
            model_info=ModelInfo.from_dict(data["model_info"]) if "model_info" in data else None,
        )
    
    def save(self, path: Path) -> None:
        """Save pack to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: Path) -> 'Pack':
        """Load pack from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def get_base_model_dependency(self) -> Optional[AssetDependency]:
        """Get the base model dependency if exists."""
        for dep in self.dependencies:
            if dep.asset_type == AssetType.BASE_MODEL:
                return dep
        return None
    
    def has_unresolved_dependencies(self) -> bool:
        """Check if pack has unresolved dependencies."""
        for dep in self.dependencies:
            if dep.status == DependencyStatus.UNRESOLVED:
                return True
        return False


@dataclass
class LockedAsset:
    """Represents a locked (installed) asset with verification info."""
    name: str
    asset_type: AssetType
    local_path: str
    hash: Optional[AssetHash] = None
    installed_at: Optional[str] = None
    verified: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "asset_type": self.asset_type.value,
            "local_path": self.local_path,
            "verified": self.verified,
        }
        if self.hash:
            result["hash"] = self.hash.to_dict()
        if self.installed_at:
            result["installed_at"] = self.installed_at
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LockedAsset':
        return cls(
            name=data["name"],
            asset_type=AssetType(data["asset_type"]),
            local_path=data["local_path"],
            hash=AssetHash.from_dict(data["hash"]) if "hash" in data else None,
            installed_at=data.get("installed_at"),
            verified=data.get("verified", False),
        )


@dataclass
class PackLock:
    """Lock file tracking installed state of a pack."""
    pack_name: str
    pack_version: str
    locked_assets: List[LockedAsset] = field(default_factory=list)
    locked_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_name": self.pack_name,
            "pack_version": self.pack_version,
            "locked_assets": [a.to_dict() for a in self.locked_assets],
            "locked_at": self.locked_at or datetime.now().isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PackLock':
        return cls(
            pack_name=data["pack_name"],
            pack_version=data["pack_version"],
            locked_assets=[LockedAsset.from_dict(a) for a in data.get("locked_assets", [])],
            locked_at=data.get("locked_at"),
        )
    
    def save(self, path: Path) -> None:
        """Save lock file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: Path) -> 'PackLock':
        """Load lock file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class RunConfig:
    """Runtime configuration for a pack execution."""
    pack_name: str
    output_prefix: str = "synapse"
    output_subfolder: Optional[str] = None
    parameter_overrides: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_name": self.pack_name,
            "output_prefix": self.output_prefix,
            "output_subfolder": self.output_subfolder,
            "parameter_overrides": self.parameter_overrides,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunConfig':
        return cls(
            pack_name=data["pack_name"],
            output_prefix=data.get("output_prefix", "synapse"),
            output_subfolder=data.get("output_subfolder"),
            parameter_overrides=data.get("parameter_overrides", {}),
        )
    
    def save(self, path: Path) -> None:
        """Save run config."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: Path) -> 'RunConfig':
        """Load run config."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


# Mapping of asset types to ComfyUI folder names
ASSET_TYPE_FOLDERS = {
    AssetType.CHECKPOINT: "checkpoints",
    AssetType.LORA: "loras",
    AssetType.VAE: "vae",
    AssetType.CONTROLNET: "controlnet",
    AssetType.UPSCALER: "upscale_models",
    AssetType.CLIP: "clip",
    AssetType.TEXT_ENCODER: "text_encoders",
    AssetType.DIFFUSION_MODEL: "diffusion_models",
    AssetType.EMBEDDING: "embeddings",
    AssetType.BASE_MODEL: "checkpoints",
}


def get_asset_folder(asset_type: AssetType) -> str:
    """Get the ComfyUI folder name for an asset type."""
    return ASSET_TYPE_FOLDERS.get(asset_type, "unknown")
