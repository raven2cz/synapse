"""
Pack Registry

Central registry for managing installed packs:
- List all packs
- Track installation status
- Manage pack metadata
- Handle pack updates
"""

import json
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..core.models import Pack, PackLock, PackMetadata
from config.settings import get_config, SynapseConfig


@dataclass
class RegistryEntry:
    """Entry in the pack registry."""
    name: str
    version: str
    installed: bool
    pack_path: Path
    lock_path: Optional[Path]
    installed_at: Optional[str]
    source_url: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "installed": self.installed,
            "pack_path": str(self.pack_path),
            "lock_path": str(self.lock_path) if self.lock_path else None,
            "installed_at": self.installed_at,
            "source_url": self.source_url,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegistryEntry':
        return cls(
            name=data["name"],
            version=data["version"],
            installed=data.get("installed", False),
            pack_path=Path(data["pack_path"]),
            lock_path=Path(data["lock_path"]) if data.get("lock_path") else None,
            installed_at=data.get("installed_at"),
            source_url=data.get("source_url"),
        )


@dataclass
class Registry:
    """Collection of registry entries."""
    entries: Dict[str, RegistryEntry] = field(default_factory=dict)
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "updated_at": self.updated_at or datetime.now().isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Registry':
        return cls(
            entries={
                k: RegistryEntry.from_dict(v)
                for k, v in data.get("entries", {}).items()
            },
            updated_at=data.get("updated_at"),
        )
    
    def save(self, path: Path) -> None:
        """Save registry to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: Path) -> 'Registry':
        """Load registry from file."""
        if not path.exists():
            return cls()
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


class PackRegistry:
    """
    Manages the central registry of Synapse packs.
    
    Features:
    - List all available packs
    - Track installation status
    - Load/save pack metadata
    - Handle pack lifecycle
    """
    
    def __init__(self, config: Optional[SynapseConfig] = None):
        self.config = config or get_config()
        self._registry: Optional[Registry] = None
    
    @property
    def registry_file(self) -> Path:
        return self.config.registry_path / "registry.json"
    
    @property
    def registry(self) -> Registry:
        """Get or load the registry."""
        if self._registry is None:
            self._registry = Registry.load(self.registry_file)
        return self._registry
    
    def save_registry(self) -> None:
        """Save the current registry state."""
        self.registry.updated_at = datetime.now().isoformat()
        self.registry.save(self.registry_file)
    
    def scan_packs_directory(self) -> None:
        """Scan packs directory and update registry."""
        packs_dir = self.config.packs_path
        
        if not packs_dir.exists():
            return
        
        # Find all pack.json files
        for pack_file in packs_dir.rglob("pack.json"):
            try:
                pack = Pack.load(pack_file)
                pack_dir = pack_file.parent
                
                # Check for lock file
                lock_file = pack_dir / "pack.lock.json"
                has_lock = lock_file.exists()
                
                entry = RegistryEntry(
                    name=pack.metadata.name,
                    version=pack.metadata.version,
                    installed=has_lock,
                    pack_path=pack_dir,
                    lock_path=lock_file if has_lock else None,
                    installed_at=pack.metadata.created_at,
                    source_url=pack.metadata.source_url,
                )
                
                self.registry.entries[pack.metadata.name] = entry
            
            except Exception as e:
                print(f"Error loading pack from {pack_file}: {e}")
        
        self.save_registry()
    
    def list_packs(self, installed_only: bool = False) -> List[RegistryEntry]:
        """List all registered packs."""
        entries = list(self.registry.entries.values())
        
        if installed_only:
            entries = [e for e in entries if e.installed]
        
        return sorted(entries, key=lambda e: e.name)
    
    def get_pack(self, name: str) -> Optional[Pack]:
        """Load a pack by name."""
        entry = self.registry.entries.get(name)
        if not entry:
            return None
        
        pack_file = entry.pack_path / "pack.json"
        if not pack_file.exists():
            return None
        
        return Pack.load(pack_file)
    
    def get_pack_lock(self, name: str) -> Optional[PackLock]:
        """Load a pack's lock file."""
        entry = self.registry.entries.get(name)
        if not entry or not entry.lock_path:
            return None
        
        if not entry.lock_path.exists():
            return None
        
        return PackLock.load(entry.lock_path)
    
    def register_pack(self, pack: Pack, pack_dir: Path) -> RegistryEntry:
        """Register a new pack."""
        # Save pack.json
        pack_file = pack_dir / "pack.json"
        pack.save(pack_file)
        
        # Create registry entry
        entry = RegistryEntry(
            name=pack.metadata.name,
            version=pack.metadata.version,
            installed=False,
            pack_path=pack_dir,
            lock_path=None,
            installed_at=None,
            source_url=pack.metadata.source_url,
        )
        
        self.registry.entries[pack.metadata.name] = entry
        self.save_registry()
        
        return entry
    
    def mark_installed(self, name: str, lock: PackLock) -> None:
        """Mark a pack as installed and save lock file."""
        entry = self.registry.entries.get(name)
        if not entry:
            return
        
        lock_path = entry.pack_path / "pack.lock.json"
        lock.save(lock_path)
        
        entry.installed = True
        entry.lock_path = lock_path
        entry.installed_at = datetime.now().isoformat()
        
        self.save_registry()
    
    def unregister_pack(self, name: str, delete_files: bool = False) -> bool:
        """Remove a pack from registry."""
        entry = self.registry.entries.get(name)
        if not entry:
            return False
        
        if delete_files and entry.pack_path.exists():
            shutil.rmtree(entry.pack_path)
        
        del self.registry.entries[name]
        self.save_registry()
        
        return True
    
    def get_pack_directory(self, name: str) -> Path:
        """Get or create directory for a pack."""
        pack_dir = self.config.packs_path / name
        pack_dir.mkdir(parents=True, exist_ok=True)
        return pack_dir


def create_registry() -> PackRegistry:
    """Factory function to create a PackRegistry."""
    return PackRegistry()
