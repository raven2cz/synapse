"""
Pack Validator and Doctor

Validates pack integrity and diagnoses issues:
- Verifies all assets exist
- Checks hash consistency
- Validates workflow references
- Suggests fixes for common problems
"""

import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from ..core.models import Pack, PackLock, AssetDependency, AssetType, ASSET_TYPE_FOLDERS
from config.settings import get_config, SynapseConfig


class IssueLevel(Enum):
    """Severity level of a validation issue."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    level: IssueLevel
    message: str
    asset_name: Optional[str] = None
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "message": self.message,
            "asset_name": self.asset_name,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Result of pack validation."""
    pack_name: str
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    
    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level in (IssueLevel.ERROR, IssueLevel.CRITICAL))
    
    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == IssueLevel.WARNING)


@dataclass
class DiagnosticReport:
    """Full diagnostic report for Synapse installation."""
    comfyui_found: bool
    comfyui_path: Path
    models_found: Dict[str, int]  # asset_type -> count
    custom_nodes_found: int
    packs_registered: int
    packs_installed: int
    issues: List[ValidationIssue] = field(default_factory=list)


class PackValidator:
    """
    Validates pack integrity and consistency.
    
    Checks:
    - All required assets exist
    - Hash verification (optional)
    - Workflow file references
    - Custom node availability
    - Lock file consistency
    """
    
    def __init__(self, config: Optional[SynapseConfig] = None):
        self.config = config or get_config()
    
    def validate_pack(
        self,
        pack: Pack,
        pack_dir: Path,
        check_hashes: bool = False,
    ) -> ValidationResult:
        """Validate a pack's integrity."""
        issues = []
        
        # Check asset dependencies
        for dep in pack.dependencies:
            asset_issues = self._validate_asset(dep, check_hashes)
            issues.extend(asset_issues)
        
        # Check custom nodes
        for node_dep in pack.custom_nodes:
            node_issues = self._validate_custom_node(node_dep)
            issues.extend(node_issues)
        
        # Check workflows
        for workflow in pack.workflows:
            workflow_path = pack_dir / "workflows" / workflow.filename
            if not workflow_path.exists():
                # Try pack_dir directly
                workflow_path = pack_dir / workflow.filename
            
            if not workflow_path.exists():
                issues.append(ValidationIssue(
                    level=IssueLevel.WARNING,
                    message=f"Workflow file not found: {workflow.filename}",
                    asset_name=workflow.name,
                    suggestion="Re-download or locate the workflow file",
                ))
        
        # Check previews
        previews_dir = pack_dir / "previews"
        for preview in pack.previews:
            preview_path = previews_dir / preview.filename
            if not preview_path.exists() and preview.url:
                issues.append(ValidationIssue(
                    level=IssueLevel.INFO,
                    message=f"Preview image not downloaded: {preview.filename}",
                    suggestion="Download preview images",
                ))
        
        # Determine overall validity
        valid = not any(i.level in (IssueLevel.ERROR, IssueLevel.CRITICAL) for i in issues)
        
        return ValidationResult(
            pack_name=pack.metadata.name,
            valid=valid,
            issues=issues,
        )
    
    def _validate_asset(
        self,
        dep: AssetDependency,
        check_hash: bool,
    ) -> List[ValidationIssue]:
        """Validate a single asset dependency."""
        issues = []
        
        # Determine expected path
        folder = ASSET_TYPE_FOLDERS.get(dep.asset_type, "unknown")
        expected_path = self.config.comfyui.models_path / folder / dep.filename
        
        if not expected_path.exists():
            # Try local_path if specified
            if dep.local_path:
                alt_path = self.config.comfyui.models_path / dep.local_path
                if alt_path.exists():
                    expected_path = alt_path
        
        if not expected_path.exists():
            issues.append(ValidationIssue(
                level=IssueLevel.ERROR,
                message=f"Asset file not found: {dep.filename}",
                asset_name=dep.name,
                suggestion=f"Install the pack to download missing assets",
            ))
            return issues
        
        # Check file size
        if dep.file_size:
            actual_size = expected_path.stat().st_size
            if abs(actual_size - dep.file_size) > 1024:  # Allow 1KB variance
                issues.append(ValidationIssue(
                    level=IssueLevel.WARNING,
                    message=f"File size mismatch for {dep.filename}",
                    asset_name=dep.name,
                    suggestion="Re-download the asset to fix potential corruption",
                ))
        
        # Check hash
        if check_hash and dep.hash and dep.hash.sha256:
            if not self._verify_hash(expected_path, dep.hash.sha256):
                issues.append(ValidationIssue(
                    level=IssueLevel.ERROR,
                    message=f"Hash mismatch for {dep.filename}",
                    asset_name=dep.name,
                    suggestion="Re-download the asset - file may be corrupted",
                ))
        
        return issues
    
    def _validate_custom_node(
        self,
        node_dep,
    ) -> List[ValidationIssue]:
        """Validate a custom node dependency."""
        issues = []
        
        node_path = self.config.comfyui.custom_nodes_path / node_dep.name
        
        if not node_path.exists():
            issues.append(ValidationIssue(
                level=IssueLevel.ERROR,
                message=f"Custom node not installed: {node_dep.name}",
                asset_name=node_dep.name,
                suggestion=f"Install via: git clone {node_dep.git_url}",
            ))
        
        return issues
    
    def _verify_hash(self, path: Path, expected_hash: str) -> bool:
        """Verify file SHA256 hash."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        
        actual = sha256.hexdigest()
        
        # Support AutoV2 (first 10 chars)
        if len(expected_hash) == 10:
            return actual[:10].upper() == expected_hash.upper()
        
        return actual.lower() == expected_hash.lower()
    
    def validate_lock(
        self,
        lock: PackLock,
        check_hashes: bool = False,
    ) -> ValidationResult:
        """Validate a pack lock file against actual installation."""
        issues = []
        
        for asset in lock.locked_assets:
            asset_path = self.config.comfyui.models_path / asset.local_path
            
            if not asset_path.exists():
                issues.append(ValidationIssue(
                    level=IssueLevel.ERROR,
                    message=f"Locked asset missing: {asset.name}",
                    asset_name=asset.name,
                    suggestion="Re-install the pack",
                ))
                continue
            
            if check_hashes and asset.hash and asset.hash.sha256:
                if not self._verify_hash(asset_path, asset.hash.sha256):
                    issues.append(ValidationIssue(
                        level=IssueLevel.ERROR,
                        message=f"Hash mismatch for locked asset: {asset.name}",
                        asset_name=asset.name,
                        suggestion="Re-download the asset",
                    ))
        
        valid = not any(i.level in (IssueLevel.ERROR, IssueLevel.CRITICAL) for i in issues)
        
        return ValidationResult(
            pack_name=lock.pack_name,
            valid=valid,
            issues=issues,
        )


class SynapseDoctor:
    """
    Diagnoses overall Synapse and ComfyUI installation health.
    
    Checks:
    - ComfyUI installation
    - Model directories
    - Custom nodes
    - Pack registry integrity
    """
    
    def __init__(self, config: Optional[SynapseConfig] = None):
        self.config = config or get_config()
        self.validator = PackValidator(config)
    
    def run_diagnostics(self) -> DiagnosticReport:
        """Run full diagnostic check."""
        issues = []
        
        # Check ComfyUI
        comfyui_found = self.config.comfyui.base_path.exists()
        
        if not comfyui_found:
            issues.append(ValidationIssue(
                level=IssueLevel.CRITICAL,
                message=f"ComfyUI not found at {self.config.comfyui.base_path}",
                suggestion="Update ComfyUI path in Synapse settings",
            ))
        
        # Count models
        models_found = {}
        if comfyui_found:
            for asset_type, folder in ASSET_TYPE_FOLDERS.items():
                folder_path = self.config.comfyui.models_path / folder
                if folder_path.exists():
                    count = sum(1 for _ in folder_path.glob("*.safetensors"))
                    count += sum(1 for _ in folder_path.glob("*.ckpt"))
                    count += sum(1 for _ in folder_path.glob("*.gguf"))
                    models_found[asset_type.value] = count
        
        # Count custom nodes
        custom_nodes_found = 0
        if comfyui_found:
            custom_nodes_path = self.config.comfyui.custom_nodes_path
            if custom_nodes_path.exists():
                custom_nodes_found = sum(
                    1 for p in custom_nodes_path.iterdir()
                    if p.is_dir() and not p.name.startswith(".")
                )
        
        # Check registry
        registry_path = self.config.registry_path / "registry.json"
        packs_registered = 0
        packs_installed = 0
        
        if registry_path.exists():
            from ..core.registry import Registry
            registry = Registry.load(registry_path)
            packs_registered = len(registry.entries)
            packs_installed = sum(1 for e in registry.entries.values() if e.installed)
        
        # Check Synapse directories
        if not self.config.synapse_data_path.exists():
            issues.append(ValidationIssue(
                level=IssueLevel.INFO,
                message="Synapse data directory not initialized",
                suggestion="Run synapse init to set up directories",
            ))
        
        return DiagnosticReport(
            comfyui_found=comfyui_found,
            comfyui_path=self.config.comfyui.base_path,
            models_found=models_found,
            custom_nodes_found=custom_nodes_found,
            packs_registered=packs_registered,
            packs_installed=packs_installed,
            issues=issues,
        )
    
    def suggest_fixes(self, report: DiagnosticReport) -> List[str]:
        """Generate fix suggestions based on diagnostic report."""
        fixes = []
        
        if not report.comfyui_found:
            fixes.append(
                f"1. Install ComfyUI at {report.comfyui_path}\n"
                "   OR update the path in ~/.synapse/config.json"
            )
        
        for issue in report.issues:
            if issue.suggestion:
                fixes.append(f"- {issue.message}: {issue.suggestion}")
        
        return fixes


def create_validator() -> PackValidator:
    """Factory function to create a PackValidator."""
    return PackValidator()


def create_doctor() -> SynapseDoctor:
    """Factory function to create a SynapseDoctor."""
    return SynapseDoctor()
