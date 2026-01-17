"""
Civitai API Client

Handles all communication with Civitai API including:
- Model and version lookups
- File downloads with resume support
- Hash verification
- Preview image downloads
- Rate limiting and error handling
"""

import os
import re
import time
import hashlib
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
import json

from ..core.models import (
    AssetDependency, AssetType, AssetSource, AssetHash,
    CivitaiSource, PreviewImage, ASSET_TYPE_FOLDERS
)


@dataclass
class CivitaiModelVersion:
    """Parsed model version data from Civitai API."""
    id: int
    model_id: int
    name: str
    description: Optional[str]
    base_model: Optional[str]
    files: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    download_url: Optional[str]
    trained_words: List[str]
    published_at: Optional[str] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any], model_id: int) -> 'CivitaiModelVersion':
        return cls(
            id=data["id"],
            model_id=model_id,
            name=data.get("name", ""),
            description=data.get("description"),
            base_model=data.get("baseModel"),
            files=data.get("files", []),
            images=data.get("images", []),
            download_url=data.get("downloadUrl"),
            trained_words=data.get("trainedWords", []),
            published_at=data.get("publishedAt"),
        )


@dataclass
class CivitaiModel:
    """Parsed model data from Civitai API."""
    id: int
    name: str
    description: Optional[str]
    type: str
    nsfw: bool
    tags: List[str]
    creator: Optional[Dict[str, Any]]
    model_versions: List[CivitaiModelVersion]
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'CivitaiModel':
        model_id = data["id"]
        return cls(
            id=model_id,
            name=data.get("name", ""),
            description=data.get("description"),
            type=data.get("type", ""),
            nsfw=data.get("nsfw", False),
            tags=data.get("tags", []),
            creator=data.get("creator"),
            model_versions=[
                CivitaiModelVersion.from_api_response(v, model_id)
                for v in data.get("modelVersions", [])
            ],
        )


class CivitaiClient:
    """
    Client for Civitai API with download support.
    
    Features:
    - Model and version lookup
    - File download with resume support
    - Hash verification (SHA256, AutoV2)
    - Preview image downloads
    - Rate limiting
    - Progress callbacks
    """
    
    BASE_URL = "https://civitai.com/api/v1"
    
    # Mapping Civitai model types to our AssetType
    MODEL_TYPE_MAP = {
        "Checkpoint": AssetType.CHECKPOINT,
        "LORA": AssetType.LORA,
        "TextualInversion": AssetType.EMBEDDING,
        "VAE": AssetType.VAE,
        "ControlNet": AssetType.CONTROLNET,
        "Upscaler": AssetType.UPSCALER,
        "AestheticGradient": AssetType.EMBEDDING,
        "Hypernetwork": AssetType.EMBEDDING,
        "Poses": AssetType.UNKNOWN,
        "Wildcards": AssetType.UNKNOWN,
        "Other": AssetType.UNKNOWN,
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        requests_per_minute: int = 30,
        timeout: int = 30,
    ):
        self.api_key = api_key or os.environ.get("CIVITAI_API_KEY")
        self.requests_per_minute = requests_per_minute
        self.timeout = timeout
        self._last_request_time = 0.0
        self._request_interval = 60.0 / requests_per_minute
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; Synapse/1.0)",
            "Accept": "application/json",
        })
        if self.api_key:
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> requests.Response:
        """Make a rate-limited API request."""
        self._rate_limit()
        
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.request(
            method,
            url,
            params=params,
            timeout=self.timeout,
            **kwargs
        )
        response.raise_for_status()
        return response
    
    def get_model(self, model_id: int) -> Dict[str, Any]:
        """Fetch model details by ID. Returns raw API response dict."""
        response = self._request("GET", f"models/{model_id}")
        return response.json()
    
    def get_model_as_object(self, model_id: int) -> CivitaiModel:
        """Fetch model details by ID as CivitaiModel object."""
        data = self.get_model(model_id)
        return CivitaiModel.from_api_response(data)
    
    def get_model_version(self, version_id: int) -> Dict[str, Any]:
        """Fetch model version details by ID. Returns raw API response dict."""
        response = self._request("GET", f"model-versions/{version_id}")
        return response.json()
    
    def get_model_version_as_object(self, version_id: int) -> CivitaiModelVersion:
        """Fetch model version details by ID as object."""
        data = self.get_model_version(version_id)
        model_id = data.get("modelId", 0)
        return CivitaiModelVersion.from_api_response(data, model_id)
    
    def get_model_by_hash(self, hash_value: str) -> Optional[CivitaiModelVersion]:
        """Find model version by file hash (SHA256 or AutoV2)."""
        try:
            response = self._request("GET", f"model-versions/by-hash/{hash_value}")
            data = response.json()
            model_id = data.get("modelId", 0)
            return CivitaiModelVersion.from_api_response(data, model_id)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def search_models(
        self,
        query: Optional[str] = None,
        tag: Optional[str] = None,
        username: Optional[str] = None,
        types: Optional[List[str]] = None,
        nsfw: Optional[bool] = None,
        sort: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for models. Returns raw API response dict."""
        params: Dict[str, Any] = {
            "limit": limit,
        }
        if query:
            params["query"] = query
        if tag:
            params["tag"] = tag
        if username:
            params["username"] = username
        if types:
            params["types"] = ",".join(types)
        if nsfw is not None:
            params["nsfw"] = "true" if nsfw else "false"
        if sort:
            params["sort"] = sort
        if cursor:
            params["cursor"] = cursor
        
        # Use authenticated session to include API key (needed for some models/settings)
        # and standard rate limiting
        response = self._request(
            "GET",
            "models",
            params=params
        )
        return response.json()
    
    def parse_civitai_url(self, url: str) -> Tuple[int, Optional[int]]:
        """
        Parse a Civitai URL to extract model ID and optional version ID.
        
        Supports formats:
        - https://civitai.com/models/12345
        - https://civitai.com/models/12345/model-name
        - https://civitai.com/models/12345?modelVersionId=67890
        """
        parsed = urlparse(url)
        
        # Extract model ID from path
        path_match = re.match(r'/models/(\d+)', parsed.path)
        if not path_match:
            raise ValueError(f"Invalid Civitai URL: {url}")
        
        model_id = int(path_match.group(1))
        
        # Check for version ID in query params
        query_params = parse_qs(parsed.query)
        version_id = None
        if "modelVersionId" in query_params:
            version_id = int(query_params["modelVersionId"][0])
        
        return model_id, version_id
    
    def get_asset_type(self, civitai_type: str) -> AssetType:
        """Convert Civitai model type to our AssetType."""
        return self.MODEL_TYPE_MAP.get(civitai_type, AssetType.UNKNOWN)
    
    def create_asset_dependency(
        self,
        model: CivitaiModel,
        version: CivitaiModelVersion,
        file_index: int = 0,
    ) -> AssetDependency:
        """Create an AssetDependency from Civitai model/version data."""
        
        if not version.files:
            raise ValueError(f"No files available for version {version.id}")
        
        file_data = version.files[file_index]
        
        # Extract hash information
        hashes = file_data.get("hashes", {})
        asset_hash = AssetHash(
            sha256=hashes.get("SHA256"),
            civitai_autov2=hashes.get("AutoV2"),
        )
        
        # Determine asset type
        asset_type = self.get_asset_type(model.type)
        
        # Determine local path based on asset type
        folder = ASSET_TYPE_FOLDERS.get(asset_type, "unknown")
        filename = file_data.get("name", f"model_{model.id}.safetensors")
        local_path = f"{folder}/{filename}"
        
        # Get download URL
        download_url = file_data.get("downloadUrl")
        if not download_url:
            # Construct download URL from model/version IDs
            download_url = f"https://civitai.com/api/download/models/{version.id}"
        
        print(f"[CivitaiClient] Created dependency: {model.name}, url={download_url}")
        
        return AssetDependency(
            name=model.name,
            asset_type=asset_type,
            source=AssetSource.CIVITAI,
            civitai=CivitaiSource(
                model_id=model.id,
                model_version_id=version.id,
                file_id=file_data.get("id"),
                model_name=model.name,
                version_name=version.name,
            ),
            filename=filename,
            file_size=file_data.get("sizeKB", 0) * 1024 if file_data.get("sizeKB") else None,
            hash=asset_hash,
            local_path=local_path,
            url=download_url,
            description=model.description,
            required=True,
        )
    
    def get_preview_images(
        self,
        version: CivitaiModelVersion,
        max_count: int = 6,
    ) -> List[PreviewImage]:
        """Extract preview images from model version."""
        previews = []
        
        for img in version.images[:max_count]:
            # Civitai images have NSFW level: 1=None, 2=Soft, 3+=Explicit
            nsfw_level = img.get("nsfw", 1) if isinstance(img.get("nsfw"), int) else (
                3 if img.get("nsfw") else 1
            )
            is_nsfw = nsfw_level >= 2  # Soft and above
            
            url = img.get("url", "")
            filename = url.split("/")[-1].split("?")[0] if url else f"preview_{img.get('id', 0)}.jpg"
            
            previews.append(PreviewImage(
                filename=filename,
                url=url,
                nsfw=is_nsfw,
                width=img.get("width"),
                height=img.get("height"),
            ))
        
        return previews
    
    def download_file(
        self,
        url: str,
        destination: Path,
        expected_hash: Optional[str] = None,
        chunk_size: int = 8192,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        resume: bool = True,
    ) -> bool:
        """
        Download a file with optional resume support and hash verification.
        
        Args:
            url: Download URL
            destination: Local file path
            expected_hash: Expected SHA256 hash for verification
            chunk_size: Download chunk size
            progress_callback: Callback(downloaded_bytes, total_bytes)
            resume: Enable resume for interrupted downloads
        
        Returns:
            True if download successful and hash verified
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        headers = {}
        mode = "wb"
        initial_size = 0
        
        # Check for partial download
        if resume and destination.exists():
            initial_size = destination.stat().st_size
            headers["Range"] = f"bytes={initial_size}-"
            mode = "ab"
        
        self._rate_limit()
        
        # Add API key to download URL if needed
        if self.api_key and "civitai.com" in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}token={self.api_key}"
        
        response = self.session.get(
            url,
            headers=headers,
            stream=True,
            timeout=300,
        )
        
        # Handle range response
        if response.status_code == 416:  # Range not satisfiable - file complete
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
        """Verify file hash (SHA256)."""
        if not expected_hash:
            return True
        
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        
        actual_hash = sha256.hexdigest()
        
        # Support both full SHA256 and AutoV2 (first 10 chars)
        if len(expected_hash) == 10:
            return actual_hash[:10].upper() == expected_hash.upper()
        
        return actual_hash.lower() == expected_hash.lower()
    
    def download_preview_image(
        self,
        preview: PreviewImage,
        destination: Path,
    ) -> bool:
        """Download a preview image."""
        if not preview.url:
            return False
        
        try:
            self._rate_limit()
            response = self.session.get(preview.url, timeout=30)
            response.raise_for_status()
            
            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(destination, "wb") as f:
                f.write(response.content)
            
            return True
        except Exception:
            return False
    
    def get_download_url(self, version: CivitaiModelVersion, file_index: int = 0) -> str:
        """Get download URL for a model version file."""
        if version.files and len(version.files) > file_index:
            return version.files[file_index].get("downloadUrl", "")
        return version.download_url or ""


def create_civitai_client() -> CivitaiClient:
    """Factory function to create a configured CivitaiClient."""
    return CivitaiClient(
        api_key=os.environ.get("CIVITAI_API_KEY"),
        requests_per_minute=30,
    )
