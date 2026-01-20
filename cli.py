#!/usr/bin/env python3
"""
Synapse CLI - The Pack-First Model Manager

Command-line interface for managing assets and workflows across ComfyUI, Forge, A1111, and SD.Next.

Usage:
    synapse init                          Initialize Synapse configuration
    synapse import <civitai-url>          Import pack from Civitai URL
    synapse import --workflow <file>      Import pack from workflow JSON
    synapse import --png <file>           Import pack from PNG with metadata
    synapse scan [--folder <path>]        Scan local assets
    synapse install <pack-name>           Install a pack
    synapse list [--installed]            List all packs
    synapse info <pack-name>              Show pack details
    synapse validate <pack-name>          Validate pack integrity
    synapse run <pack-name> [--workflow]  Generate derived workflow
    synapse doctor                        Run system diagnostics
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import get_config, SynapseConfig
from src.core.models import Pack, AssetType
from src.core.pack_builder import PackBuilder
from src.core.installer import PackInstaller, InstallStatus
from src.core.registry import PackRegistry
from src.core.validator import PackValidator, SynapseDoctor
# from src.workflows.generator import DerivedWorkflowGenerator
from src.workflows.scanner import WorkflowScanner


class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD_MAGENTA = "\033[1;35m"


# Synapse CLI icon
HEX_ICON = "⬢"
    

def print_header(text: str) -> None:
    """Print a styled header."""
    print(f"\n{Colors.BOLD_MAGENTA}{HEX_ICON}{Colors.RESET} {Colors.BOLD}{text}{Colors.RESET}")
    print(f"{Colors.CYAN}{'─'*60}{Colors.RESET}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"{Colors.BOLD_MAGENTA}{HEX_ICON}{Colors.RESET} {text}")


def progress_callback(message: str, progress: float) -> None:
    """Display download progress."""
    bar_width = 40
    filled = int(bar_width * progress)
    bar = "█" * filled + "░" * (bar_width - filled)
    percent = int(progress * 100)
    print(f"\r  [{bar}] {percent:3d}% - {message[:40]:<40}", end="", flush=True)
    if progress >= 1.0:
        print()


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize Synapse configuration."""
    print_header("Synapse Initialization")
    
    config = get_config()
    
    # Create directories
    config.packs_path.mkdir(parents=True, exist_ok=True)
    config.registry_path.mkdir(parents=True, exist_ok=True)
    config.cache_path.mkdir(parents=True, exist_ok=True)
    
    # Save default config
    config.save()
    
    print_success(f"Created configuration at: {config.config_file}")
    print_success(f"Packs directory: {config.packs_path}")
    print_success(f"ComfyUI path: {config.comfyui.base_path}")
    
    # Validate ComfyUI installation
    if config.comfyui.base_path.exists():
        print_success("ComfyUI installation found")
    else:
        print_warning(f"ComfyUI not found at {config.comfyui.base_path}")
        print_info("Update config.json with correct ComfyUI path")
    
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    """Import a pack from various sources."""
    print_header("Synapse Import")
    
    config = get_config()
    builder = PackBuilder(config)
    registry = PackRegistry(config)
    
    # Determine source type
    if args.workflow:
        # Import from workflow JSON
        workflow_path = Path(args.workflow)
        if not workflow_path.exists():
            print_error(f"Workflow file not found: {workflow_path}")
            return 1
        
        print_info(f"Importing from workflow: {workflow_path}")
        result = builder.build_from_workflow(workflow_path)
        
    elif args.png:
        # Import from PNG metadata
        png_path = Path(args.png)
        if not png_path.exists():
            print_error(f"PNG file not found: {png_path}")
            return 1
        
        print_info(f"Importing from PNG: {png_path}")
        result = builder.build_from_png_metadata(png_path)
        
    elif args.url:
        # Import from Civitai URL
        print_info(f"Importing from URL: {args.url}")
        result = builder.build_from_civitai_url(args.url)
        
    else:
        print_error("No source specified. Use --workflow, --png, or provide a URL")
        return 1
    
    if not result.success:
        print_error("Import failed:")
        for error in result.errors:
            print_error(f"  {error}")
        return 1
    
    # Show warnings if any
    for warning in result.warnings:
        print_warning(warning)
    
    # Register the pack
    pack = result.pack
    pack_dir = registry.get_pack_directory(pack.metadata.name)
    entry = registry.register_pack(pack, pack_dir)
    
    # Copy workflow files to pack directory
    import shutil
    if pack.workflows:
        workflows_dir = pack_dir / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy from source
        if args.workflow:
            src_path = Path(args.workflow)
            if src_path.exists():
                dst_path = workflows_dir / src_path.name
                shutil.copy2(src_path, dst_path)
        elif args.png:
            # PNG workflow was extracted - it's stored in pack.docs
            pass
    
    print_success(f"Pack created: {pack.metadata.name} v{pack.metadata.version}")
    print_info(f"Location: {pack_dir}")
    
    # Show summary
    print(f"\n{Colors.BOLD}Pack Summary:{Colors.RESET}")
    print(f"  Dependencies: {len(pack.dependencies)}")
    print(f"  Custom Nodes: {len(pack.custom_nodes)}")
    print(f"  Workflows: {len(pack.workflows)}")
    print(f"  Previews: {len(pack.previews)}")
    
    if pack.dependencies:
        print(f"\n{Colors.BOLD}Assets:{Colors.RESET}")
        for dep in pack.dependencies[:5]:
            print(f"  • {dep.name} ({dep.asset_type.value})")
        if len(pack.dependencies) > 5:
            print(f"  ... and {len(pack.dependencies) - 5} more")
    
    print_info("\nRun 'synapse install <pack-name>' to download assets")
    
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan local assets or workflow files."""
    print_header("Synapse Scan")
    
    config = get_config()
    
    if args.workflow:
        # Scan a workflow file
        workflow_path = Path(args.workflow)
        if not workflow_path.exists():
            print_error(f"Workflow file not found: {workflow_path}")
            return 1
        
        scanner = WorkflowScanner()
        result = scanner.scan_file(workflow_path)
        
        # Get deduplicated assets
        unique_assets = scanner.get_unique_assets(result)
        
        print_info(f"Scanned: {workflow_path.name}")
        print(f"\n{Colors.BOLD}Found Assets:{Colors.RESET}")
        
        # Group by type
        by_type = {}
        for asset in unique_assets:
            type_name = asset.asset_type.value
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(asset)
        
        for type_name, assets in sorted(by_type.items()):
            print(f"\n  {Colors.CYAN}{type_name}:{Colors.RESET}")
            for asset in assets:
                print(f"    • {asset.name}")
        
        if result.custom_node_types:
            print(f"\n{Colors.BOLD}Custom Nodes:{Colors.RESET}")
            for node_type in sorted(result.custom_node_types)[:10]:
                print(f"  • {node_type}")
            if len(result.custom_node_types) > 10:
                print(f"  ... and {len(result.custom_node_types) - 10} more")
        
        return 0
    
    # Scan local ComfyUI installation
    builder = PackBuilder(config)
    
    scan_types = None
    if args.type:
        try:
            scan_types = [AssetType(args.type)]
        except ValueError:
            print_error(f"Invalid asset type: {args.type}")
            print_info(f"Valid types: {', '.join(t.value for t in AssetType)}")
            return 1
    
    print_info(f"Scanning: {config.comfyui.base_path}")
    result = builder.build_from_local_scan(asset_types=scan_types)
    
    if not result.success:
        print_error("Scan failed")
        for error in result.errors:
            print_error(f"  {error}")
        return 1
    
    pack = result.pack
    print_success(f"Found {len(pack.dependencies)} assets")
    
    # Group by type
    by_type = {}
    for dep in pack.dependencies:
        type_name = dep.asset_type.value
        if type_name not in by_type:
            by_type[type_name] = []
        by_type[type_name].append(dep)
    
    print(f"\n{Colors.BOLD}Assets by Type:{Colors.RESET}")
    for type_name, deps in sorted(by_type.items()):
        print(f"  {type_name}: {len(deps)}")
    
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """Install a pack's dependencies."""
    print_header("Synapse Install")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(args.pack_name)
    if not pack:
        print_error(f"Pack not found: {args.pack_name}")
        print_info("Use 'synapse list' to see available packs")
        return 1
    
    print_info(f"Installing: {pack.metadata.name} v{pack.metadata.version}")
    
    installer = PackInstaller(config)
    
    # Install with progress callback
    result = installer.install_pack(
        pack,
        skip_existing=args.skip_existing,
        progress_callback=progress_callback if not args.quiet else None
    )
    
    if result.success:
        print_success(f"\nInstallation complete!")
        print(f"  Downloaded: {result.downloaded_count}")
        print(f"  Skipped: {result.skipped_count}")
        print(f"  Failed: {result.failed_count}")
        
        # Save lock and update registry
        pack_dir = registry.registry.entries[pack.metadata.name].pack_path
        registry.mark_installed(pack.metadata.name, result.lock)
        
        return 0
    else:
        print_error("\nInstallation failed:")
        for error in result.errors:
            print_error(f"  {error}")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List all registered packs."""
    print_header("Synapse Packs")
    
    config = get_config()
    registry = PackRegistry(config)
    registry.scan_packs_directory()
    
    entries = registry.list_packs(installed_only=args.installed)
    
    if not entries:
        print_info("No packs found")
        print_info("Use 'synapse import <url>' to add a pack")
        return 0
    
    print(f"{'Name':<30} {'Version':<10} {'Status':<12} {'Source'}")
    print("-" * 80)
    
    for entry in entries:
        status = f"{Colors.GREEN}Installed{Colors.RESET}" if entry.installed else "Pending"
        source = entry.source_url[:35] + "..." if entry.source_url and len(entry.source_url) > 38 else (entry.source_url or "Local")
        print(f"{entry.name:<30} {entry.version:<10} {status:<21} {source}")
    
    print(f"\nTotal: {len(entries)} packs")
    
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show detailed pack information."""
    print_header(f"Pack: {args.pack_name}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(args.pack_name)
    if not pack:
        print_error(f"Pack not found: {args.pack_name}")
        return 1
    
    entry = registry.registry.entries.get(args.pack_name)
    
    # Metadata
    print(f"{Colors.BOLD}Metadata:{Colors.RESET}")
    print(f"  Name: {pack.metadata.name}")
    print(f"  Version: {pack.metadata.version}")
    print(f"  Description: {pack.metadata.description or 'N/A'}")
    print(f"  Author: {pack.metadata.author or 'Unknown'}")
    print(f"  Created: {pack.metadata.created_at or 'N/A'}")
    if pack.metadata.tags:
        print(f"  Tags: {', '.join(pack.metadata.tags)}")
    
    # Status
    print(f"\n{Colors.BOLD}Status:{Colors.RESET}")
    if entry and entry.installed:
        print(f"  {Colors.GREEN}✓ Installed{Colors.RESET}")
        print(f"  Installed at: {entry.installed_at}")
    else:
        print(f"  {Colors.YELLOW}○ Not installed{Colors.RESET}")
    
    # Dependencies
    if pack.dependencies:
        print(f"\n{Colors.BOLD}Dependencies ({len(pack.dependencies)}):{Colors.RESET}")
        for dep in pack.dependencies:
            source = dep.source.value if dep.source else "unknown"
            print(f"  • {dep.name} ({dep.asset_type.value}) - {source}")
    
    # Custom nodes
    if pack.custom_nodes:
        print(f"\n{Colors.BOLD}Custom Nodes ({len(pack.custom_nodes)}):{Colors.RESET}")
        for node in pack.custom_nodes:
            print(f"  • {node.name or node.git_url}")
    
    # Workflows
    if pack.workflows:
        print(f"\n{Colors.BOLD}Workflows ({len(pack.workflows)}):{Colors.RESET}")
        for wf in pack.workflows:
            print(f"  • {wf.filename}")
    
    # Previews
    if pack.previews:
        nsfw_count = sum(1 for p in pack.previews if p.nsfw)
        print(f"\n{Colors.BOLD}Previews ({len(pack.previews)}):{Colors.RESET}")
        print(f"  Safe: {len(pack.previews) - nsfw_count}, NSFW: {nsfw_count}")
    
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate pack integrity."""
    print_header(f"Validating: {args.pack_name}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(args.pack_name)
    if not pack:
        print_error(f"Pack not found: {args.pack_name}")
        return 1
    
    entry = registry.registry.entries.get(args.pack_name)
    if not entry:
        print_error(f"Pack not in registry: {args.pack_name}")
        return 1
    
    pack_dir = entry.pack_path
    
    validator = PackValidator(config)
    result = validator.validate_pack(pack, pack_dir, check_hashes=args.verify_hashes)
    
    if result.valid:
        print_success("Pack is valid!")
    else:
        print_error("Validation failed")
    
    # Show issues by level
    from src.core.validator import IssueLevel
    
    for level in [IssueLevel.CRITICAL, IssueLevel.ERROR, IssueLevel.WARNING, IssueLevel.INFO]:
        issues = [i for i in result.issues if i.level == level]
        if issues:
            color = {
                IssueLevel.CRITICAL: Colors.RED,
                IssueLevel.ERROR: Colors.RED,
                IssueLevel.WARNING: Colors.YELLOW,
                IssueLevel.INFO: Colors.BLUE,
            }[level]
            
            print(f"\n{color}{level.value.upper()}:{Colors.RESET}")
            for issue in issues:
                print(f"  • {issue.message}")
                if issue.suggestion:
                    print(f"    → {issue.suggestion}")
    
    return 0 if result.valid else 1


def cmd_run(args: argparse.Namespace) -> int:
    """Generate derived workflow for execution."""
    print_header(f"Running: {args.pack_name}")
    
    config = get_config()
    registry = PackRegistry(config)
    
    pack = registry.get_pack(args.pack_name)
    if not pack:
        print_error(f"Pack not found: {args.pack_name}")
        return 1
    
    entry = registry.registry.entries.get(args.pack_name)
    if not entry or not entry.installed:
        print_error("Pack is not installed")
        print_info("Run 'synapse install <pack-name>' first")
        return 1
    
    if not pack.workflows:
        print_error("Pack has no workflows")
        return 1
    
    # Select workflow
    workflow_idx = 0
    if args.workflow:
        for idx, wf in enumerate(pack.workflows):
            if wf.filename == args.workflow or str(idx) == args.workflow:
                workflow_idx = idx
                break
        else:
            print_error(f"Workflow not found: {args.workflow}")
            print_info("Available workflows:")
            for idx, wf in enumerate(pack.workflows):
                print(f"  [{idx}] {wf.filename}")
            return 1
    
    workflow_info = pack.workflows[workflow_idx]
    
    # Load upstream workflow
    pack_dir = entry.pack_path
    workflow_path = pack_dir / "workflows" / workflow_info.filename
    
    if not workflow_path.exists():
        print_error(f"Workflow file not found: {workflow_path}")
        return 1
    
    with open(workflow_path, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    

    # generator = DerivedWorkflowGenerator(config)
    
    # run_config = pack.run_config
    # if args.prefix:
    #     run_config.output_prefix = args.prefix
    # if args.subfolder:
    #     run_config.output_subfolder = args.subfolder
    
    # result = generator.generate_derived(workflow, pack, run_config)
    
    # # Save derived workflow
    # output_path = pack_dir / "workflows" / f"derived_{workflow_info.filename}"
    # generator.save_derived(result, output_path)
    
    # print_success(f"Generated: {output_path}")
    
    # # Show patches applied
    # if result.patches:
    #     print(f"\n{Colors.BOLD}Patches Applied:{Colors.RESET}")
    #     for patch in result.patches:
    #         print(f"  • {patch.node_id}: {patch.original_value} → {patch.new_value}")
    
    # print_info(f"\nLoad in ComfyUI: {output_path}")
    
    print_error("Derived workflow generation is currently unavailable (DerivedWorkflowGenerator missing).")
    return 1


def cmd_doctor(args: argparse.Namespace) -> int:
    """Run system diagnostics."""
    print_header("Synapse Doctor")
    
    config = get_config()
    doctor = SynapseDoctor(config)
    
    print_info("Running diagnostics...")
    report = doctor.run_diagnostics()
    
    # ComfyUI status
    print(f"\n{Colors.BOLD}ComfyUI:{Colors.RESET}")
    if report.comfyui_found:
        print_success(f"Installation found at: {report.comfyui_path}")
    else:
        print_error(f"Not found at: {report.comfyui_path}")
    
    # Model directories
    print(f"\n{Colors.BOLD}Model Directories:{Colors.RESET}")
    for dir_name, count in report.models_found.items():
        if count >= 0:
            print_success(f"{dir_name}: {count} files")
        else:
            print_warning(f"{dir_name}: not found")
    
    # Custom nodes
    print(f"\n{Colors.BOLD}Custom Nodes:{Colors.RESET}")
    print(f"  Found: {report.custom_nodes_found}")
    
    # Registry
    print(f"\n{Colors.BOLD}Registry:{Colors.RESET}")
    if report.packs_registered >= 0:
        print_success(f"Valid ({report.packs_registered} packs, {report.packs_installed} installed)")
    else:
        print_warning("Not initialized")
    
    # Issues
    if report.issues:
        print(f"\n{Colors.BOLD}Issues Found:{Colors.RESET}")
        for issue in report.issues:
            if issue.level.value in ("critical", "error"):
                print_error(f"{issue.message}")
            else:
                print_warning(f"{issue.message}")
            if issue.suggestion:
                print_info(f"  → {issue.suggestion}")
    
    # Suggestions
    if args.fix:
        print(f"\n{Colors.BOLD}Applying Fixes:{Colors.RESET}")
        suggestions = doctor.suggest_fixes(report)
        for suggestion in suggestions:
            print_info(suggestion)
    
    return 0 if report.comfyui_found and report.packs_registered >= 0 else 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="synapse",
        description=f"{Colors.BOLD_MAGENTA}{HEX_ICON}{Colors.RESET} {Colors.BOLD}Synapse{Colors.RESET} - Pack-first model manager for generative UIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"{Colors.BOLD_MAGENTA}{HEX_ICON}{Colors.RESET} {Colors.BOLD}Synapse{Colors.RESET} v2.1.8"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # init
    init_parser = subparsers.add_parser("init", help="Initialize Synapse configuration")
    init_parser.set_defaults(func=cmd_init)
    
    # import
    import_parser = subparsers.add_parser("import", help="Import a pack from various sources")
    import_parser.add_argument("url", nargs="?", help="Civitai model URL")
    import_parser.add_argument("--workflow", "-w", help="Import from workflow JSON file")
    import_parser.add_argument("--png", "-p", help="Import from PNG with embedded metadata")
    import_parser.set_defaults(func=cmd_import)
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Scan local assets or workflows")
    scan_parser.add_argument("--workflow", "-w", help="Scan a workflow file")
    scan_parser.add_argument("--type", "-t", help="Filter by asset type")
    scan_parser.set_defaults(func=cmd_scan)
    
    # install
    install_parser = subparsers.add_parser("install", help="Install a pack's dependencies")
    install_parser.add_argument("pack_name", help="Name of the pack to install")
    install_parser.add_argument("--skip-existing", "-s", action="store_true", help="Skip existing files")
    install_parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    install_parser.set_defaults(func=cmd_install)
    
    # list
    list_parser = subparsers.add_parser("list", help="List all registered packs")
    list_parser.add_argument("--installed", "-i", action="store_true", help="Show only installed packs")
    list_parser.set_defaults(func=cmd_list)
    
    # info
    info_parser = subparsers.add_parser("info", help="Show pack details")
    info_parser.add_argument("pack_name", help="Name of the pack")
    info_parser.set_defaults(func=cmd_info)
    
    # validate
    validate_parser = subparsers.add_parser("validate", help="Validate pack integrity")
    validate_parser.add_argument("pack_name", help="Name of the pack")
    validate_parser.add_argument("--verify-hashes", "-H", action="store_true", help="Verify file hashes")
    validate_parser.set_defaults(func=cmd_validate)
    
    # run
    run_parser = subparsers.add_parser("run", help="Generate derived workflow")
    run_parser.add_argument("pack_name", help="Name of the pack")
    run_parser.add_argument("--workflow", "-w", help="Workflow name or index")
    run_parser.add_argument("--prefix", "-p", help="Output filename prefix")
    run_parser.add_argument("--subfolder", "-s", help="Output subfolder")
    run_parser.set_defaults(func=cmd_run)
    
    # doctor
    doctor_parser = subparsers.add_parser("doctor", help="Run system diagnostics")
    doctor_parser.add_argument("--fix", "-f", action="store_true", help="Apply suggested fixes")
    doctor_parser.set_defaults(func=cmd_doctor)
    
    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 0
    
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled")
        return 130
    except Exception as e:
        print_error(f"Error: {e}")
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
