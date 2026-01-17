"""
ComfyUI Router

Provides endpoints for interacting with ComfyUI:
- List local models (checkpoints, loras, etc.)
- Check ComfyUI status
- Get model folders
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from pathlib import Path
import os

from config.settings import get_config

logger = logging.getLogger(__name__)

router = APIRouter()


class LocalModel(BaseModel):
    """Local model information."""
    name: str
    path: str
    type: str
    size: Optional[int] = None
    modified: Optional[str] = None


class ComfyUIStatus(BaseModel):
    """ComfyUI connection status."""
    connected: bool
    url: Optional[str] = None
    version: Optional[str] = None


# Model type to folder mapping (matches ComfyUI structure)
MODEL_FOLDERS = {
    "checkpoints": ["checkpoints"],
    "loras": ["loras"],
    "vae": ["vae"],
    "controlnet": ["controlnet"],
    "embeddings": ["embeddings"],
    "upscale_models": ["upscale_models"],
    "clip": ["clip"],
    "clip_vision": ["clip_vision"],
    "diffusion_models": ["diffusion_models", "unet"],
}

# File extensions to include
MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}


def get_models_from_folder(base_path: Path, folder_name: str) -> List[LocalModel]:
    """Scan folder for model files."""
    models = []
    
    folders_to_check = MODEL_FOLDERS.get(folder_name, [folder_name])
    
    for folder in folders_to_check:
        folder_path = base_path / folder
        if not folder_path.exists():
            continue
        
        try:
            for file_path in folder_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in MODEL_EXTENSIONS:
                    try:
                        stat = file_path.stat()
                        models.append(LocalModel(
                            name=file_path.name,
                            path=str(file_path.relative_to(base_path)),
                            type=folder_name,
                            size=stat.st_size,
                            modified=str(stat.st_mtime),
                        ))
                    except Exception as e:
                        logger.warning(f"Error reading file {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Error scanning folder {folder_path}: {e}")
    
    return models


@router.get("/status", response_model=ComfyUIStatus)
async def get_comfyui_status():
    """Check ComfyUI connection status."""
    config = get_config()
    
    # TODO: Actually check ComfyUI API
    # For now, just return configured URL
    return ComfyUIStatus(
        connected=True,
        url=config.paths.comfyui_url if hasattr(config.paths, 'comfyui_url') else "http://127.0.0.1:8188",
    )


@router.get("/models/{model_type}", response_model=List[LocalModel])
async def get_local_models(model_type: str):
    """Get list of local models by type.
    
    Args:
        model_type: One of: checkpoints, loras, vae, controlnet, embeddings, upscale_models, clip, diffusion_models
    """
    config = get_config()
    
    # Get ComfyUI models path
    models_path = Path(config.paths.comfyui) / "models"
    
    if not models_path.exists():
        logger.warning(f"ComfyUI models path not found: {models_path}")
        return []
    
    models = get_models_from_folder(models_path, model_type)
    
    # Sort by name
    models.sort(key=lambda m: m.name.lower())
    
    return models


@router.get("/models", response_model=Dict[str, List[LocalModel]])
async def get_all_local_models():
    """Get all local models grouped by type."""
    config = get_config()
    
    models_path = Path(config.paths.comfyui) / "models"
    
    if not models_path.exists():
        logger.warning(f"ComfyUI models path not found: {models_path}")
        return {}
    
    result = {}
    for model_type in MODEL_FOLDERS.keys():
        models = get_models_from_folder(models_path, model_type)
        if models:
            result[model_type] = models
    
    return result


@router.get("/folders")
async def get_model_folders():
    """Get ComfyUI model folder structure."""
    config = get_config()
    
    models_path = Path(config.paths.comfyui) / "models"
    
    folders = {}
    for folder_type, folder_names in MODEL_FOLDERS.items():
        for folder_name in folder_names:
            folder_path = models_path / folder_name
            if folder_path.exists():
                folders[folder_type] = str(folder_path)
                break
    
    return {
        "base_path": str(models_path),
        "folders": folders,
    }
