"""
Synapse Store CLI

Thin wrapper around Store API providing command-line interface.

Usage:
    synapse store init
    synapse status [--json]
    synapse use <pack> [--ui-set local] [--sync]
    synapse back [--ui-set local]
    synapse update <pack> [--dry-run] [--sync]
    synapse doctor [--rebuild-db auto|force|off]
    synapse search <query> [--json]
"""

from __future__ import annotations

import json as json_module
import sys
from pathlib import Path
from typing import List, Optional

import typer

from .models import UpdatePlan

app = typer.Typer(
    name="synapse",
    help="Synapse Store - ComfyUI Asset Manager",
    no_args_is_help=True,
)

store_app = typer.Typer(
    name="store",
    help="Store management commands",
)
app.add_typer(store_app, name="store")


def get_store():
    """Get or create Store instance."""
    from . import Store
    return Store()


def output_json(data: dict) -> None:
    """Output data as JSON."""
    typer.echo(json_module.dumps(data, indent=2, default=str))


def output_error(message: str) -> None:
    """Output error message."""
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)


def output_success(message: str) -> None:
    """Output success message."""
    typer.secho(message, fg=typer.colors.GREEN)


def output_warning(message: str) -> None:
    """Output warning message."""
    typer.secho(f"Warning: {message}", fg=typer.colors.YELLOW)


# =============================================================================
# Store Commands
# =============================================================================

@store_app.command("init")
def store_init(
    force: bool = typer.Option(False, "--force", "-f", help="Force reinitialize"),
):
    """Initialize the store."""
    store = get_store()
    
    if store.is_initialized() and not force:
        output_warning("Store already initialized. Use --force to reinitialize.")
        raise typer.Exit(0)
    
    store.init(force=force)
    output_success(f"Store initialized at {store.layout.root}")


@store_app.command("config")
def store_config(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show store configuration."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    config = store.get_config()
    
    if json:
        output_json(config.model_dump())
    else:
        typer.echo(f"Store root: {store.layout.root}")
        typer.echo(f"Default UI set: {config.defaults.ui_set}")
        typer.echo(f"Default profile: {config.defaults.active_profile}")
        typer.echo(f"UI targets: {', '.join(store.get_ui_targets())}")


# =============================================================================
# Pack Commands
# =============================================================================

@app.command("list")
def list_packs(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all packs."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    packs = store.list_packs()
    
    if json:
        output_json({"packs": packs})
    else:
        if not packs:
            typer.echo("No packs found.")
        else:
            typer.echo(f"Found {len(packs)} pack(s):")
            for name in sorted(packs):
                typer.echo(f"  - {name}")


@app.command("import")
def import_pack(
    url: str = typer.Argument(..., help="Civitai URL to import"),
    no_previews: bool = typer.Option(False, "--no-previews", help="Skip preview downloads"),
    no_add_global: bool = typer.Option(False, "--no-add-global", help="Don't add to global profile"),
):
    """Import a pack from Civitai URL."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    typer.echo(f"Importing from {url}...")
    
    try:
        pack = store.import_civitai(
            url,
            download_previews=not no_previews,
            add_to_global=not no_add_global,
        )
        output_success(f"Imported pack: {pack.name}")
        typer.echo(f"  Type: {pack.pack_type.value}")
        typer.echo(f"  Dependencies: {len(pack.dependencies)}")
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("install")
def install_pack(
    pack_name: str = typer.Argument(..., help="Pack name to install"),
):
    """Install blobs for a pack."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    typer.echo(f"Installing {pack_name}...")
    
    def progress(dep_id: str, downloaded: int, total: int):
        pct = (downloaded / total * 100) if total > 0 else 0
        typer.echo(f"  {dep_id}: {pct:.1f}% ({downloaded}/{total} bytes)")
    
    try:
        hashes = store.install(pack_name, progress_callback=progress)
        output_success(f"Installed {len(hashes)} blob(s)")
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("resolve")
def resolve_pack(
    pack_name: str = typer.Argument(..., help="Pack name to resolve"),
):
    """Resolve dependencies for a pack."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    typer.echo(f"Resolving {pack_name}...")
    
    def progress(dep_id: str, status: str):
        typer.echo(f"  {dep_id}: {status}")
    
    try:
        lock = store.resolve(pack_name, progress_callback=progress)
        output_success(f"Resolved {len(lock.resolved)} dependency(ies)")
        if lock.unresolved:
            output_warning(f"{len(lock.unresolved)} unresolved dependency(ies)")
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("delete")
def delete_pack(
    pack_name: str = typer.Argument(..., help="Pack name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force delete without confirmation"),
):
    """Delete a pack."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    if not force:
        confirm = typer.confirm(f"Delete pack '{pack_name}'?")
        if not confirm:
            raise typer.Abort()
    
    if store.delete_pack(pack_name):
        output_success(f"Deleted pack: {pack_name}")
    else:
        output_error(f"Pack not found: {pack_name}")
        raise typer.Exit(1)


# =============================================================================
# Profile Commands
# =============================================================================

@app.command("use")
def use_pack(
    pack_name: str = typer.Argument(..., help="Pack name to use"),
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set to use"),
    sync: bool = typer.Option(True, "--sync/--no-sync", help="Sync views after use"),
):
    """
    Activate a work profile for a pack.
    
    Creates work__<pack> profile and pushes it onto the stack.
    """
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    try:
        result = store.use(pack_name, ui_set=ui_set, sync=sync)
        output_success(f"Activated: {result.created_profile}")
        typer.echo(f"  Pack: {result.pack}")
        typer.echo(f"  UI targets: {', '.join(result.ui_targets)}")
        if result.notes:
            for note in result.notes:
                typer.echo(f"  Note: {note}")
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("back")
def back_command(
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set to use"),
    sync: bool = typer.Option(False, "--sync/--no-sync", help="Sync views after back"),
):
    """
    Go back to previous profile.
    
    Pops the current profile from the stack.
    """
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    try:
        result = store.back(ui_set=ui_set, sync=sync)
        output_success(f"Back: {result.from_profile} → {result.to_profile}")
        if result.notes:
            for note in result.notes:
                typer.echo(f"  Note: {note}")
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Status Command
# =============================================================================

@app.command("status")
def status_command(
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set to use"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show current store status."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    try:
        status = store.status(ui_set=ui_set)
        
        if json:
            output_json(status.model_dump())
        else:
            typer.echo(f"Profile: {status.profile}")
            typer.echo(f"UI targets: {', '.join(status.ui_targets)}")
            typer.echo()
            
            typer.echo("Active profiles:")
            for ui, profile in status.active.items():
                typer.echo(f"  {ui}: {profile}")
            
            if status.missing_blobs:
                typer.echo()
                output_warning(f"{len(status.missing_blobs)} missing blob(s):")
                for mb in status.missing_blobs:
                    typer.echo(f"  - {mb.pack}/{mb.dependency_id} ({mb.sha256[:12]}...)")
            
            if status.unresolved:
                typer.echo()
                output_warning(f"{len(status.unresolved)} unresolved dependency(ies):")
                for ur in status.unresolved:
                    typer.echo(f"  - {ur.pack}/{ur.dependency_id}: {ur.reason}")
            
            if status.shadowed:
                typer.echo()
                output_warning(f"{len(status.shadowed)} shadowed file(s):")
                for sh in status.shadowed:
                    typer.echo(f"  - {sh.dst_relpath}: {sh.winner_pack} shadows {sh.loser_pack}")
            
            if not status.missing_blobs and not status.unresolved:
                output_success("All dependencies resolved and downloaded.")
                
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Update Commands
# =============================================================================

@app.command("check-updates")
def check_updates_command(
    pack_name: Optional[str] = typer.Argument(None, help="Pack name to check (all if not specified)"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Check for available updates."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    try:
        plans = store.check_updates(pack_name)
        
        if json:
            output_json({k: v.model_dump() for k, v in plans.items()})
        else:
            has_updates = False
            for name, plan in plans.items():
                if plan.changes or plan.ambiguous:
                    has_updates = True
                    typer.echo(f"\n{name}:")
                    for change in plan.changes:
                        old_ver = change.old.get("provider_version_id", "unknown")
                        new_ver = change.new.get("provider_version_id", "unknown")
                        typer.echo(f"  {change.dependency_id}: {old_ver} → {new_ver}")
                    for amb in plan.ambiguous:
                        typer.echo(f"  {amb.dependency_id}: {len(amb.candidates)} candidates (ambiguous)")
            
            if not has_updates:
                output_success("All packs are up to date.")
                
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("update")
def update_command(
    pack_name: str = typer.Argument(..., help="Pack name to update"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Only show what would be done"),
    sync: bool = typer.Option(True, "--sync/--no-sync", help="Sync views after update"),
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set for sync"),
    choose: Optional[str] = typer.Option(None, "--choose", help="JSON dict of dep_id -> file_id for ambiguous"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Update a pack to latest versions."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    choose_dict = None
    if choose:
        try:
            choose_dict = json_module.loads(choose)
        except json_module.JSONDecodeError:
            output_error("Invalid JSON for --choose")
            raise typer.Exit(1)
    
    try:
        result = store.update(
            pack_name,
            dry_run=dry_run,
            choose=choose_dict,
            sync=sync,
            ui_set=ui_set,
        )
        
        if json:
            output_json(result.model_dump())
        else:
            if dry_run:
                typer.echo("Dry run - no changes applied")
            
            if result.applied:
                output_success(f"Applied {len(result.applied)} update(s)")
                for change in result.applied:
                    old_ver = change.old.get("provider_version_id", "unknown")
                    new_ver = change.new.get("provider_version_id", "unknown")
                    typer.echo(f"  {change.dependency_id}: {old_ver} → {new_ver}")
            
            if result.skipped:
                typer.echo(f"Skipped {len(result.skipped)} (already up to date)")
            
            if result.errors:
                output_error(f"{len(result.errors)} error(s):")
                for err in result.errors:
                    typer.echo(f"  - {err}")
                    
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Doctor Command
# =============================================================================

@app.command("doctor")
def doctor_command(
    rebuild_views: bool = typer.Option(False, "--rebuild-views", help="Rebuild all views"),
    rebuild_db: Optional[str] = typer.Option(None, "--rebuild-db", help="Rebuild DB: auto|force|off"),
    verify_blobs: bool = typer.Option(False, "--verify-blobs", help="Verify all blob hashes"),
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set for rebuilding"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run diagnostics and repairs."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    try:
        report = store.doctor(
            rebuild_views=rebuild_views,
            rebuild_db=rebuild_db,
            verify_blobs=verify_blobs,
            ui_set=ui_set,
        )
        
        if json:
            output_json(report.model_dump())
        else:
            typer.echo(f"Profile: {report.profile}")
            typer.echo(f"UI targets: {', '.join(report.ui_targets)}")
            typer.echo()
            
            typer.echo("Actions:")
            if report.actions.views_rebuilt:
                typer.echo("  ✓ Views rebuilt")
            if report.actions.db_rebuilt:
                typer.echo(f"  ✓ DB rebuilt ({report.actions.db_rebuilt})")
            if report.actions.blobs_verified:
                typer.echo("  ✓ Blobs verified")
            
            if report.notes:
                typer.echo()
                typer.echo("Notes:")
                for note in report.notes:
                    typer.echo(f"  - {note}")
            
            if report.missing_blobs:
                output_warning(f"{len(report.missing_blobs)} missing blob(s)")
            
            if report.unresolved:
                output_warning(f"{len(report.unresolved)} unresolved dependency(ies)")
                
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Search Command
# =============================================================================

@app.command("search")
def search_command(
    query: str = typer.Argument(..., help="Search query"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Search packs by name or metadata."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    try:
        result = store.search(query)
        
        if json:
            output_json(result.model_dump())
        else:
            if not result.items:
                typer.echo(f"No results for '{query}'")
            else:
                typer.echo(f"Found {len(result.items)} result(s) for '{query}':")
                for item in result.items:
                    typer.echo(f"  - {item.pack_name} ({item.pack_type})")
                    if item.provider:
                        typer.echo(f"    Provider: {item.provider}")
                    if item.source_url:
                        typer.echo(f"    URL: {item.source_url}")
                        
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Clean Command
# =============================================================================

@app.command("clean")
def clean_command(
    tmp: bool = typer.Option(True, "--tmp/--no-tmp", help="Clean tmp directory"),
    cache: bool = typer.Option(False, "--cache/--no-cache", help="Clean cache directory"),
    partial: bool = typer.Option(True, "--partial/--no-partial", help="Clean partial downloads"),
):
    """Clean temporary and cache files."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    try:
        result = store.clean(tmp=tmp, cache=cache, partial=partial)
        
        total = sum(result.values())
        output_success(f"Cleaned {total} item(s)")
        for key, count in result.items():
            if count > 0:
                typer.echo(f"  {key}: {count}")
                
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Sync Command
# =============================================================================

@app.command("sync")
def sync_command(
    profile: Optional[str] = typer.Argument(None, help="Profile to sync (active if not specified)"),
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set to use"),
    install: bool = typer.Option(True, "--install/--no-install", help="Install missing blobs"),
):
    """Sync a profile: install missing blobs and rebuild views."""
    store = get_store()
    
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)
    
    try:
        reports = store.sync(profile_name=profile, ui_set=ui_set, install_missing=install)
        
        output_success(f"Synced {len(reports)} UI(s)")
        for ui, report in reports.items():
            typer.echo(f"  {ui}: {report.entries_created} entries")
            if report.errors:
                for err in report.errors:
                    output_warning(f"    Error: {err}")
                    
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
