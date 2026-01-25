"""
Synapse Store v2 - Storage Layout Manager

Manages the v2 storage layout:
- state/ (git-versioned)
  - config.json
  - ui_sets.json
  - packs/<Pack>/pack.json, lock.json, resources/, workflows/
  - profiles/<name>/profile.json
- data/ (local runtime)
  - blobs/sha256/<first2>/<sha256>
  - views/<ui>/profiles/<profile>/..., active -> profiles/<profile>
  - registry/index.sqlite
  - cache/
  - tmp/
  - runtime.json
"""

from __future__ import annotations

import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, List, Optional, Tuple

import filelock

from .models import (
    Pack,
    PackLock,
    Profile,
    Runtime,
    StoreConfig,
    UISets,
)


class StoreError(Exception):
    """Base exception for store errors."""
    pass


class StoreLockError(StoreError):
    """Error when store lock cannot be acquired."""
    pass


class StoreNotInitializedError(StoreError):
    """Error when store is not initialized."""
    pass


class PackNotFoundError(StoreError):
    """Error when pack is not found."""
    pass


class ProfileNotFoundError(StoreError):
    """Error when profile is not found."""
    pass


class StoreLayout:
    """
    Manages the v2 storage layout.
    
    Provides atomic file operations and proper locking for concurrent access.
    """
    
    LOCK_TIMEOUT = 30.0  # seconds
    
    def __init__(self, root: Optional[Path] = None):
        """
        Initialize store layout.
        
        Args:
            root: Root directory for the store. Defaults to SYNAPSE_ROOT env var
                  or ~/.synapse
        """
        if root is None:
            root = Path(os.environ.get("SYNAPSE_ROOT", Path.home() / ".synapse"))
        
        self.root = Path(root).expanduser().resolve()
        
        # Check for separate state/data roots
        self.state_root = Path(os.environ.get("SYNAPSE_STATE_ROOT", self.root / "state"))
        self.data_root = Path(os.environ.get("SYNAPSE_DATA_ROOT", self.root / "data"))
    
    # =========================================================================
    # Path Properties
    # =========================================================================
    
    @property
    def state_path(self) -> Path:
        """Path to state directory (git-versioned)."""
        return self.state_root
    
    @property
    def data_path(self) -> Path:
        """Path to data directory (local runtime)."""
        return self.data_root
    
    @property
    def config_path(self) -> Path:
        """Path to config.json."""
        return self.state_path / "config.json"
    
    @property
    def ui_sets_path(self) -> Path:
        """Path to ui_sets.json."""
        return self.state_path / "ui_sets.json"
    
    @property
    def packs_path(self) -> Path:
        """Path to packs directory."""
        return self.state_path / "packs"
    
    @property
    def profiles_path(self) -> Path:
        """Path to profiles directory."""
        return self.state_path / "profiles"
    
    @property
    def blobs_path(self) -> Path:
        """Path to blob store."""
        return self.data_path / "blobs" / "sha256"
    
    @property
    def views_path(self) -> Path:
        """Path to views directory."""
        return self.data_path / "views"
    
    @property
    def registry_path(self) -> Path:
        """Path to registry directory."""
        return self.data_path / "registry"
    
    @property
    def db_path(self) -> Path:
        """Path to SQLite database."""
        return self.registry_path / "index.sqlite"
    
    @property
    def cache_path(self) -> Path:
        """Path to cache directory."""
        return self.data_path / "cache"
    
    @property
    def tmp_path(self) -> Path:
        """Path to temp directory."""
        return self.data_path / "tmp"
    
    @property
    def runtime_path(self) -> Path:
        """Path to runtime.json."""
        return self.data_path / "runtime.json"
    
    @property
    def lock_file_path(self) -> Path:
        """Path to store lock file."""
        return self.data_path / ".synapse.lock"
    
    # =========================================================================
    # Pack Paths
    # =========================================================================
    
    def pack_dir(self, pack_name: str) -> Path:
        """Get directory for a pack."""
        return self.packs_path / pack_name
    
    def pack_json_path(self, pack_name: str) -> Path:
        """Get path to pack.json for a pack."""
        return self.pack_dir(pack_name) / "pack.json"
    
    def pack_lock_path(self, pack_name: str) -> Path:
        """Get path to lock.json for a pack."""
        return self.pack_dir(pack_name) / "lock.json"
    
    def pack_resources_path(self, pack_name: str) -> Path:
        """Get path to resources directory for a pack."""
        return self.pack_dir(pack_name) / "resources"
    
    def pack_previews_path(self, pack_name: str) -> Path:
        """Get path to previews directory for a pack."""
        return self.pack_resources_path(pack_name) / "previews"
    
    def pack_workflows_path(self, pack_name: str) -> Path:
        """Get path to workflows directory for a pack."""
        return self.pack_dir(pack_name) / "workflows"
    
    # =========================================================================
    # Profile Paths
    # =========================================================================
    
    def profile_dir(self, profile_name: str) -> Path:
        """Get directory for a profile."""
        return self.profiles_path / profile_name
    
    def profile_json_path(self, profile_name: str) -> Path:
        """Get path to profile.json for a profile."""
        return self.profile_dir(profile_name) / "profile.json"
    
    # =========================================================================
    # View Paths
    # =========================================================================
    
    def view_ui_path(self, ui_name: str) -> Path:
        """Get path to views for a specific UI."""
        return self.views_path / ui_name
    
    def view_profiles_path(self, ui_name: str) -> Path:
        """Get path to profiles directory within a UI view."""
        return self.view_ui_path(ui_name) / "profiles"
    
    def view_profile_path(self, ui_name: str, profile_name: str) -> Path:
        """Get path to a specific profile within a UI view."""
        return self.view_profiles_path(ui_name) / profile_name
    
    def view_active_path(self, ui_name: str) -> Path:
        """Get path to active symlink for a UI."""
        return self.view_ui_path(ui_name) / "active"
    
    # =========================================================================
    # Blob Paths
    # =========================================================================
    
    def blob_path(self, sha256: str) -> Path:
        """Get path to a blob by its SHA256 hash."""
        if len(sha256) < 2:
            raise ValueError(f"Invalid SHA256 hash: {sha256}")
        return self.blobs_path / sha256[:2] / sha256
    
    def blob_part_path(self, sha256: str) -> Path:
        """Get path to a partial download for a blob."""
        return self.blob_path(sha256).with_suffix(".part")

    def blob_manifest_path(self, sha256: str) -> Path:
        """Get path to the manifest file for a blob."""
        return self.blob_path(sha256).with_suffix(".meta")

    # =========================================================================
    # Locking
    # =========================================================================
    
    @contextmanager
    def lock(self, timeout: Optional[float] = None) -> Generator[None, None, None]:
        """
        Acquire exclusive lock on the store.
        
        Args:
            timeout: Lock timeout in seconds. Defaults to LOCK_TIMEOUT.
        
        Raises:
            StoreLockError: If lock cannot be acquired.
        """
        if timeout is None:
            timeout = self.LOCK_TIMEOUT
        
        # Ensure lock file parent exists
        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        lock = filelock.FileLock(self.lock_file_path)
        try:
            lock.acquire(timeout=timeout)
            yield
        except filelock.Timeout:
            raise StoreLockError(
                f"Could not acquire store lock within {timeout}s. "
                "Another operation may be in progress."
            )
        finally:
            lock.release()
    
    # =========================================================================
    # Initialization
    # =========================================================================
    
    def is_initialized(self) -> bool:
        """Check if store is initialized."""
        return self.config_path.exists() and self.state_path.exists()
    
    def init_store(self, force: bool = False) -> None:
        """
        Initialize the store with default configuration.
        
        Args:
            force: If True, reinitialize even if already initialized.
        
        Raises:
            StoreError: If already initialized and force is False.
        """
        if self.is_initialized() and not force:
            # Already initialized, just ensure all directories exist
            self._ensure_directories()
            return
        
        with self.lock():
            self._ensure_directories()
            self._write_default_config()
            self._write_default_ui_sets()
            self._write_default_global_profile()
            self._write_default_runtime()
    
    def _ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        directories = [
            self.state_path,
            self.packs_path,
            self.profiles_path,
            self.data_path,
            self.blobs_path,
            self.views_path,
            self.registry_path,
            self.cache_path,
            self.tmp_path,
        ]
        for d in directories:
            d.mkdir(parents=True, exist_ok=True)
    
    def _write_default_config(self) -> None:
        """Write default config.json."""
        if not self.config_path.exists():
            config = StoreConfig.create_default()
            self.write_json(self.config_path, config.model_dump(by_alias=True))
    
    def _write_default_ui_sets(self) -> None:
        """Write default ui_sets.json."""
        if not self.ui_sets_path.exists():
            ui_sets = UISets.create_default()
            self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
    
    def _write_default_global_profile(self) -> None:
        """Write default global profile."""
        global_profile_path = self.profile_json_path("global")
        if not global_profile_path.exists():
            profile = Profile(name="global")
            global_profile_path.parent.mkdir(parents=True, exist_ok=True)
            self.write_json(global_profile_path, profile.model_dump(by_alias=True))
    
    def _write_default_runtime(self) -> None:
        """Write default runtime.json."""
        if not self.runtime_path.exists():
            # Get known UIs from config or use defaults
            ui_names = ["comfyui", "forge"]
            if self.config_path.exists():
                config = self.load_config()
                ui_names = config.ui.known
            runtime = Runtime.create_default(ui_names)
            self.write_json(self.runtime_path, runtime.model_dump(by_alias=True))
    
    # =========================================================================
    # JSON I/O (Atomic)
    # =========================================================================
    
    def write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """
        Write JSON file atomically with canonical formatting.
        
        Uses write-to-temp-then-rename pattern for atomicity.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file first
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
                f.write("\n")  # Trailing newline
            
            # Atomic rename
            tmp_path.replace(path)
        finally:
            # Clean up temp file if it still exists
            if tmp_path.exists():
                tmp_path.unlink()
    
    def read_json(self, path: Path) -> Dict[str, Any]:
        """Read JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # =========================================================================
    # Config Operations
    # =========================================================================
    
    def load_config(self) -> StoreConfig:
        """Load store configuration."""
        if not self.config_path.exists():
            raise StoreNotInitializedError("Store not initialized. Run 'synapse store init' first.")
        data = self.read_json(self.config_path)
        return StoreConfig.model_validate(data)
    
    def save_config(self, config: StoreConfig) -> None:
        """Save store configuration."""
        self.write_json(self.config_path, config.model_dump(by_alias=True))
    
    def load_ui_sets(self) -> UISets:
        """Load UI sets configuration."""
        if not self.ui_sets_path.exists():
            return UISets.create_default()
        data = self.read_json(self.ui_sets_path)
        return UISets.model_validate(data)
    
    def save_ui_sets(self, ui_sets: UISets) -> None:
        """Save UI sets configuration."""
        self.write_json(self.ui_sets_path, ui_sets.model_dump(by_alias=True))
    
    # =========================================================================
    # Pack Operations
    # =========================================================================
    
    def list_packs(self) -> List[str]:
        """List all pack names."""
        if not self.packs_path.exists():
            return []
        return [
            d.name for d in self.packs_path.iterdir()
            if d.is_dir() and (d / "pack.json").exists()
        ]
    
    def pack_exists(self, pack_name: str) -> bool:
        """Check if a pack exists."""
        return self.pack_json_path(pack_name).exists()
    
    def load_pack(self, pack_name: str) -> Pack:
        """Load a pack by name."""
        path = self.pack_json_path(pack_name)
        if not path.exists():
            raise PackNotFoundError(f"Pack not found: {pack_name}")
        data = self.read_json(path)
        return Pack.model_validate(data)
    
    def save_pack(self, pack: Pack) -> None:
        """Save a pack."""
        path = self.pack_json_path(pack.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.write_json(path, pack.model_dump(by_alias=True))
    
    def load_pack_lock(self, pack_name: str) -> Optional[PackLock]:
        """Load lock file for a pack. Returns None if not exists."""
        path = self.pack_lock_path(pack_name)
        if not path.exists():
            return None
        data = self.read_json(path)
        return PackLock.model_validate(data)
    
    def save_pack_lock(self, lock: PackLock) -> None:
        """Save lock file for a pack."""
        path = self.pack_lock_path(lock.pack)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.write_json(path, lock.model_dump(by_alias=True))
    
    def delete_pack(self, pack_name: str) -> bool:
        """Delete a pack. Returns True if deleted."""
        pack_dir = self.pack_dir(pack_name)
        if pack_dir.exists():
            shutil.rmtree(pack_dir)
            return True
        return False
    
    # =========================================================================
    # Profile Operations
    # =========================================================================
    
    def list_profiles(self) -> List[str]:
        """List all profile names."""
        if not self.profiles_path.exists():
            return []
        return [
            d.name for d in self.profiles_path.iterdir()
            if d.is_dir() and (d / "profile.json").exists()
        ]
    
    def profile_exists(self, profile_name: str) -> bool:
        """Check if a profile exists."""
        return self.profile_json_path(profile_name).exists()
    
    def load_profile(self, profile_name: str) -> Profile:
        """Load a profile by name."""
        path = self.profile_json_path(profile_name)
        if not path.exists():
            raise ProfileNotFoundError(f"Profile not found: {profile_name}")
        data = self.read_json(path)
        return Profile.model_validate(data)
    
    def save_profile(self, profile: Profile) -> None:
        """Save a profile."""
        path = self.profile_json_path(profile.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.write_json(path, profile.model_dump(by_alias=True))
    
    def delete_profile(self, profile_name: str) -> bool:
        """Delete a profile. Returns True if deleted. Cannot delete 'global'."""
        if profile_name == "global":
            raise StoreError("Cannot delete global profile")
        profile_dir = self.profile_dir(profile_name)
        if profile_dir.exists():
            shutil.rmtree(profile_dir)
            return True
        return False
    
    # =========================================================================
    # Runtime Operations
    # =========================================================================
    
    def load_runtime(self) -> Runtime:
        """Load runtime state."""
        if not self.runtime_path.exists():
            config = self.load_config() if self.config_path.exists() else StoreConfig.create_default()
            return Runtime.create_default(config.ui.known)
        data = self.read_json(self.runtime_path)
        return Runtime.model_validate(data)
    
    def save_runtime(self, runtime: Runtime) -> None:
        """Save runtime state."""
        self.write_json(self.runtime_path, runtime.model_dump(by_alias=True))
    
    # =========================================================================
    # Iteration Helpers
    # =========================================================================
    
    def iter_packs(self) -> Iterator[Tuple[str, Pack]]:
        """Iterate over all packs."""
        for pack_name in self.list_packs():
            try:
                yield pack_name, self.load_pack(pack_name)
            except Exception:
                continue
    
    def iter_packs_with_locks(self) -> Iterator[Tuple[str, Pack, Optional[PackLock]]]:
        """Iterate over all packs with their locks."""
        for pack_name in self.list_packs():
            try:
                pack = self.load_pack(pack_name)
                lock = self.load_pack_lock(pack_name)
                yield pack_name, pack, lock
            except Exception:
                continue
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def clean_tmp(self) -> int:
        """Clean temporary directory. Returns number of files removed."""
        count = 0
        if self.tmp_path.exists():
            for item in self.tmp_path.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    count += 1
                except Exception:
                    pass
        return count
    
    def clean_cache(self) -> int:
        """Clean cache directory. Returns number of files removed."""
        count = 0
        if self.cache_path.exists():
            for item in self.cache_path.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    count += 1
                except Exception:
                    pass
        return count
