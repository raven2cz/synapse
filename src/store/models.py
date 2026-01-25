"""
Synapse Store v2 - Data Models

Pydantic v2 models for pack.json, lock.json, config.json, profile.json, runtime.json.
All models are designed to be JSON-serializable and validated.

Schema versions:
- synapse.config.v2
- synapse.ui_sets.v1
- synapse.pack.v2
- synapse.lock.v2
- synapse.profile.v1
- synapse.runtime.v1
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# =============================================================================
# Enums
# =============================================================================

class AssetKind(str, Enum):
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
    UNET = "unet"
    UNKNOWN = "unknown"


class ProviderName(str, Enum):
    """Supported asset providers."""
    CIVITAI = "civitai"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    URL = "url"


class SelectorStrategy(str, Enum):
    """Selector strategies for resolving dependencies."""
    CIVITAI_FILE = "civitai_file"
    CIVITAI_MODEL_LATEST = "civitai_model_latest"
    HUGGINGFACE_FILE = "huggingface_file"
    BASE_MODEL_HINT = "base_model_hint"
    LOCAL_FILE = "local_file"
    URL_DOWNLOAD = "url_download"


class UpdatePolicyMode(str, Enum):
    """Update policy modes for dependencies."""
    PINNED = "pinned"
    FOLLOW_LATEST = "follow_latest"


class ConflictMode(str, Enum):
    """Conflict resolution modes."""
    LAST_WINS = "last_wins"
    FIRST_WINS = "first_wins"
    STRICT = "strict"


# =============================================================================
# Validators
# =============================================================================

def validate_safe_name(name: str) -> str:
    """Validate name doesn't contain path traversal or dangerous chars."""
    if not name:
        raise ValueError("Name cannot be empty")
    if "/" in name or "\\" in name:
        raise ValueError("Name cannot contain path separators")
    if ".." in name:
        raise ValueError("Name cannot contain path traversal")
    if "\x00" in name:
        raise ValueError("Name cannot contain null bytes")
    return name


def validate_safe_filename(filename: str) -> str:
    """Validate filename is safe for filesystem."""
    validate_safe_name(filename)
    # Additional filename-specific checks
    if filename.startswith("."):
        raise ValueError("Filename cannot start with dot")
    return filename


# =============================================================================
# Config Models (state/config.json)
# =============================================================================

class UIKindMap(BaseModel):
    """Mapping of asset kinds to UI-specific folder paths."""
    checkpoint: str = "models/checkpoints"
    lora: str = "models/loras"
    vae: str = "models/vae"
    embedding: str = "models/embeddings"
    controlnet: str = "models/controlnet"
    upscaler: str = "models/upscale_models"
    clip: str = "models/clip"
    text_encoder: str = "models/text_encoders"
    diffusion_model: str = "models/diffusion_models"
    unet: str = "models/unet"
    
    def get_path(self, kind: AssetKind) -> Optional[str]:
        """Get folder path for asset kind."""
        return getattr(self, kind.value, None)


class UIConfig(BaseModel):
    """UI configuration section."""
    known: List[str] = Field(default_factory=lambda: ["comfyui", "forge", "a1111", "sdnext"])
    kind_map: Dict[str, UIKindMap] = Field(default_factory=dict)
    
    @classmethod
    def get_default_kind_maps(cls) -> Dict[str, UIKindMap]:
        """Get default kind maps for all known UIs."""
        return {
            "comfyui": UIKindMap(
                checkpoint="models/checkpoints",
                lora="models/loras",
                vae="models/vae",
                embedding="models/embeddings",
                controlnet="models/controlnet",
                upscaler="models/upscale_models",
                clip="models/clip",
                text_encoder="models/text_encoders",
                diffusion_model="models/diffusion_models",
                unet="models/unet",
            ),
            "forge": UIKindMap(
                checkpoint="models/Stable-diffusion",
                lora="models/Lora",
                vae="models/VAE",
                embedding="embeddings",
                controlnet="models/ControlNet",
                upscaler="models/ESRGAN",
                clip="models/CLIP",
                text_encoder="models/text_encoder",
                diffusion_model="models/diffusion_models",
                unet="models/unet",
            ),
            "a1111": UIKindMap(
                checkpoint="models/Stable-diffusion",
                lora="models/Lora",
                vae="models/VAE",
                embedding="embeddings",
                controlnet="models/ControlNet",
                upscaler="models/ESRGAN",
                clip="models/CLIP",
                text_encoder="models/text_encoder",
                diffusion_model="models/diffusion_models",
                unet="models/unet",
            ),
            "sdnext": UIKindMap(
                checkpoint="models/Stable-diffusion",
                lora="models/Lora",
                vae="models/VAE",
                embedding="embeddings",
                controlnet="models/ControlNet",
                upscaler="models/ESRGAN",
                clip="models/CLIP",
                text_encoder="models/text_encoder",
                diffusion_model="models/diffusion_models",
                unet="models/unet",
            ),
        }


class ProviderConfig(BaseModel):
    """Provider-specific configuration."""
    primary_file_only_default: bool = True
    preferred_ext: List[str] = Field(default_factory=lambda: [".safetensors"])


class CivitaiSelectorConfig(BaseModel):
    """Civitai selector for base model alias."""
    model_config = ConfigDict(protected_namespaces=())
    
    model_id: int
    version_id: int
    file_id: int


class BaseModelAliasSelector(BaseModel):
    """Selector configuration for base model alias."""
    strategy: SelectorStrategy = SelectorStrategy.CIVITAI_FILE
    civitai: Optional[CivitaiSelectorConfig] = None


class BaseModelAlias(BaseModel):
    """Base model alias definition."""
    kind: AssetKind = AssetKind.CHECKPOINT
    default_expose_filename: str
    selector: BaseModelAliasSelector


class ConfigDefaults(BaseModel):
    """Default configuration values."""
    ui_set: str = "local"
    conflicts_mode: ConflictMode = ConflictMode.LAST_WINS
    active_profile: str = "global"
    use_base: str = "global"


class BackupConfig(BaseModel):
    """Configuration for backup storage."""
    enabled: bool = False
    path: Optional[str] = None  # e.g., "/mnt/external/synapse-backup" or "D:\\SynapseBackup"
    auto_backup_new: bool = False  # Automatically backup new blobs
    warn_before_delete_last_copy: bool = True  # Warn when deleting last copy


class StoreConfig(BaseModel):
    """Main store configuration (state/config.json)."""
    schema_: str = Field(default="synapse.config.v2", alias="schema")
    defaults: ConfigDefaults = Field(default_factory=ConfigDefaults)
    ui: UIConfig = Field(default_factory=UIConfig)
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)
    base_model_aliases: Dict[str, BaseModelAlias] = Field(default_factory=dict)
    backup: BackupConfig = Field(default_factory=BackupConfig)

    model_config = {"populate_by_name": True}
    
    @classmethod
    def create_default(cls) -> "StoreConfig":
        """Create default configuration with all defaults populated."""
        config = cls()
        config.ui.kind_map = UIConfig.get_default_kind_maps()
        config.providers = {
            "civitai": ProviderConfig(),
            "huggingface": ProviderConfig(
                primary_file_only_default=False,
                preferred_ext=[".safetensors", ".bin", ".gguf"]
            ),
        }
        # Default base model aliases for common models
        config.base_model_aliases = cls._get_default_base_model_aliases()
        return config
    
    @staticmethod
    def _get_default_base_model_aliases() -> Dict[str, BaseModelAlias]:
        """Get default base model aliases for well-known models."""
        return {
            # These are placeholder values - real IDs should be filled in
            "SD1.5": BaseModelAlias(
                kind=AssetKind.CHECKPOINT,
                default_expose_filename="v1-5-pruned-emaonly.safetensors",
                selector=BaseModelAliasSelector(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
                )
            ),
            "SDXL": BaseModelAlias(
                kind=AssetKind.CHECKPOINT,
                default_expose_filename="sd_xl_base_1.0.safetensors",
                selector=BaseModelAliasSelector(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
                )
            ),
            "Illustrious": BaseModelAlias(
                kind=AssetKind.CHECKPOINT,
                default_expose_filename="illustrious_v1.safetensors",
                selector=BaseModelAliasSelector(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
                )
            ),
            "Pony": BaseModelAlias(
                kind=AssetKind.CHECKPOINT,
                default_expose_filename="ponyDiffusionV6XL.safetensors",
                selector=BaseModelAliasSelector(
                    strategy=SelectorStrategy.CIVITAI_FILE,
                    civitai=CivitaiSelectorConfig(model_id=0, version_id=0, file_id=0)
                )
            ),
        }


# =============================================================================
# UI Sets Model (state/ui_sets.json)
# =============================================================================

class UISets(BaseModel):
    """UI sets configuration (state/ui_sets.json)."""
    schema_: str = Field(default="synapse.ui_sets.v1", alias="schema")
    sets: Dict[str, List[str]] = Field(default_factory=dict)
    
    model_config = {"populate_by_name": True}
    
    @classmethod
    def create_default(cls) -> "UISets":
        """
        Create default UI sets.
        
        Includes:
        - Named sets (local, all)
        - Implicit singleton sets for each UI (comfyui, forge, a1111, sdnext)
          This allows UI to send ui_set="comfyui" and it works.
        """
        return cls(
            sets={
                # Named sets
                "local": ["comfyui", "forge"],
                "comfy_only": ["comfyui"],
                "all": ["comfyui", "forge", "a1111", "sdnext"],
                # Implicit singleton sets - each UI can be targeted directly
                "comfyui": ["comfyui"],
                "forge": ["forge"],
                "a1111": ["a1111"],
                "sdnext": ["sdnext"],
            }
        )


# =============================================================================
# Pack Models (state/packs/<Pack>/pack.json)
# =============================================================================

class CivitaiSelector(BaseModel):
    """Civitai-specific selector data."""
    model_config = ConfigDict(protected_namespaces=())
    
    model_id: int
    version_id: Optional[int] = None
    file_id: Optional[int] = None


class HuggingFaceSelector(BaseModel):
    """HuggingFace-specific selector data."""
    repo_id: str
    filename: str
    revision: Optional[str] = None
    subfolder: Optional[str] = None


class SelectorConstraints(BaseModel):
    """Constraints for file selection."""
    primary_file_only: bool = True
    file_ext: List[str] = Field(default_factory=lambda: [".safetensors"])
    base_model_hint: Optional[str] = None


class DependencySelector(BaseModel):
    """Selector for resolving a dependency."""
    strategy: SelectorStrategy
    civitai: Optional[CivitaiSelector] = None
    huggingface: Optional[HuggingFaceSelector] = None
    base_model: Optional[str] = None  # For base_model_hint strategy
    url: Optional[str] = None  # For url_download strategy
    local_path: Optional[str] = None  # For local_file strategy
    constraints: Optional[SelectorConstraints] = None


class UpdatePolicy(BaseModel):
    """Update policy for a dependency."""
    mode: UpdatePolicyMode = UpdatePolicyMode.PINNED
    
    @classmethod
    def from_string(cls, value: str) -> "UpdatePolicy":
        """Create UpdatePolicy from string shorthand."""
        return cls(mode=UpdatePolicyMode(value))


class ExposeConfig(BaseModel):
    """Configuration for how an asset is exposed to UI."""
    filename: str
    trigger_words: List[str] = Field(default_factory=list)
    
    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        return validate_safe_filename(v)


class PackDependency(BaseModel):
    """A single dependency within a pack."""
    id: str
    kind: AssetKind
    required: bool = True
    selector: DependencySelector
    update_policy: UpdatePolicy = Field(default_factory=UpdatePolicy)
    expose: ExposeConfig
    description: Optional[str] = None  # Optional description for the dependency
    
    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return validate_safe_name(v)


class PackSource(BaseModel):
    """Source information for a pack."""
    model_config = ConfigDict(protected_namespaces=())
    
    provider: ProviderName
    model_id: Optional[int] = None
    version_id: Optional[int] = None
    url: Optional[str] = None


class PackResources(BaseModel):
    """Resource configuration for a pack."""
    previews_keep_in_git: bool = True
    workflows_keep_in_git: bool = True


class GenerationParameters(BaseModel):
    """Default generation parameters extracted from Civitai or user-defined."""
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    clip_skip: Optional[int] = None
    denoise: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    seed: Optional[int] = None
    hires_fix: bool = False
    hires_upscaler: Optional[str] = None
    hires_steps: Optional[int] = None
    hires_denoise: Optional[float] = None


class ModelInfo(BaseModel):
    """Extended model information table (like Civitai details panel)."""
    model_config = ConfigDict(protected_namespaces=())
    
    model_type: Optional[str] = None
    base_model: Optional[str] = None
    trigger_words: List[str] = Field(default_factory=list)
    trained_words: List[str] = Field(default_factory=list)
    usage_tips: Optional[str] = None
    hash_autov2: Optional[str] = None
    hash_sha256: Optional[str] = None
    civitai_air: Optional[str] = None
    download_count: Optional[int] = None
    rating: Optional[float] = None
    published_at: Optional[str] = None
    strength_recommended: Optional[float] = None


class WorkflowInfo(BaseModel):
    """Information about an included ComfyUI workflow."""
    name: str
    filename: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    is_default: bool = False


class PreviewInfo(BaseModel):
    """
    Preview media information (image or video).
    
    Supports both images and videos from Civitai and other sources.
    The `media_type` field indicates whether this is an image or video.
    """
    filename: str
    url: Optional[str] = None
    nsfw: bool = False
    width: Optional[int] = None
    height: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None
    
    # Media type: 'image', 'video', or 'unknown'
    # Default is 'image' for backward compatibility
    media_type: Literal['image', 'video', 'unknown'] = 'image'
    
    # Video-specific fields
    duration: Optional[float] = None  # Duration in seconds
    has_audio: Optional[bool] = None  # Whether video has audio track
    thumbnail_url: Optional[str] = None  # Thumbnail/poster image URL for video
    
    @property
    def is_video(self) -> bool:
        """Check if this preview is a video."""
        return self.media_type == 'video'
    
    @property
    def is_image(self) -> bool:
        """Check if this preview is an image."""
        return self.media_type == 'image'


class Pack(BaseModel):
    """Main pack structure (state/packs/<Pack>/pack.json)."""
    schema_: str = Field(default="synapse.pack.v2", alias="schema")
    name: str
    pack_type: AssetKind
    source: PackSource
    dependencies: List[PackDependency] = Field(default_factory=list)
    resources: PackResources = Field(default_factory=PackResources)

    # Previews with metadata (canonical source of truth)
    previews: List[PreviewInfo] = Field(default_factory=list)

    # Cover/thumbnail URL - user-selected preview to show as pack cover
    # If not set, falls back to first preview
    cover_url: Optional[str] = None

    # Optional metadata fields
    version: Optional[str] = None
    description: Optional[str] = None
    base_model: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    user_tags: List[str] = Field(default_factory=list)
    trigger_words: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    
    # NSFW flags - managed via user_tags for UI compatibility
    # nsfw-pack: blur previews in list
    # nsfw-pack-hide: completely hide pack when NSFW mode disabled
    
    # Generation parameters and model info
    parameters: Optional[GenerationParameters] = None
    model_info: Optional[ModelInfo] = None
    
    # ComfyUI workflows
    workflows: List[WorkflowInfo] = Field(default_factory=list)
    
    model_config = {"populate_by_name": True}
    
    @property
    def is_nsfw(self) -> bool:
        """Check if pack is marked NSFW (blur previews)."""
        return "nsfw-pack" in self.user_tags
    
    @property
    def is_nsfw_hidden(self) -> bool:
        """Check if pack should be completely hidden when NSFW disabled."""
        return "nsfw-pack-hide" in self.user_tags
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_safe_name(v)
    
    @model_validator(mode="after")
    def validate_unique_dep_ids(self) -> "Pack":
        """Ensure all dependency IDs are unique."""
        ids = [dep.id for dep in self.dependencies]
        if len(ids) != len(set(ids)):
            raise ValueError("Dependency IDs must be unique within a pack")
        return self
    
    def get_dependency(self, dep_id: str) -> Optional[PackDependency]:
        """Get dependency by ID."""
        for dep in self.dependencies:
            if dep.id == dep_id:
                return dep
        return None


# =============================================================================
# Lock Models (state/packs/<Pack>/lock.json)
# =============================================================================

class ArtifactProvider(BaseModel):
    """Provider information for a resolved artifact."""
    model_config = ConfigDict(protected_namespaces=())
    
    name: ProviderName
    model_id: Optional[int] = None
    version_id: Optional[int] = None
    file_id: Optional[int] = None
    repo_id: Optional[str] = None
    filename: Optional[str] = None
    revision: Optional[str] = None


class ArtifactDownload(BaseModel):
    """Download information for an artifact."""
    urls: List[str] = Field(default_factory=list)


class ArtifactIntegrity(BaseModel):
    """Integrity information for an artifact."""
    sha256_verified: bool = False


class ResolvedArtifact(BaseModel):
    """A resolved artifact in the lock file."""
    kind: AssetKind
    sha256: Optional[str] = None
    size_bytes: Optional[int] = None
    provider: ArtifactProvider
    download: ArtifactDownload = Field(default_factory=ArtifactDownload)
    integrity: ArtifactIntegrity = Field(default_factory=ArtifactIntegrity)


# Backwards compatibility aliases for API
Artifact = ResolvedArtifact
DownloadInfo = ArtifactDownload
IntegrityInfo = ArtifactIntegrity


class ResolvedDependency(BaseModel):
    """A resolved dependency entry in the lock file."""
    dependency_id: str
    artifact: ResolvedArtifact


class UnresolvedDependency(BaseModel):
    """An unresolved dependency entry in the lock file."""
    dependency_id: str
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)


class PackLock(BaseModel):
    """Lock file structure (state/packs/<Pack>/lock.json)."""
    schema_: str = Field(default="synapse.lock.v2", alias="schema")
    pack: str
    resolved_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    resolved: List[ResolvedDependency] = Field(default_factory=list)
    unresolved: List[UnresolvedDependency] = Field(default_factory=list)
    
    model_config = {"populate_by_name": True}
    
    def get_resolved(self, dep_id: str) -> Optional[ResolvedDependency]:
        """Get resolved dependency by ID."""
        for r in self.resolved:
            if r.dependency_id == dep_id:
                return r
        return None
    
    def is_fully_resolved(self) -> bool:
        """Check if all dependencies are resolved."""
        return len(self.unresolved) == 0


# =============================================================================
# Profile Models (state/profiles/<name>/profile.json)
# =============================================================================

class ProfilePackEntry(BaseModel):
    """A pack entry in a profile."""
    name: str
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_safe_name(v)


class ConflictConfig(BaseModel):
    """Conflict resolution configuration."""
    mode: ConflictMode = ConflictMode.LAST_WINS


class Profile(BaseModel):
    """Profile structure (state/profiles/<name>/profile.json)."""
    schema_: str = Field(default="synapse.profile.v1", alias="schema")
    name: str
    conflicts: ConflictConfig = Field(default_factory=ConflictConfig)
    packs: List[ProfilePackEntry] = Field(default_factory=list)
    
    model_config = {"populate_by_name": True}
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_safe_name(v)
    
    def add_pack(self, pack_name: str, move_to_end: bool = True) -> None:
        """Add a pack to the profile. If move_to_end is True, moves existing pack to end."""
        # Remove if exists
        self.packs = [p for p in self.packs if p.name != pack_name]
        # Add at end
        self.packs.append(ProfilePackEntry(name=pack_name))
    
    def remove_pack(self, pack_name: str) -> bool:
        """Remove a pack from the profile. Returns True if removed."""
        original_len = len(self.packs)
        self.packs = [p for p in self.packs if p.name != pack_name]
        return len(self.packs) < original_len
    
    def get_pack_names(self) -> List[str]:
        """Get list of pack names in order."""
        return [p.name for p in self.packs]


# =============================================================================
# Runtime Models (data/runtime.json)
# =============================================================================

class UIRuntimeState(BaseModel):
    """Runtime state for a single UI."""
    stack: List[str] = Field(default_factory=lambda: ["global"])


class Runtime(BaseModel):
    """Runtime state (data/runtime.json)."""
    schema_: str = Field(default="synapse.runtime.v1", alias="schema")
    ui: Dict[str, UIRuntimeState] = Field(default_factory=dict)
    
    model_config = {"populate_by_name": True}
    
    def get_active_profile(self, ui_name: str) -> str:
        """Get the active profile for a UI (top of stack)."""
        if ui_name in self.ui and self.ui[ui_name].stack:
            return self.ui[ui_name].stack[-1]
        return "global"
    
    def get_stack(self, ui_name: str) -> List[str]:
        """Get the stack for a UI."""
        if ui_name in self.ui:
            return self.ui[ui_name].stack.copy()
        return ["global"]
    
    def push_profile(self, ui_name: str, profile_name: str) -> None:
        """Push a profile onto the stack for a UI."""
        if ui_name not in self.ui:
            self.ui[ui_name] = UIRuntimeState()
        self.ui[ui_name].stack.append(profile_name)
    
    def pop_profile(self, ui_name: str) -> Optional[str]:
        """Pop and return the top profile from the stack. Returns None if at base."""
        if ui_name not in self.ui:
            return None
        stack = self.ui[ui_name].stack
        if len(stack) <= 1:
            return None  # Can't pop global
        return stack.pop()
    
    def set_stack(self, ui_name: str, stack: List[str]) -> None:
        """Set the entire stack for a UI (used for reset operations)."""
        if ui_name not in self.ui:
            self.ui[ui_name] = UIRuntimeState()
        self.ui[ui_name].stack = stack
    
    @classmethod
    def create_default(cls, ui_names: List[str]) -> "Runtime":
        """Create default runtime with global profile for all UIs."""
        return cls(
            ui={name: UIRuntimeState(stack=["global"]) for name in ui_names}
        )


# =============================================================================
# Report Models (for CLI/API responses)
# =============================================================================

class MissingBlob(BaseModel):
    """Report entry for a missing blob."""
    pack: str
    dependency_id: str
    kind: AssetKind
    sha256: str


class UnresolvedReport(BaseModel):
    """Report entry for an unresolved dependency."""
    pack: str
    dependency_id: str
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ShadowedEntry(BaseModel):
    """Report entry for a shadowed file (conflict resolved by last_wins)."""
    ui: str
    dst_relpath: str
    winner_pack: str
    loser_pack: str


class StatusReport(BaseModel):
    """Status report structure."""
    profile: str
    ui_targets: List[str]
    active: Dict[str, str]
    missing_blobs: List[MissingBlob] = Field(default_factory=list)
    unresolved: List[UnresolvedReport] = Field(default_factory=list)
    shadowed: List[ShadowedEntry] = Field(default_factory=list)


class UpdateChange(BaseModel):
    """A single change in an update plan."""
    dependency_id: str
    old: Dict[str, Any]
    new: Dict[str, Any]


class UpdateCandidate(BaseModel):
    """A candidate for ambiguous update selection."""
    model_config = ConfigDict(protected_namespaces=())
    
    provider: str
    provider_model_id: Optional[int] = None
    provider_version_id: Optional[int] = None
    provider_file_id: Optional[int] = None
    sha256: Optional[str] = None


class AmbiguousUpdate(BaseModel):
    """Ambiguous update requiring selection."""
    dependency_id: str
    candidates: List[UpdateCandidate]


class UpdatePlan(BaseModel):
    """Update plan structure."""
    pack: str
    already_up_to_date: bool = False
    changes: List[UpdateChange] = Field(default_factory=list)
    ambiguous: List[AmbiguousUpdate] = Field(default_factory=list)


class UpdateResult(BaseModel):
    """Result of applying an update."""
    pack: str
    applied: bool
    lock_updated: bool
    synced: bool
    ui_targets: List[str] = Field(default_factory=list)
    already_up_to_date: bool = False


class DoctorActions(BaseModel):
    """Actions taken by doctor."""
    views_rebuilt: bool = False
    db_rebuilt: Optional[str] = None  # "auto", "force", or None
    blobs_verified: bool = False


class DoctorReport(BaseModel):
    """Doctor report structure."""
    profile: str
    ui_targets: List[str]
    actions: DoctorActions
    active: Dict[str, str]
    missing_blobs: List[MissingBlob] = Field(default_factory=list)
    unresolved: List[UnresolvedReport] = Field(default_factory=list)
    shadowed: List[ShadowedEntry] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class SearchResultItem(BaseModel):
    """A single search result item."""
    model_config = ConfigDict(protected_namespaces=())
    
    pack_name: str
    pack_type: str
    provider: Optional[str] = None
    source_model_id: Optional[int] = None
    source_url: Optional[str] = None


class SearchResult(BaseModel):
    """Search result structure."""
    query: str
    used_db: bool
    items: List[SearchResultItem] = Field(default_factory=list)


class UseResult(BaseModel):
    """Result of 'use' command."""
    pack: str
    created_profile: str
    ui_targets: List[str]
    activated_profile: str
    synced: bool
    shadowed: List[ShadowedEntry] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class BackResult(BaseModel):
    """Result of 'back' command."""
    ui_targets: List[str]
    from_profile: str
    to_profile: str
    synced: bool
    notes: List[str] = Field(default_factory=list)


class ResetResult(BaseModel):
    """Result of 'reset' command."""
    ui_targets: List[str]
    from_profiles: Dict[str, str]  # UI -> previous active profile
    to_profile: str  # Always "global"
    synced: bool
    notes: List[str] = Field(default_factory=list)


class DeleteResult(BaseModel):
    """Result of 'delete' command."""
    pack_name: str
    deleted: bool
    cleanup_warnings: List[str] = Field(default_factory=list)
    removed_from_global: bool = False
    removed_work_profile: bool = False
    removed_from_stacks: bool = False


# =============================================================================
# Inventory Models (for Model Inventory feature)
# =============================================================================

class BlobStatus(str, Enum):
    """Status of a blob in the inventory."""
    REFERENCED = "referenced"    # Blob exists locally and is used by at least one pack
    ORPHAN = "orphan"            # Blob exists locally but no pack references it
    MISSING = "missing"          # Pack references blob but it doesn't exist anywhere
    BACKUP_ONLY = "backup_only"  # Blob is only on backup storage (not local)


class BlobLocation(str, Enum):
    """Physical location of a blob."""
    LOCAL_ONLY = "local_only"    # Only on local disk
    BACKUP_ONLY = "backup_only"  # Only on backup storage
    BOTH = "both"                # On both local and backup (synced)
    NOWHERE = "nowhere"          # Missing everywhere


class BlobOrigin(BaseModel):
    """Origin information for a blob - where it came from."""
    model_config = ConfigDict(protected_namespaces=())

    provider: ProviderName
    model_id: Optional[int] = None
    version_id: Optional[int] = None
    file_id: Optional[int] = None
    filename: Optional[str] = None
    repo_id: Optional[str] = None  # For HuggingFace


class PackReference(BaseModel):
    """Reference from a pack to a blob."""
    pack_name: str
    dependency_id: str
    kind: AssetKind
    expose_filename: Optional[str] = None
    size_bytes: Optional[int] = None
    origin: Optional[BlobOrigin] = None


class InventoryItem(BaseModel):
    """A single item in the blob inventory."""
    sha256: str
    kind: AssetKind
    display_name: str  # Priority: expose.filename > origin.filename > sha256[:12]
    size_bytes: int

    # Location tracking
    location: BlobLocation
    on_local: bool
    on_backup: bool

    # Status and usage
    status: BlobStatus
    used_by_packs: List[str] = Field(default_factory=list)  # Pack names
    ref_count: int = 0  # Total reference count (can be > len(used_by_packs))

    # Origin and context
    origin: Optional[BlobOrigin] = None
    active_in_uis: List[str] = Field(default_factory=list)  # UIs currently using this blob

    # Verification status
    verified: Optional[bool] = None  # True/False/None (not verified)


class BackupStats(BaseModel):
    """Statistics about backup storage."""
    enabled: bool = False
    connected: bool = False
    path: Optional[str] = None
    blobs_local_only: int = 0
    blobs_backup_only: int = 0
    blobs_both: int = 0
    bytes_local_only: int = 0
    bytes_backup_only: int = 0
    bytes_synced: int = 0
    total_bytes: int = 0
    free_space: Optional[int] = None
    last_sync: Optional[str] = None


class InventorySummary(BaseModel):
    """Summary statistics for the inventory."""
    blobs_total: int = 0
    blobs_referenced: int = 0
    blobs_orphan: int = 0
    blobs_missing: int = 0
    blobs_backup_only: int = 0
    bytes_total: int = 0
    bytes_referenced: int = 0
    bytes_orphan: int = 0
    bytes_by_kind: Dict[str, int] = Field(default_factory=dict)
    disk_total: Optional[int] = None
    disk_free: Optional[int] = None
    backup: Optional[BackupStats] = None


class InventoryResponse(BaseModel):
    """Response from inventory endpoint."""
    generated_at: str
    summary: InventorySummary
    items: List[InventoryItem] = Field(default_factory=list)


class CleanupResult(BaseModel):
    """Result of a cleanup operation."""
    dry_run: bool
    orphans_found: int = 0
    orphans_deleted: int = 0
    bytes_freed: int = 0
    deleted: List[InventoryItem] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ImpactAnalysis(BaseModel):
    """Analysis of what would break if a blob is deleted."""
    sha256: str
    status: BlobStatus
    size_bytes: int
    used_by_packs: List[str] = Field(default_factory=list)
    active_in_uis: List[str] = Field(default_factory=list)
    can_delete_safely: bool
    warning: Optional[str] = None


# =============================================================================
# Blob Manifest Model (for orphan metadata persistence)
# =============================================================================

class BlobManifest(BaseModel):
    """
    Write-once manifest for blob metadata persistence.

    Created when a blob is first adopted by any pack.
    Immutable after creation - never updated.
    Used as fallback for orphan blob display.
    """
    version: int = 1  # Schema version
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    original_filename: str  # Display name from first pack
    kind: AssetKind  # Asset kind (checkpoint, lora, etc.)
    origin: Optional[BlobOrigin] = None  # Provider info if available


# =============================================================================
# Backup Storage Models
# =============================================================================

class BackupStatus(BaseModel):
    """Status of the backup storage connection."""
    enabled: bool
    connected: bool
    path: Optional[str] = None
    total_blobs: int = 0
    total_bytes: int = 0
    total_space: Optional[int] = None  # Total space on backup drive
    free_space: Optional[int] = None
    last_sync: Optional[str] = None
    error: Optional[str] = None
    # Config options (for UI)
    auto_backup_new: bool = False
    warn_before_delete_last_copy: bool = True


class BackupOperationResult(BaseModel):
    """Result of a backup/restore operation."""
    success: bool
    sha256: str
    bytes_copied: int = 0
    duration_ms: int = 0
    error: Optional[str] = None
    verified: Optional[bool] = None


class BackupDeleteResult(BaseModel):
    """Result of deleting from backup storage."""
    success: bool
    sha256: str
    bytes_freed: int = 0
    still_on_local: bool = False
    error: Optional[str] = None


class SyncItem(BaseModel):
    """An item to be synced."""
    sha256: str
    size_bytes: int
    display_name: Optional[str] = None
    kind: Optional[str] = None  # AssetKind value (checkpoint, lora, vae, etc.)


class SyncResult(BaseModel):
    """Result of a sync operation."""
    dry_run: bool
    direction: str  # "to_backup" or "from_backup"
    blobs_to_sync: int = 0
    bytes_to_sync: int = 0
    blobs_synced: int = 0
    bytes_synced: int = 0
    items: List[SyncItem] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


# =============================================================================
# API Response Wrapper
# =============================================================================

# =============================================================================
# State Sync Models (for state/ directory backup)
# =============================================================================

class StateSyncStatus(str, Enum):
    """Status of a file in state sync."""
    SYNCED = "synced"              # Same on both sides
    LOCAL_ONLY = "local_only"      # Only on local
    BACKUP_ONLY = "backup_only"    # Only on backup
    MODIFIED = "modified"          # Different on local vs backup
    CONFLICT = "conflict"          # Both modified since last sync


class StateSyncItem(BaseModel):
    """A single file in the state sync."""
    relative_path: str  # e.g., "packs/MyPack/pack.json"
    status: StateSyncStatus
    local_mtime: Optional[str] = None
    backup_mtime: Optional[str] = None
    local_size: Optional[int] = None
    backup_size: Optional[int] = None


class StateSyncSummary(BaseModel):
    """Summary of state sync status."""
    total_files: int = 0
    synced: int = 0
    local_only: int = 0
    backup_only: int = 0
    modified: int = 0
    conflicts: int = 0
    last_sync: Optional[str] = None


class StateSyncResult(BaseModel):
    """Result of a state sync operation."""
    dry_run: bool
    direction: str  # "to_backup", "from_backup", "bidirectional"
    summary: StateSyncSummary
    items: List[StateSyncItem] = Field(default_factory=list)
    synced_files: int = 0
    errors: List[str] = Field(default_factory=list)


# =============================================================================
# API Response Wrapper
# =============================================================================

class APIResponse(BaseModel):
    """Standard API response wrapper."""
    ok: bool
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def success(cls, result: Any) -> "APIResponse":
        return cls(ok=True, result=result)

    @classmethod
    def failure(cls, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> "APIResponse":
        return cls(ok=False, error={"code": code, "message": message, "details": details or {}})
