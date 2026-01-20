"""
Pack Installer

Handles downloading and installing pack assets:
- Downloads models from Civitai/HuggingFace
- Installs custom nodes
- Downloads preview images
- Verifies hashes
- Tracks installation state
"""

import os
import subprocess
import hashlib
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

try:
    # When running as part of src package (normal operation)
    from .models import (
        Pack, PackLock, LockedAsset, AssetDependency, CustomNodeDependency,
        AssetSource, AssetHash, PreviewImage, ASSET_TYPE_FOLDERS
    )
    from ..clients.civitai_client import CivitaiClient
    from ..clients.huggingface_client import HuggingFaceClient
except ImportError:
    # When running tests with core as top-level package
    from core.models import (
        Pack, PackLock, LockedAsset, AssetDependency, CustomNodeDependency,
        AssetSource, AssetHash, PreviewImage, ASSET_TYPE_FOLDERS
    )
    from clients.civitai_client import CivitaiClient
    from clients.huggingface_client import HuggingFaceClient
from config.settings import get_config, SynapseConfig


class InstallStatus(Enum):
    """Status of an installation operation."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class InstallProgress:
    """Progress information for an installation."""
    asset_name: str
    status: InstallStatus
    downloaded_bytes: int = 0
    total_bytes: int = 0
    message: str = ""


@dataclass
class InstallResult:
    """Result of installing a pack."""
    pack_name: str
    success: bool
    lock: Optional[PackLock]
    installed_assets: List[str]
    failed_assets: List[str]
    skipped_assets: List[str]
    errors: List[str]


ProgressCallback = Callable[[InstallProgress], None]


class PackInstaller:
    """
    Installs pack assets to ComfyUI.
    
    Features:
    - Downloads models from Civitai/HuggingFace
    - Resume support for interrupted downloads
    - Hash verification
    - Custom node installation via git
    - Preview image downloads
    - Progress callbacks for UI
    """
    
    def __init__(
        self,
        config: Optional[SynapseConfig] = None,
        civitai_client: Optional[CivitaiClient] = None,
        huggingface_client: Optional[HuggingFaceClient] = None,
    ):
        self.config = config or get_config()
        self.civitai = civitai_client or CivitaiClient()
        self.huggingface = huggingface_client or HuggingFaceClient()
    
    def install_pack(
        self,
        pack: Pack,
        pack_dir: Path,
        progress_callback: Optional[ProgressCallback] = None,
        skip_existing: bool = True,
        verify_hashes: bool = True,
    ) -> InstallResult:
        """
        Install all assets from a pack.
        
        Args:
            pack: Pack to install
            pack_dir: Directory containing pack files
            progress_callback: Optional callback for progress updates
            skip_existing: Skip assets that already exist
            verify_hashes: Verify file hashes after download
        
        Returns:
            InstallResult with details of installation
        """
        installed = []
        failed = []
        skipped = []
        errors = []
        locked_assets = []
        
        # Install model assets
        for dep in pack.dependencies:
            try:
                result = self._install_asset(
                    dep,
                    progress_callback,
                    skip_existing,
                    verify_hashes,
                )
                
                if result["status"] == InstallStatus.COMPLETE:
                    installed.append(dep.name)
                    locked_assets.append(LockedAsset(
                        name=dep.name,
                        asset_type=dep.asset_type,
                        local_path=result["local_path"],
                        hash=dep.hash,
                        installed_at=datetime.now().isoformat(),
                        verified=result.get("verified", False),
                    ))
                elif result["status"] == InstallStatus.SKIPPED:
                    skipped.append(dep.name)
                    # Still add to lock as it exists
                    locked_assets.append(LockedAsset(
                        name=dep.name,
                        asset_type=dep.asset_type,
                        local_path=result["local_path"],
                        hash=dep.hash,
                        verified=True,
                    ))
                else:
                    failed.append(dep.name)
                    errors.append(result.get("error", f"Failed to install {dep.name}"))
            
            except Exception as e:
                failed.append(dep.name)
                errors.append(f"Error installing {dep.name}: {e}")
        
        # Install custom nodes
        for node_dep in pack.custom_nodes:
            try:
                success = self._install_custom_node(node_dep, progress_callback)
                if success:
                    installed.append(f"node:{node_dep.name}")
                else:
                    failed.append(f"node:{node_dep.name}")
            except Exception as e:
                failed.append(f"node:{node_dep.name}")
                errors.append(f"Error installing node {node_dep.name}: {e}")
        
        # Download preview images
        previews_dir = pack_dir / "previews"
        for preview in pack.previews:
            try:
                self._download_preview(preview, previews_dir, progress_callback)
            except Exception as e:
                errors.append(f"Error downloading preview {preview.filename}: {e}")
        
        # Create lock file
        lock = PackLock(
            pack_name=pack.metadata.name,
            pack_version=pack.metadata.version,
            locked_assets=locked_assets,
            locked_at=datetime.now().isoformat(),
        )
        
        # Save lock file
        lock_path = pack_dir / "pack.lock.json"
        lock.save(lock_path)
        
        return InstallResult(
            pack_name=pack.metadata.name,
            success=len(failed) == 0,
            lock=lock,
            installed_assets=installed,
            failed_assets=failed,
            skipped_assets=skipped,
            errors=errors,
        )
    
    def _install_asset(
        self,
        dep: AssetDependency,
        progress_callback: Optional[ProgressCallback],
        skip_existing: bool,
        verify_hashes: bool,
    ) -> Dict[str, Any]:
        """Install a single asset dependency."""
        
        # Determine destination path
        folder = ASSET_TYPE_FOLDERS.get(dep.asset_type, "unknown")
        dest_dir = self.config.comfyui.models_path / folder
        dest_path = dest_dir / dep.filename
        
        # Check if already exists
        if skip_existing and dest_path.exists():
            if progress_callback:
                progress_callback(InstallProgress(
                    asset_name=dep.name,
                    status=InstallStatus.SKIPPED,
                    message="File already exists",
                ))
            
            return {
                "status": InstallStatus.SKIPPED,
                "local_path": str(dest_path.relative_to(self.config.comfyui.models_path)),
            }
        
        # Notify starting
        if progress_callback:
            progress_callback(InstallProgress(
                asset_name=dep.name,
                status=InstallStatus.DOWNLOADING,
                total_bytes=dep.file_size or 0,
            ))
        
        # Download based on source
        success = False
        expected_hash = dep.hash.sha256 if dep.hash else None
        
        def download_progress(downloaded: int, total: int):
            if progress_callback:
                progress_callback(InstallProgress(
                    asset_name=dep.name,
                    status=InstallStatus.DOWNLOADING,
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                ))
        
        if dep.source == AssetSource.CIVITAI and dep.civitai:
            # Get download URL from Civitai
            version = self.civitai.get_model_version(dep.civitai.model_version_id)
            download_url = self.civitai.get_download_url(version)
            
            if download_url:
                success = self.civitai.download_file(
                    download_url,
                    dest_path,
                    expected_hash=expected_hash,
                    progress_callback=download_progress,
                )
        
        elif dep.source == AssetSource.HUGGINGFACE and dep.huggingface:
            success = self.huggingface.download_file(
                dep.huggingface.repo_id,
                dep.huggingface.filename,
                dest_path,
                revision=dep.huggingface.revision or "main",
                expected_hash=expected_hash,
                progress_callback=download_progress,
            )
        
        elif dep.source == AssetSource.URL and dep.url:
            success = self.civitai.download_file(
                dep.url,
                dest_path,
                expected_hash=expected_hash,
                progress_callback=download_progress,
            )
        
        elif dep.source == AssetSource.LOCAL:
            # Local source - just verify existence
            if dest_path.exists():
                success = True
            else:
                return {
                    "status": InstallStatus.FAILED,
                    "error": f"Local asset not found: {dest_path}",
                }
        
        if success:
            # Verify hash if requested
            verified = False
            if verify_hashes and expected_hash:
                if progress_callback:
                    progress_callback(InstallProgress(
                        asset_name=dep.name,
                        status=InstallStatus.VERIFYING,
                    ))
                verified = self._verify_file_hash(dest_path, expected_hash)
            
            if progress_callback:
                progress_callback(InstallProgress(
                    asset_name=dep.name,
                    status=InstallStatus.COMPLETE,
                    message="Download complete",
                ))
            
            return {
                "status": InstallStatus.COMPLETE,
                "local_path": str(dest_path.relative_to(self.config.comfyui.models_path)),
                "verified": verified,
            }
        else:
            return {
                "status": InstallStatus.FAILED,
                "error": "Download failed",
            }
    
    def _install_custom_node(
        self,
        node_dep: CustomNodeDependency,
        progress_callback: Optional[ProgressCallback],
    ) -> bool:
        """Install a custom node package via git clone."""
        
        custom_nodes_dir = self.config.comfyui.custom_nodes_path
        node_dir = custom_nodes_dir / node_dep.name
        
        if progress_callback:
            progress_callback(InstallProgress(
                asset_name=f"node:{node_dep.name}",
                status=InstallStatus.DOWNLOADING,
                message="Cloning repository",
            ))
        
        try:
            # Check if already installed
            if node_dir.exists():
                # Try to update
                result = subprocess.run(
                    ["git", "pull"],
                    cwd=node_dir,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    # Pull failed, but node exists
                    pass
            else:
                # Clone repository
                result = subprocess.run(
                    ["git", "clone", node_dep.git_url, node_dep.name],
                    cwd=custom_nodes_dir,
                    capture_output=True,
                    text=True,
                )
                
                if result.returncode != 0:
                    return False
            
            # Checkout specific commit if specified
            if node_dep.commit:
                subprocess.run(
                    ["git", "checkout", node_dep.commit],
                    cwd=node_dir,
                    capture_output=True,
                )
            elif node_dep.branch:
                subprocess.run(
                    ["git", "checkout", node_dep.branch],
                    cwd=node_dir,
                    capture_output=True,
                )
            
            # Install pip requirements if any
            if node_dep.pip_requirements:
                requirements_file = node_dir / "requirements.txt"
                if requirements_file.exists():
                    subprocess.run(
                        ["pip", "install", "-r", "requirements.txt"],
                        cwd=node_dir,
                        capture_output=True,
                    )
            
            if progress_callback:
                progress_callback(InstallProgress(
                    asset_name=f"node:{node_dep.name}",
                    status=InstallStatus.COMPLETE,
                ))
            
            return True
            
        except Exception:
            return False
    
    def _download_preview(
        self,
        preview: PreviewImage,
        dest_dir: Path,
        progress_callback: Optional[ProgressCallback],
    ) -> bool:
        """Download a preview image."""
        if not preview.url:
            return False
        
        dest_path = dest_dir / preview.filename
        return self.civitai.download_preview_image(preview, dest_path)
    
    def _verify_file_hash(self, path: Path, expected_hash: str) -> bool:
        """Verify file SHA256 hash."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        
        actual_hash = sha256.hexdigest()
        
        # Support both full hash and AutoV2 (first 10 chars)
        if len(expected_hash) == 10:
            return actual_hash[:10].upper() == expected_hash.upper()
        
        return actual_hash.lower() == expected_hash.lower()
    
    def verify_pack_installation(
        self,
        lock: PackLock,
    ) -> Dict[str, bool]:
        """Verify all assets in a lock file exist and have correct hashes."""
        results = {}
        
        for asset in lock.locked_assets:
            asset_path = self.config.comfyui.models_path / asset.local_path
            
            if not asset_path.exists():
                results[asset.name] = False
                continue
            
            if asset.hash and asset.hash.sha256:
                results[asset.name] = self._verify_file_hash(
                    asset_path,
                    asset.hash.sha256,
                )
            else:
                results[asset.name] = True
        
        return results


def create_installer() -> PackInstaller:
    """Factory function to create a configured PackInstaller."""
    return PackInstaller()
