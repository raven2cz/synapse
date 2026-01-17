"""
Synapse Configuration Module

Central configuration for all Synapse components including paths,
API settings, and user preferences.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class ComfyUIConfig:
    """ComfyUI installation paths configuration."""
    base_path: Path = field(default_factory=lambda: Path.home() / "ComfyUI")
    
    @property
    def models_path(self) -> Path:
        return self.base_path / "models"
    
    @property
    def checkpoints_path(self) -> Path:
        return self.models_path / "checkpoints"
    
    @property
    def loras_path(self) -> Path:
        return self.models_path / "loras"
    
    @property
    def vae_path(self) -> Path:
        return self.models_path / "vae"
    
    @property
    def controlnet_path(self) -> Path:
        return self.models_path / "controlnet"
    
    @property
    def upscale_models_path(self) -> Path:
        return self.models_path / "upscale_models"
    
    @property
    def clip_path(self) -> Path:
        return self.models_path / "clip"
    
    @property
    def text_encoders_path(self) -> Path:
        return self.models_path / "text_encoders"
    
    @property
    def diffusion_models_path(self) -> Path:
        return self.models_path / "diffusion_models"
    
    @property
    def embeddings_path(self) -> Path:
        return self.models_path / "embeddings"
    
    @property
    def custom_nodes_path(self) -> Path:
        return self.base_path / "custom_nodes"
    
    @property
    def output_path(self) -> Path:
        return self.base_path / "output"
    
    @property
    def input_path(self) -> Path:
        return self.base_path / "input"


@dataclass
class APIConfig:
    """API configuration for external services."""
    civitai_token: Optional[str] = field(
        default_factory=lambda: os.environ.get("CIVITAI_API_TOKEN") or os.environ.get("CIVITAI_API_KEY")
    )
    huggingface_token: Optional[str] = field(
        default_factory=lambda: os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    )
    civitai_base_url: str = "https://civitai.com/api/v1"
    huggingface_base_url: str = "https://huggingface.co"
    
    # Rate limiting
    civitai_requests_per_minute: int = 30
    download_chunk_size: int = 8192
    download_timeout: int = 300


@dataclass
class UIConfig:
    """User interface configuration."""
    nsfw_blur_enabled: bool = True  # DEFAULT = ACTIVE (blur NSFW when toggle OFF)
    preview_max_count: int = 6
    preview_thumbnail_size: tuple = (256, 256)
    color_scheme: str = "dark"
    show_download_progress: bool = True


@dataclass
class UIRoots:
    """UI installation roots configuration."""
    comfyui: Path = field(default_factory=lambda: Path.home() / "ComfyUI")
    forge: Path = field(default_factory=lambda: Path.home() / "stable-diffusion-webui-forge")
    a1111: Path = field(default_factory=lambda: Path.home() / "stable-diffusion-webui")
    sdnext: Path = field(default_factory=lambda: Path.home() / "sdnext")
    
    def to_dict(self) -> dict:
        return {
            "comfyui": str(self.comfyui),
            "forge": str(self.forge),
            "a1111": str(self.a1111),
            "sdnext": str(self.sdnext),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UIRoots':
        return cls(
            comfyui=Path(data.get("comfyui", str(Path.home() / "ComfyUI"))),
            forge=Path(data.get("forge", str(Path.home() / "stable-diffusion-webui-forge"))),
            a1111=Path(data.get("a1111", str(Path.home() / "stable-diffusion-webui"))),
            sdnext=Path(data.get("sdnext", str(Path.home() / "sdnext"))),
        )


@dataclass
class StoreSettings:
    """Store v2 configuration."""
    root: Path = field(default_factory=lambda: Path.home() / ".synapse" / "store")
    ui_roots: UIRoots = field(default_factory=UIRoots)
    default_ui_set: str = "local"
    ui_sets: dict = field(default_factory=lambda: {
        # Named sets
        "local": ["comfyui", "forge"],
        "all": ["comfyui", "forge", "a1111", "sdnext"],
        # Implicit singleton sets - each UI can be targeted directly
        "comfyui": ["comfyui"],
        "forge": ["forge"],
        "a1111": ["a1111"],
        "sdnext": ["sdnext"],
    })
    
    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "ui_roots": self.ui_roots.to_dict(),
            "default_ui_set": self.default_ui_set,
            "ui_sets": self.ui_sets,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'StoreSettings':
        ui_roots = UIRoots.from_dict(data.get("ui_roots", {}))
        default_ui_sets = {
            "local": ["comfyui", "forge"],
            "all": ["comfyui", "forge", "a1111", "sdnext"],
            "comfyui": ["comfyui"],
            "forge": ["forge"],
            "a1111": ["a1111"],
            "sdnext": ["sdnext"],
        }
        return cls(
            root=Path(data.get("root", str(Path.home() / ".synapse" / "store"))),
            ui_roots=ui_roots,
            default_ui_set=data.get("default_ui_set", "local"),
            ui_sets=data.get("ui_sets", default_ui_sets),
        )


@dataclass
class SynapseConfig:
    """Main Synapse configuration container."""
    comfyui: ComfyUIConfig = field(default_factory=ComfyUIConfig)
    api: APIConfig = field(default_factory=APIConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    store: StoreSettings = field(default_factory=StoreSettings)
    
    # Synapse data paths
    synapse_data_path: Path = field(
        default_factory=lambda: Path.home() / ".synapse"
    )
    
    @property
    def packs_path(self) -> Path:
        return self.synapse_data_path / "packs"
    
    @property
    def data_path(self) -> Path:
        """Alias for synapse_data_path for compatibility."""
        return self.synapse_data_path
    
    @property
    def registry_path(self) -> Path:
        return self.synapse_data_path / "registry"
    
    @property
    def cache_path(self) -> Path:
        return self.synapse_data_path / "cache"
    
    @property
    def config_file(self) -> Path:
        return self.synapse_data_path / "config.json"
    
    def ensure_directories(self) -> None:
        """Create all necessary directories."""
        directories = [
            self.synapse_data_path,
            self.packs_path,
            self.registry_path,
            self.cache_path,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def save(self) -> None:
        """Save configuration to file."""
        self.ensure_directories()
        config_dict = {
            "comfyui": {
                "base_path": str(self.comfyui.base_path)
            },
            "api": {
                "civitai_token": self.api.civitai_token,
                "huggingface_token": self.api.huggingface_token,
                "civitai_requests_per_minute": self.api.civitai_requests_per_minute,
                "download_chunk_size": self.api.download_chunk_size,
                "download_timeout": self.api.download_timeout,
            },
            "ui": {
                "nsfw_blur_enabled": self.ui.nsfw_blur_enabled,
                "preview_max_count": self.ui.preview_max_count,
                "color_scheme": self.ui.color_scheme,
                "show_download_progress": self.ui.show_download_progress,
            },
            "store": self.store.to_dict(),
        }
        with open(self.config_file, 'w') as f:
            json.dump(config_dict, f, indent=2)
    
    @classmethod
    def load(cls) -> 'SynapseConfig':
        """Load configuration from file or create default."""
        config = cls()
        if config.config_file.exists():
            try:
                with open(config.config_file) as f:
                    data = json.load(f)
                
                if "comfyui" in data:
                    config.comfyui.base_path = Path(data["comfyui"].get(
                        "base_path", str(Path.home() / "ComfyUI")
                    )).expanduser()
                
                if "api" in data:
                    api_data = data["api"]
                    # Load tokens - prefer saved, fallback to env
                    if api_data.get("civitai_token"):
                        config.api.civitai_token = api_data["civitai_token"]
                    if api_data.get("huggingface_token"):
                        config.api.huggingface_token = api_data["huggingface_token"]
                    config.api.civitai_requests_per_minute = api_data.get(
                        "civitai_requests_per_minute", 30
                    )
                    config.api.download_chunk_size = api_data.get(
                        "download_chunk_size", 8192
                    )
                    config.api.download_timeout = api_data.get(
                        "download_timeout", 300
                    )
                
                if "ui" in data:
                    ui_data = data["ui"]
                    config.ui.nsfw_blur_enabled = ui_data.get(
                        "nsfw_blur_enabled", True
                    )
                    config.ui.preview_max_count = ui_data.get(
                        "preview_max_count", 6
                    )
                    config.ui.color_scheme = ui_data.get(
                        "color_scheme", "dark"
                    )
                    config.ui.show_download_progress = ui_data.get(
                        "show_download_progress", True
                    )
                
                if "store" in data:
                    config.store = StoreSettings.from_dict(data["store"])
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load config, using defaults: {e}")
        
        config.ensure_directories()
        return config


# Global configuration instance
_config: Optional[SynapseConfig] = None


def get_config() -> SynapseConfig:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = SynapseConfig.load()
    return _config


def reset_config() -> None:
    """Reset global configuration (useful for testing)."""
    global _config
    _config = None
