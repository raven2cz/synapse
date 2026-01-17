"""
API Configuration - Proxy to main config

This module provides a unified interface to the main config system.
All settings come from config/settings.py.
"""

from pathlib import Path
from typing import Optional

# Import main config
from config.settings import get_config


class Settings:
    """
    Proxy settings class that delegates to main config.
    
    This ensures single source of truth for all configuration.
    """
    
    @property
    def debug(self) -> bool:
        return False
    
    @property
    def host(self) -> str:
        return "0.0.0.0"
    
    @property
    def port(self) -> int:
        return 8000
    
    @property
    def comfyui_path(self) -> Path:
        config = get_config()
        return Path(config.comfyui.base_path).expanduser()
    
    @property
    def synapse_data_path(self) -> Path:
        config = get_config()
        return config.data_path
    
    @property
    def store_root(self) -> Path:
        config = get_config()
        return config.store.root
    
    @property
    def civitai_token(self) -> Optional[str]:
        config = get_config()
        return config.api.civitai_token
    
    @property
    def huggingface_token(self) -> Optional[str]:
        config = get_config()
        return config.api.huggingface_token
    
    @property
    def nsfw_blur_enabled(self) -> bool:
        config = get_config()
        return config.ui.nsfw_blur_enabled


# Singleton instance
settings = Settings()
