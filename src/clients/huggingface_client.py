"""
HuggingFace Client

Handles downloads from HuggingFace Hub including:
- Single file downloads
- Repository snapshot downloads
- Revision/branch handling
- Resume support
- Token authentication for gated repos
"""

import os
import re
import hashlib
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from urllib.parse import quote

from ..core.models import (
    AssetDependency, AssetType, AssetSource, AssetHash,
    HuggingFaceSource, ASSET_TYPE_FOLDERS
)


@dataclass
class HFFileInfo:
    """Information about a file in a HuggingFace repository."""
    filename: str
    size: int
    sha256: Optional[str]
    lfs: bool
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'HFFileInfo':
        return cls(
            filename=data.get("path", ""),
            size=data.get("size", 0),
            sha256=data.get("oid") if data.get("lfs") else None,  # LFS OID is SHA256
            lfs=data.get("lfs") is not None,
        )


@dataclass
class HFRepoInfo:
    """Information about a HuggingFace repository."""
    repo_id: str
    revision: str
    files: List[HFFileInfo]
    
    @classmethod
    def from_api_response(cls, repo_id: str, revision: str, data: List[Dict[str, Any]]) -> 'HFRepoInfo':
        return cls(
            repo_id=repo_id,
            revision=revision,
            files=[HFFileInfo.from_api_response(f) for f in data if f.get("type") == "file"],
        )


class HuggingFaceClient:
    """
    Client for HuggingFace Hub downloads.
    
    Features:
    - Single file and repository downloads
    - Resume support for large files
    - Token authentication for gated models
    - Revision/branch support
    - Progress callbacks
    """
    
    BASE_URL = "https://huggingface.co"
    API_URL = "https://huggingface.co/api"
    
    # Known model file patterns and their types
    FILE_TYPE_PATTERNS = {
        r".*\.safetensors$": AssetType.CHECKPOINT,
        r".*lora.*\.safetensors$": AssetType.LORA,
        r".*vae.*\.safetensors$": AssetType.VAE,
        r".*text_encoder.*\.safetensors$": AssetType.TEXT_ENCODER,
        r".*diffusion_model.*\.safetensors$": AssetType.DIFFUSION_MODEL,
        r".*unet.*\.safetensors$": AssetType.DIFFUSION_MODEL,
        r".*clip.*\.safetensors$": AssetType.CLIP,
        r".*controlnet.*\.safetensors$": AssetType.CONTROLNET,
        r".*upscale.*\.safetensors$": AssetType.UPSCALER,
    }
    
    # Folder-based type detection
    FOLDER_TYPE_MAP = {
        "text_encoders": AssetType.TEXT_ENCODER,
        "text_encoder": AssetType.TEXT_ENCODER,
        "vae": AssetType.VAE,
        "unet": AssetType.DIFFUSION_MODEL,
        "diffusion_models": AssetType.DIFFUSION_MODEL,
        "controlnet": AssetType.CONTROLNET,
        "loras": AssetType.LORA,
        "embeddings": AssetType.EMBEDDING,
    }
    
    def __init__(
        self,
        token: Optional[str] = None,
        timeout: int = 30,
    ):
        self.token = token or os.environ.get("HF_TOKEN")
        self.timeout = timeout
        
        self.session = requests.Session()
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers["User-Agent"] = "Synapse/1.0"
    
    def get_repo_info(self, repo_id: str, revision: str = "main") -> Optional[Dict[str, Any]]:
        """Get basic repository information."""
        try:
            url = f"{self.API_URL}/models/{repo_id}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
    
    def get_repo_files(
        self,
        repo_id: str,
        revision: str = "main",
        path: str = "",
    ) -> HFRepoInfo:
        """List files in a repository."""
        url = f"{self.API_URL}/models/{repo_id}/tree/{revision}"
        if path:
            url += f"/{path}"
        
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        
        return HFRepoInfo.from_api_response(repo_id, revision, response.json())
    
    def get_file_url(
        self,
        repo_id: str,
        filename: str,
        revision: str = "main",
    ) -> str:
        """Get download URL for a file."""
        encoded_filename = quote(filename, safe="/")
        return f"{self.BASE_URL}/{repo_id}/resolve/{revision}/{encoded_filename}"
    
    def parse_hf_url(self, url: str) -> tuple[str, str, str]:
        """
        Parse a HuggingFace URL to extract repo_id, filename, and revision.
        
        Supports formats:
        - https://huggingface.co/owner/repo/blob/main/path/file.safetensors
        - https://huggingface.co/owner/repo/resolve/main/path/file.safetensors
        """
        # Remove base URL
        path = url.replace(self.BASE_URL + "/", "")
        
        # Match pattern: owner/repo/(blob|resolve)/revision/filepath
        match = re.match(
            r"([^/]+/[^/]+)/(?:blob|resolve)/([^/]+)/(.+)",
            path
        )
        
        if match:
            repo_id = match.group(1)
            revision = match.group(2)
            filename = match.group(3)
            return repo_id, filename, revision
        
        # Simple format: owner/repo
        parts = path.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}", "", "main"
        
        raise ValueError(f"Invalid HuggingFace URL: {url}")
    
    def detect_asset_type(self, filename: str, subfolder: Optional[str] = None) -> AssetType:
        """Detect asset type from filename and path."""
        # Check folder first
        if subfolder:
            folder_name = subfolder.rstrip("/").split("/")[-1].lower()
            if folder_name in self.FOLDER_TYPE_MAP:
                return self.FOLDER_TYPE_MAP[folder_name]
        
        # Check filename patterns
        filename_lower = filename.lower()
        for pattern, asset_type in self.FILE_TYPE_PATTERNS.items():
            if re.match(pattern, filename_lower):
                return asset_type
        
        # Default to checkpoint for .safetensors
        if filename_lower.endswith(".safetensors"):
            return AssetType.CHECKPOINT
        
        return AssetType.UNKNOWN
    
    def create_asset_dependency(
        self,
        repo_id: str,
        filename: str,
        revision: str = "main",
        subfolder: Optional[str] = None,
        file_size: Optional[int] = None,
        sha256: Optional[str] = None,
    ) -> AssetDependency:
        """Create an AssetDependency from HuggingFace file info."""
        
        # Detect asset type
        asset_type = self.detect_asset_type(filename, subfolder)
        
        # Build local path
        folder = ASSET_TYPE_FOLDERS.get(asset_type, "unknown")
        local_filename = filename.split("/")[-1]
        local_path = f"{folder}/{local_filename}"
        
        # Build hash
        asset_hash = AssetHash(sha256=sha256) if sha256 else None
        
        return AssetDependency(
            name=f"{repo_id}/{filename}",
            asset_type=asset_type,
            source=AssetSource.HUGGINGFACE,
            huggingface=HuggingFaceSource(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                subfolder=subfolder,
            ),
            filename=local_filename,
            file_size=file_size,
            hash=asset_hash,
            local_path=local_path,
            required=True,
        )
    
    def download_file(
        self,
        repo_id: str,
        filename: str,
        destination: Path,
        revision: str = "main",
        expected_hash: Optional[str] = None,
        chunk_size: int = 8192,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        resume: bool = True,
    ) -> bool:
        """
        Download a file from HuggingFace Hub.
        
        Args:
            repo_id: Repository ID (owner/repo)
            filename: File path within repository
            destination: Local file path
            revision: Git revision (branch, tag, commit)
            expected_hash: Expected SHA256 hash
            chunk_size: Download chunk size
            progress_callback: Callback(downloaded_bytes, total_bytes)
            resume: Enable resume for interrupted downloads
        
        Returns:
            True if download successful and hash verified
        """
        url = self.get_file_url(repo_id, filename, revision)
        
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        mode = "wb"
        initial_size = 0
        
        # Check for partial download
        if resume and destination.exists():
            initial_size = destination.stat().st_size
            headers["Range"] = f"bytes={initial_size}-"
            mode = "ab"
        
        response = self.session.get(
            url,
            headers=headers,
            stream=True,
            timeout=300,
            allow_redirects=True,
        )
        
        # Handle range response
        if response.status_code == 416:  # Range not satisfiable
            return self._verify_hash(destination, expected_hash)
        
        response.raise_for_status()
        
        # Get total size
        total_size = int(response.headers.get("content-length", 0)) + initial_size
        downloaded = initial_size
        
        # Download with progress
        with open(destination, mode) as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
        
        # Verify hash
        return self._verify_hash(destination, expected_hash)
    
    def _verify_hash(self, path: Path, expected_hash: Optional[str]) -> bool:
        """Verify file SHA256 hash."""
        if not expected_hash:
            return True
        
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        
        actual_hash = sha256.hexdigest()
        return actual_hash.lower() == expected_hash.lower()
    
    def download_repo_files(
        self,
        repo_id: str,
        destination_dir: Path,
        patterns: Optional[List[str]] = None,
        revision: str = "main",
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[Path]:
        """
        Download multiple files from a repository.
        
        Args:
            repo_id: Repository ID
            destination_dir: Local directory for downloads
            patterns: File patterns to match (e.g., ["*.safetensors"])
            revision: Git revision
            progress_callback: Callback(filename, downloaded_bytes, total_bytes)
        
        Returns:
            List of downloaded file paths
        """
        repo_info = self.get_repo_files(repo_id, revision)
        downloaded = []
        
        for file_info in repo_info.files:
            # Check patterns
            if patterns:
                matches = False
                for pattern in patterns:
                    if re.match(pattern.replace("*", ".*"), file_info.filename):
                        matches = True
                        break
                if not matches:
                    continue
            
            # Download file
            dest_path = destination_dir / file_info.filename
            
            def file_progress(downloaded_bytes: int, total_bytes: int):
                if progress_callback:
                    progress_callback(file_info.filename, downloaded_bytes, total_bytes)
            
            success = self.download_file(
                repo_id,
                file_info.filename,
                dest_path,
                revision=revision,
                expected_hash=file_info.sha256,
                progress_callback=file_progress,
            )
            
            if success:
                downloaded.append(dest_path)
        
        return downloaded


def create_huggingface_client() -> HuggingFaceClient:
    """Factory function to create a configured HuggingFaceClient."""
    return HuggingFaceClient(
        token=os.environ.get("HF_TOKEN"),
    )
