"""
Synapse Store CLI

Professional command-line interface for Synapse Store.

Usage:
    synapse store init          Initialize the store
    synapse list                List all packs
    synapse show <pack>         Show pack details
    synapse import <url>        Import from Civitai
    synapse use <pack>          Activate a pack
    synapse back                Go to previous profile
    synapse reset               Reset to global profile
    synapse status              Show current status
    synapse attach              Attach UIs to store
    synapse detach              Detach UIs from store
"""

from __future__ import annotations

import json as json_module
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .models import (
    AssetKind,
    BackupConfig,
    BlobLocation,
    BlobStatus,
    UpdatePlan,
)

# =============================================================================
# Console Setup
# =============================================================================

console = Console()
err_console = Console(stderr=True)

app = typer.Typer(
    name="synapse",
    help="🧠 Synapse Store - Professional ComfyUI Asset Manager",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

store_app = typer.Typer(
    name="store",
    help="Store management commands",
)
app.add_typer(store_app, name="store")

profiles_app = typer.Typer(
    name="profiles",
    help="Profile management commands",
)
app.add_typer(profiles_app, name="profiles")

inventory_app = typer.Typer(
    name="inventory",
    help="Blob inventory management",
)
app.add_typer(inventory_app, name="inventory")

backup_app = typer.Typer(
    name="backup",
    help="Backup storage management",
)
app.add_typer(backup_app, name="backup")


# =============================================================================
# Helper Functions
# =============================================================================

def get_store():
    """Get or create Store instance."""
    from . import Store
    return Store()


def output_json(data: dict) -> None:
    """Output data as JSON."""
    console.print_json(json_module.dumps(data, default=str))


def output_error(message: str) -> None:
    """Output error message with styling."""
    err_console.print(f"[bold red]✗ Error:[/bold red] {message}")


def output_success(message: str) -> None:
    """Output success message with styling."""
    console.print(f"[bold green]✓[/bold green] {message}")


def output_warning(message: str) -> None:
    """Output warning message with styling."""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def output_info(message: str) -> None:
    """Output info message."""
    console.print(f"[dim]ℹ[/dim] {message}")


def output_header(title: str, subtitle: str = "") -> None:
    """Output a styled header."""
    text = Text()
    text.append("🧠 ", style="bold")
    text.append(title, style="bold cyan")
    if subtitle:
        text.append(f" • {subtitle}", style="dim")
    console.print(text)
    console.print()


def require_initialized(store) -> None:
    """Check if store is initialized, exit if not."""
    if not store.is_initialized():
        output_error("Store not initialized. Run 'synapse store init' first.")
        raise typer.Exit(1)


# =============================================================================
# Store Commands
# =============================================================================

@store_app.command("init")
def store_init(
    force: bool = typer.Option(False, "--force", "-f", help="Force reinitialize"),
):
    """Initialize the Synapse store."""
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
    require_initialized(store)

    config = store.get_config()

    if json:
        output_json(config.model_dump())
    else:
        table = Table(title="Store Configuration", box=box.ROUNDED)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Store root", str(store.layout.root))
        table.add_row("Default UI set", config.defaults.ui_set)
        table.add_row("Default profile", config.defaults.active_profile)
        table.add_row("UI targets", ", ".join(store.get_ui_targets()))

        console.print(table)


# =============================================================================
# Pack Commands
# =============================================================================

@app.command("list")
def list_packs(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all installed packs."""
    store = get_store()
    require_initialized(store)

    packs = store.list_packs()

    if json:
        output_json({"packs": packs})
    else:
        if not packs:
            output_info("No packs installed.")
            console.print("\n[dim]Import a pack with:[/dim] synapse import <civitai-url>")
        else:
            table = Table(title=f"Installed Packs ({len(packs)})", box=box.ROUNDED)
            table.add_column("#", style="dim", width=4)
            table.add_column("Pack Name", style="cyan bold")
            table.add_column("Type", style="green")
            table.add_column("Dependencies", justify="right")

            for i, name in enumerate(sorted(packs), 1):
                try:
                    pack = store.layout.load_pack(name)
                    pack_type = pack.pack_type.value if hasattr(pack.pack_type, 'value') else str(pack.pack_type)
                    deps = str(len(pack.dependencies))
                except Exception:
                    pack_type = "?"
                    deps = "?"
                table.add_row(str(i), name, pack_type, deps)

            console.print(table)


@app.command("show")
def show_pack(
    pack_name: str = typer.Argument(..., help="Pack name to show"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show detailed information about a pack."""
    store = get_store()
    require_initialized(store)

    try:
        pack = store.layout.load_pack(pack_name)
        lock = store.layout.load_pack_lock(pack_name)
    except Exception as e:
        output_error(f"Pack not found: {pack_name}")
        raise typer.Exit(1)

    if json:
        output_json({
            "pack": pack.model_dump(),
            "lock": lock.model_dump() if lock else None,
        })
    else:
        # Header
        console.print(Panel(
            f"[bold cyan]{pack.name}[/bold cyan]\n"
            f"[dim]Type:[/dim] {pack.pack_type.value}",
            title="Pack Details",
            box=box.ROUNDED,
        ))

        # Source info
        if pack.source:
            console.print(f"\n[bold]Source:[/bold]")
            console.print(f"  Provider: [green]{pack.source.provider.value}[/green]")
            if pack.source.model_id:
                console.print(f"  Model ID: {pack.source.model_id}")
            if pack.source.url:
                console.print(f"  URL: [link]{pack.source.url}[/link]")

        # Dependencies
        if pack.dependencies:
            console.print(f"\n[bold]Dependencies ({len(pack.dependencies)}):[/bold]")
            table = Table(box=box.SIMPLE)
            table.add_column("ID", style="cyan")
            table.add_column("Kind", style="green")
            table.add_column("Filename")
            table.add_column("Status", justify="center")

            for dep in pack.dependencies:
                filename = dep.expose.filename if dep.expose else "-"
                # Check if resolved
                status = "❓"
                if lock:
                    resolved = next((r for r in lock.resolved if r.dependency_id == dep.id), None)
                    if resolved:
                        blob_exists = store.blob_store.blob_exists(resolved.artifact.sha256)
                        status = "[green]✓[/green]" if blob_exists else "[yellow]⬇[/yellow]"

                table.add_row(dep.id, dep.kind.value, filename, status)

            console.print(table)
        else:
            console.print("\n[dim]No dependencies[/dim]")


@app.command("import")
def import_pack(
    url: str = typer.Argument(..., help="Civitai URL to import"),
    no_previews: bool = typer.Option(False, "--no-previews", help="Skip preview downloads"),
    no_add_global: bool = typer.Option(False, "--no-add-global", help="Don't add to global profile"),
):
    """Import a pack from Civitai URL."""
    store = get_store()
    require_initialized(store)

    console.print(f"[dim]Importing from {url}...[/dim]")

    try:
        pack = store.import_civitai(
            url,
            download_previews=not no_previews,
            add_to_global=not no_add_global,
        )
        output_success(f"Imported pack: [bold]{pack.name}[/bold]")
        console.print(f"  Type: [green]{pack.pack_type.value}[/green]")
        console.print(f"  Dependencies: {len(pack.dependencies)}")
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("install")
def install_pack(
    pack_name: str = typer.Argument(..., help="Pack name to install"),
):
    """Download and install blobs for a pack."""
    store = get_store()
    require_initialized(store)

    console.print(f"[dim]Installing {pack_name}...[/dim]")

    def progress(dep_id: str, downloaded: int, total: int):
        pct = (downloaded / total * 100) if total > 0 else 0
        console.print(f"  [cyan]{dep_id}[/cyan]: {pct:.1f}%", end="\r")

    try:
        hashes = store.install(pack_name, progress_callback=progress)
        console.print()  # Clear progress line
        output_success(f"Installed {len(hashes)} blob(s)")
    except Exception as e:
        console.print()
        output_error(str(e))
        raise typer.Exit(1)


@app.command("resolve")
def resolve_pack(
    pack_name: str = typer.Argument(..., help="Pack name to resolve"),
):
    """Resolve dependencies for a pack."""
    store = get_store()
    require_initialized(store)

    console.print(f"[dim]Resolving {pack_name}...[/dim]")

    def progress(dep_id: str, status: str):
        console.print(f"  [cyan]{dep_id}[/cyan]: {status}")

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
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Delete a pack and clean up associated resources."""
    store = get_store()
    require_initialized(store)

    if not force and not json:
        confirm = typer.confirm(f"Delete pack '{pack_name}'?")
        if not confirm:
            raise typer.Abort()

    result = store.delete_pack(pack_name)

    if json:
        output_json(result.model_dump())
    else:
        if result.deleted:
            output_success(f"Deleted pack: [bold]{pack_name}[/bold]")
            if result.cleanup_warnings:
                for warning in result.cleanup_warnings:
                    output_warning(warning)
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
    """Activate a work profile for a pack."""
    store = get_store()
    require_initialized(store)

    try:
        result = store.use(pack_name, ui_set=ui_set, sync=sync)
        output_success(f"Activated: [bold cyan]{result.created_profile}[/bold cyan]")
        console.print(f"  Pack: [green]{result.pack}[/green]")
        console.print(f"  UIs: {', '.join(result.ui_targets)}")
        if result.shadowed:
            output_warning(f"{len(result.shadowed)} shadowed file(s)")
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("back")
def back_command(
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set to use"),
    sync: bool = typer.Option(False, "--sync/--no-sync", help="Sync views after back"),
):
    """Go back to previous profile."""
    store = get_store()
    require_initialized(store)

    try:
        result = store.back(ui_set=ui_set, sync=sync)
        if "already_at_base" in result.notes:
            output_info(f"Already at base profile: [cyan]{result.to_profile}[/cyan]")
        else:
            output_success(f"Back: [dim]{result.from_profile}[/dim] → [bold cyan]{result.to_profile}[/bold cyan]")
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("reset")
def reset_command(
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set to use"),
    sync: bool = typer.Option(False, "--sync/--no-sync", help="Sync views after reset"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Reset stack to global for all UIs."""
    store = get_store()
    require_initialized(store)

    try:
        result = store.reset(ui_set=ui_set, sync=sync)

        if json:
            output_json(result.model_dump())
        else:
            if "already_at_global" in result.notes:
                output_info("Already at global profile")
            else:
                output_success(f"Reset to: [bold cyan]{result.to_profile}[/bold cyan]")
                for ui, from_profile in result.from_profiles.items():
                    if from_profile != "global":
                        console.print(f"  {ui}: [dim]{from_profile}[/dim] → [green]global[/green]")
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@profiles_app.command("list")
def list_profiles(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all profiles."""
    store = get_store()
    require_initialized(store)

    profiles = store.list_profiles()

    if json:
        output_json({"profiles": profiles})
    else:
        # Get active profiles
        runtime = store.layout.load_runtime()

        table = Table(title=f"Profiles ({len(profiles)})", box=box.ROUNDED)
        table.add_column("Profile", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Active In")

        for name in sorted(profiles):
            # Determine type
            if name == "global":
                ptype = "base"
            elif name.startswith("work__"):
                ptype = "work"
            else:
                ptype = "custom"

            # Check where it's active
            active_in = []
            for ui, state in runtime.ui.items():
                if state.stack and state.stack[-1] == name:
                    active_in.append(ui)

            active_str = ", ".join(active_in) if active_in else "[dim]-[/dim]"
            table.add_row(name, ptype, active_str)

        console.print(table)


@profiles_app.command("show")
def show_profile(
    profile_name: str = typer.Argument(..., help="Profile name"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show profile details."""
    store = get_store()
    require_initialized(store)

    try:
        profile = store.layout.load_profile(profile_name)
    except Exception:
        output_error(f"Profile not found: {profile_name}")
        raise typer.Exit(1)

    if json:
        output_json(profile.model_dump())
    else:
        console.print(Panel(
            f"[bold cyan]{profile.name}[/bold cyan]",
            title="Profile Details",
            box=box.ROUNDED,
        ))

        if profile.packs:
            console.print(f"\n[bold]Packs ({len(profile.packs)}):[/bold]")
            for i, pack_entry in enumerate(profile.packs, 1):
                enabled = "[green]✓[/green]" if pack_entry.enabled else "[red]✗[/red]"
                console.print(f"  {i}. {enabled} [cyan]{pack_entry.name}[/cyan]")
        else:
            console.print("\n[dim]No packs in this profile[/dim]")


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
    require_initialized(store)

    try:
        status = store.status(ui_set=ui_set)

        if json:
            output_json(status.model_dump())
        else:
            output_header("Synapse Status")

            # Active profiles
            table = Table(box=box.ROUNDED, show_header=True)
            table.add_column("UI", style="cyan")
            table.add_column("Active Profile", style="green")

            for ui, profile in status.active.items():
                table.add_row(ui, profile)

            console.print(table)

            # Issues
            if status.missing_blobs:
                console.print()
                output_warning(f"{len(status.missing_blobs)} missing blob(s)")
                for mb in status.missing_blobs[:5]:
                    console.print(f"  [dim]•[/dim] {mb.pack}/{mb.dependency_id}")
                if len(status.missing_blobs) > 5:
                    console.print(f"  [dim]... and {len(status.missing_blobs) - 5} more[/dim]")

            if status.unresolved:
                console.print()
                output_warning(f"{len(status.unresolved)} unresolved dependency(ies)")

            if status.shadowed:
                console.print()
                output_info(f"{len(status.shadowed)} shadowed file(s) (last pack wins)")

            if not status.missing_blobs and not status.unresolved:
                console.print()
                output_success("All dependencies resolved and installed")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# UI Attachment Commands
# =============================================================================

@app.command("attach")
def attach_command(
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set to attach"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Attach UIs to Synapse views (create symlinks)."""
    store = get_store()
    require_initialized(store)

    try:
        results = store.attach_uis(ui_set=ui_set)

        if json:
            output_json(results)
        else:
            output_header("UI Attachment")

            all_success = all(r.get("success", False) for r in results.values())

            for ui, result in results.items():
                if result.get("success"):
                    method = result.get("method", "unknown")
                    console.print(f"  [green]✓[/green] [cyan]{ui}[/cyan] → attached ({method})")
                else:
                    errors = result.get("errors", [])
                    console.print(f"  [red]✗[/red] [cyan]{ui}[/cyan] → failed")
                    for err in errors:
                        console.print(f"    [dim]{err}[/dim]")

            if all_success:
                console.print()
                output_success("All UIs attached successfully")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("detach")
def detach_command(
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set to detach"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Detach UIs from Synapse views (remove symlinks)."""
    store = get_store()
    require_initialized(store)

    try:
        results = store.detach_uis(ui_set=ui_set)

        if json:
            output_json(results)
        else:
            output_header("UI Detachment")

            for ui, result in results.items():
                if result.get("success"):
                    console.print(f"  [green]✓[/green] [cyan]{ui}[/cyan] → detached")
                else:
                    errors = result.get("errors", [])
                    console.print(f"  [red]✗[/red] [cyan]{ui}[/cyan] → failed")
                    for err in errors:
                        console.print(f"    [dim]{err}[/dim]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("attach-status")
def attach_status_command(
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set to check"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show UI attachment status."""
    store = get_store()
    require_initialized(store)

    try:
        results = store.get_attach_status(ui_set=ui_set)

        if json:
            output_json(results)
        else:
            output_header("UI Attachment Status")

            table = Table(box=box.ROUNDED)
            table.add_column("UI", style="cyan")
            table.add_column("Attached")
            table.add_column("Method")
            table.add_column("Path")

            for ui, status in results.items():
                attached = "[green]✓ Yes[/green]" if status.get("attached") else "[dim]✗ No[/dim]"
                method = status.get("method", "-")
                path = status.get("link_path", "-")
                if len(str(path)) > 40:
                    path = "..." + str(path)[-37:]
                table.add_row(ui, attached, method, str(path))

            console.print(table)

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Update Commands
# =============================================================================

@app.command("check-updates")
def check_updates(
    pack_name: str = typer.Argument(..., help="Pack name to check"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Check for updates on a specific pack."""
    store = get_store()
    require_initialized(store)

    try:
        plan = store.check_updates(pack_name)

        if json:
            output_json(plan.model_dump())
        else:
            if not plan.changes and not plan.ambiguous:
                output_success(f"[bold]{pack_name}[/bold] is up to date")
            else:
                output_header(f"Updates for {pack_name}")

                if plan.changes:
                    console.print(f"[bold]Available updates ({len(plan.changes)}):[/bold]")
                    for change in plan.changes:
                        console.print(f"  [cyan]{change.dependency_id}[/cyan]")
                        console.print(f"    [dim]Old:[/dim] v{change.old.get('provider_version_id', '?')}")
                        console.print(f"    [green]New:[/green] v{change.new.get('provider_version_id', '?')}")

                if plan.ambiguous:
                    console.print(f"\n[bold yellow]Ambiguous ({len(plan.ambiguous)}):[/bold yellow]")
                    for amb in plan.ambiguous:
                        console.print(f"  [yellow]{amb.dependency_id}[/yellow]: {len(amb.candidates)} candidates")

                console.print(f"\n[dim]Run 'synapse update {pack_name}' to apply updates[/dim]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("check-all-updates")
def check_all_updates(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Check for updates on all packs."""
    store = get_store()
    require_initialized(store)

    try:
        results = store.check_all_updates()

        if json:
            output_json({name: plan.model_dump() for name, plan in results.items()})
        else:
            output_header("Update Check")

            packs_with_updates = {
                name: plan for name, plan in results.items()
                if plan.changes or plan.ambiguous
            }

            if not packs_with_updates:
                output_success("All packs are up to date")
            else:
                table = Table(box=box.ROUNDED)
                table.add_column("Pack", style="cyan")
                table.add_column("Updates", justify="right", style="green")
                table.add_column("Ambiguous", justify="right", style="yellow")

                for name, plan in sorted(packs_with_updates.items()):
                    table.add_row(
                        name,
                        str(len(plan.changes)) if plan.changes else "-",
                        str(len(plan.ambiguous)) if plan.ambiguous else "-",
                    )

                console.print(table)
                console.print(f"\n[dim]Run 'synapse update <pack>' to apply updates[/dim]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("update")
def update_command(
    pack_name: str = typer.Argument(..., help="Pack name to update"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be updated"),
    sync: bool = typer.Option(True, "--sync/--no-sync", help="Sync views after update"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Update a pack to latest versions."""
    store = get_store()
    require_initialized(store)

    try:
        result = store.update(pack_name, dry_run=dry_run, sync=sync)

        if json:
            output_json(result.model_dump())
        else:
            if dry_run:
                output_header(f"Dry Run: {pack_name}")
                if result.plan and result.plan.changes:
                    console.print("[bold]Would update:[/bold]")
                    for change in result.plan.changes:
                        console.print(f"  [cyan]{change.dependency_id}[/cyan]")
                else:
                    output_info("Nothing to update")
            else:
                if result.applied:
                    output_success(f"Updated [bold]{pack_name}[/bold]")
                    console.print(f"  Applied {len(result.applied)} update(s)")
                else:
                    output_info(f"[bold]{pack_name}[/bold] is already up to date")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Maintenance Commands
# =============================================================================

@app.command("doctor")
def doctor_command(
    rebuild_views: bool = typer.Option(False, "--rebuild-views", help="Force rebuild views"),
    verify_blobs: bool = typer.Option(True, "--verify-blobs/--no-verify-blobs", help="Verify blob integrity"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run diagnostics and repairs on the store."""
    store = get_store()
    require_initialized(store)

    try:
        if not json:
            console.print("[dim]Running diagnostics...[/dim]")
        report = store.doctor(
            rebuild_views=rebuild_views,
            verify_blobs=verify_blobs,
        )

        if json:
            output_json(report.model_dump())
        else:
            output_header("Doctor Report")

            # Summary
            console.print(f"Profile: [cyan]{report.profile}[/cyan]")
            console.print(f"UI targets: {', '.join(report.ui_targets)}")

            # Actions taken
            if report.actions:
                console.print(f"\n[bold]Actions:[/bold]")
                if report.actions.views_rebuilt:
                    console.print("  [green]✓[/green] Views rebuilt")
                if report.actions.blobs_verified:
                    console.print("  [green]✓[/green] Blobs verified")
                if report.actions.db_rebuilt:
                    console.print(f"  [green]✓[/green] DB rebuilt ({report.actions.db_rebuilt})")

            # Issues
            if report.missing_blobs:
                console.print(f"\n[yellow]Missing blobs ({len(report.missing_blobs)}):[/yellow]")
                for mb in report.missing_blobs[:5]:
                    console.print(f"  • {mb.pack}/{mb.dependency_id}")
                if len(report.missing_blobs) > 5:
                    console.print(f"  [dim]... and {len(report.missing_blobs) - 5} more[/dim]")

            if report.unresolved:
                console.print(f"\n[yellow]Unresolved ({len(report.unresolved)}):[/yellow]")
                for ur in report.unresolved[:5]:
                    console.print(f"  • {ur.pack}/{ur.dependency_id}: {ur.reason}")

            if report.shadowed:
                console.print(f"\n[dim]Shadowed ({len(report.shadowed)}):[/dim]")
                for sh in report.shadowed[:5]:
                    console.print(f"  • {sh.filename}: {sh.by_pack} shadows {sh.pack}")

            # Notes
            if report.notes:
                console.print(f"\n[dim]Notes:[/dim]")
                for note in report.notes:
                    console.print(f"  • {note}")

            if not report.missing_blobs and not report.unresolved:
                console.print()
                output_success("Store is healthy")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("search")
def search_command(
    query: str = typer.Argument(..., help="Search query"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Search installed packs."""
    store = get_store()
    require_initialized(store)

    try:
        result = store.search(query)

        if json:
            output_json(result.model_dump())
        else:
            if not result.items:
                output_info(f"No results for '{query}'")
            else:
                table = Table(title=f"Search Results for '{query}'", box=box.ROUNDED)
                table.add_column("Pack", style="cyan bold")
                table.add_column("Type", style="green")
                table.add_column("Provider")

                for item in result.items:
                    table.add_row(
                        item.pack_name,
                        item.pack_type or "-",
                        item.provider or "-",
                    )

                console.print(table)

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("clean")
def clean_command(
    tmp: bool = typer.Option(True, "--tmp/--no-tmp", help="Clean tmp directory"),
    cache: bool = typer.Option(False, "--cache/--no-cache", help="Clean cache directory"),
    partial: bool = typer.Option(True, "--partial/--no-partial", help="Clean partial downloads"),
):
    """Clean temporary files and caches."""
    store = get_store()
    require_initialized(store)

    try:
        result = store.clean(tmp=tmp, cache=cache, partial=partial)

        total = sum(result.values())
        if total > 0:
            output_success(f"Cleaned {total} file(s)")
            for category, count in result.items():
                if count > 0:
                    console.print(f"  {category}: {count}")
        else:
            output_info("Nothing to clean")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@app.command("sync")
def sync_command(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile to sync"),
    ui_set: Optional[str] = typer.Option(None, "--ui-set", "-u", help="UI set to sync"),
):
    """Sync views for a profile."""
    store = get_store()
    require_initialized(store)

    try:
        console.print("[dim]Syncing views...[/dim]")
        reports = store.sync(profile_name=profile, ui_set=ui_set)

        output_success("Views synced")
        for ui, report in reports.items():
            entries = report.get("entries_created", 0)
            shadowed = len(report.get("shadowed", []))
            console.print(f"  [cyan]{ui}[/cyan]: {entries} entries, {shadowed} shadowed")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Inventory Commands
# =============================================================================

def _format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _location_display(location: BlobLocation) -> str:
    """Get display text for blob location."""
    if location == BlobLocation.BOTH:
        return "[green]Both[/green]"
    elif location == BlobLocation.LOCAL_ONLY:
        return "[cyan]Local[/cyan]"
    elif location == BlobLocation.BACKUP_ONLY:
        return "[yellow]Backup[/yellow]"
    else:
        return "[red]Nowhere[/red]"


def _status_display(status: BlobStatus) -> str:
    """Get display text for blob status."""
    if status == BlobStatus.REFERENCED:
        return "[green]✓ Referenced[/green]"
    elif status == BlobStatus.ORPHAN:
        return "[yellow]⚠ Orphan[/yellow]"
    elif status == BlobStatus.MISSING:
        return "[red]✗ Missing[/red]"
    elif status == BlobStatus.BACKUP_ONLY:
        return "[blue]↓ Backup Only[/blue]"
    else:
        return status.value


@inventory_app.command("list")
def inventory_list(
    kind: Optional[str] = typer.Option(None, "--kind", "-k", help="Filter by asset kind"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status (referenced/orphan/missing/backup_only)"),
    verify: bool = typer.Option(False, "--verify", "-v", help="Verify blob hashes (slow)"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all blobs in inventory."""
    store = get_store()
    require_initialized(store)

    # Parse filters
    kind_filter = None
    if kind:
        try:
            kind_filter = AssetKind(kind.lower())
        except ValueError:
            output_error(f"Invalid kind: {kind}")
            valid = ", ".join(k.value for k in AssetKind)
            console.print(f"[dim]Valid kinds: {valid}[/dim]")
            raise typer.Exit(1)

    status_filter = None
    if status:
        try:
            status_filter = BlobStatus(status.lower())
        except ValueError:
            output_error(f"Invalid status: {status}")
            valid = ", ".join(s.value for s in BlobStatus)
            console.print(f"[dim]Valid statuses: {valid}[/dim]")
            raise typer.Exit(1)

    try:
        inventory = store.inventory_service.build_inventory(
            kind_filter=kind_filter,
            status_filter=status_filter,
            include_verification=verify,
        )

        if json:
            output_json(inventory.model_dump())
        else:
            output_header("Blob Inventory", f"{len(inventory.items)} blobs")

            # Summary panel
            summary = inventory.summary
            summary_text = (
                f"[bold]Total:[/bold] {summary.blobs_total} blobs ({_format_size(summary.bytes_total)})\n"
                f"[green]Referenced:[/green] {summary.blobs_referenced} ({_format_size(summary.bytes_referenced)})\n"
                f"[yellow]Orphan:[/yellow] {summary.blobs_orphan} ({_format_size(summary.bytes_orphan)})\n"
                f"[red]Missing:[/red] {summary.blobs_missing}\n"
                f"[blue]Backup Only:[/blue] {summary.blobs_backup_only}"
            )
            console.print(Panel(summary_text, title="Summary", box=box.ROUNDED))

            if inventory.items:
                # Table of blobs
                table = Table(box=box.SIMPLE)
                table.add_column("Name", style="cyan", max_width=30)
                table.add_column("Kind", style="green")
                table.add_column("Size", justify="right")
                table.add_column("Location")
                table.add_column("Status")
                table.add_column("Refs", justify="right")
                if verify:
                    table.add_column("Valid")

                for item in inventory.items[:50]:  # Limit display
                    row = [
                        item.display_name,
                        item.kind.value,
                        _format_size(item.size_bytes),
                        _location_display(item.location),
                        _status_display(item.status),
                        str(item.ref_count),
                    ]
                    if verify:
                        valid_str = "[green]✓[/green]" if item.verified else "[red]✗[/red]" if item.verified is False else "[dim]-[/dim]"
                        row.append(valid_str)
                    table.add_row(*row)

                console.print(table)

                if len(inventory.items) > 50:
                    console.print(f"\n[dim]... and {len(inventory.items) - 50} more[/dim]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@inventory_app.command("orphans")
def inventory_orphans(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List orphan blobs (not referenced by any pack)."""
    store = get_store()
    require_initialized(store)

    try:
        inventory = store.inventory_service.build_inventory(status_filter=BlobStatus.ORPHAN)

        if json:
            output_json({
                "orphans": [item.model_dump() for item in inventory.items],
                "total_bytes": inventory.summary.bytes_orphan,
            })
        else:
            if not inventory.items:
                output_success("No orphan blobs found")
            else:
                output_header("Orphan Blobs", f"{len(inventory.items)} found")
                console.print(f"[dim]These blobs are not referenced by any pack and can be safely deleted.[/dim]\n")

                table = Table(box=box.SIMPLE)
                table.add_column("SHA256", style="dim", max_width=16)
                table.add_column("Name", style="cyan")
                table.add_column("Kind", style="green")
                table.add_column("Size", justify="right")
                table.add_column("Location")

                for item in inventory.items[:30]:
                    table.add_row(
                        item.sha256[:12] + "...",
                        item.display_name,
                        item.kind.value,
                        _format_size(item.size_bytes),
                        _location_display(item.location),
                    )

                console.print(table)
                console.print(f"\n[bold]Total:[/bold] {_format_size(inventory.summary.bytes_orphan)} can be freed")
                console.print(f"\n[dim]Run 'synapse inventory cleanup' to remove orphans[/dim]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@inventory_app.command("missing")
def inventory_missing(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List missing blobs (referenced but not present)."""
    store = get_store()
    require_initialized(store)

    try:
        inventory = store.inventory_service.build_inventory(status_filter=BlobStatus.MISSING)

        if json:
            output_json({
                "missing": [item.model_dump() for item in inventory.items],
                "count": len(inventory.items),
            })
        else:
            if not inventory.items:
                output_success("No missing blobs")
            else:
                output_warning(f"{len(inventory.items)} missing blob(s)")
                console.print("[dim]These blobs are referenced by packs but don't exist.[/dim]\n")

                table = Table(box=box.SIMPLE)
                table.add_column("SHA256", style="dim", max_width=16)
                table.add_column("Name", style="cyan")
                table.add_column("Kind", style="green")
                table.add_column("Used By")

                for item in inventory.items[:30]:
                    packs = ", ".join(item.used_by_packs[:3])
                    if len(item.used_by_packs) > 3:
                        packs += f" +{len(item.used_by_packs) - 3}"
                    table.add_row(
                        item.sha256[:12] + "...",
                        item.display_name,
                        item.kind.value,
                        packs,
                    )

                console.print(table)

                if store.backup_service.is_connected():
                    console.print(f"\n[dim]Some may be restorable from backup. Run 'synapse backup restore <sha256>'[/dim]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@inventory_app.command("cleanup")
def inventory_cleanup(
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview vs actually delete"),
    max_items: int = typer.Option(0, "--max", "-m", help="Maximum items to delete (0=unlimited)"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Remove orphan blobs safely."""
    from rich.progress import Progress, SpinnerColumn, TextColumn

    store = get_store()
    require_initialized(store)

    try:
        if not dry_run and not json:
            console.print("[bold yellow]⚠ EXECUTING CLEANUP[/bold yellow]")
            console.print("[dim]This will permanently delete orphan blobs.[/dim]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Scanning for orphans...", total=None)
            result = store.inventory_service.cleanup_orphans(dry_run=dry_run, max_items=max_items)
            progress.update(task, description="Done")

        if json:
            output_json(result.model_dump())
        else:
            if dry_run:
                output_header("Cleanup Preview", "DRY RUN")
                if result.orphans_found == 0:
                    output_success("No orphan blobs to clean up")
                else:
                    console.print(f"[bold]Found {result.orphans_found} orphan blob(s)[/bold]")
                    console.print(f"Would free: [green]{_format_size(result.bytes_freed)}[/green]")

                    if result.deleted:
                        console.print("\n[dim]Blobs that would be deleted:[/dim]")
                        for item in result.deleted[:10]:
                            console.print(f"  • {item.display_name} ({_format_size(item.size_bytes)})")
                        if len(result.deleted) > 10:
                            console.print(f"  [dim]... and {len(result.deleted) - 10} more[/dim]")

                    console.print(f"\n[dim]Run with --execute to delete[/dim]")
            else:
                if result.orphans_deleted > 0:
                    output_success(f"Deleted {result.orphans_deleted} orphan blob(s)")
                    console.print(f"Freed: [green]{_format_size(result.bytes_freed)}[/green]")
                else:
                    output_info("No orphan blobs to clean up")

                if result.errors:
                    console.print(f"\n[yellow]Errors ({len(result.errors)}):[/yellow]")
                    for err in result.errors[:5]:
                        console.print(f"  • {err}")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@inventory_app.command("impacts")
def inventory_impacts(
    sha256: str = typer.Argument(..., help="SHA256 hash of blob to analyze"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Analyze what would break if a blob is deleted."""
    store = get_store()
    require_initialized(store)

    try:
        impacts = store.inventory_service.get_impacts(sha256)

        if json:
            output_json(impacts.model_dump())
        else:
            output_header("Impact Analysis")

            console.print(f"[bold]SHA256:[/bold] [dim]{sha256}[/dim]")
            console.print(f"[bold]Status:[/bold] {_status_display(impacts.status)}")
            console.print(f"[bold]Size:[/bold] {_format_size(impacts.size_bytes)}")

            if impacts.used_by_packs:
                console.print(f"\n[bold]Used by {len(impacts.used_by_packs)} pack(s):[/bold]")
                for pack in impacts.used_by_packs:
                    console.print(f"  • [cyan]{pack}[/cyan]")

            if impacts.can_delete_safely:
                console.print(f"\n[green]✓ Safe to delete[/green]")
            else:
                console.print(f"\n[red]✗ NOT safe to delete[/red]")
                if impacts.warning:
                    console.print(f"[yellow]{impacts.warning}[/yellow]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@inventory_app.command("verify")
def inventory_verify(
    all_blobs: bool = typer.Option(False, "--all", "-a", help="Verify all blobs"),
    sha256: Optional[str] = typer.Option(None, "--sha256", "-s", help="Verify specific blob"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Verify blob integrity (check hashes)."""
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

    store = get_store()
    require_initialized(store)

    if not all_blobs and not sha256:
        output_error("Specify --all or --sha256")
        raise typer.Exit(1)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Verifying blobs...", total=None)

            if sha256:
                result = store.inventory_service.verify_blobs(sha256_list=[sha256])
            else:
                result = store.inventory_service.verify_blobs(all_blobs=True)

            progress.update(task, description="Done")

        if json:
            output_json(result)
        else:
            output_header("Verification Results")

            console.print(f"[bold]Verified:[/bold] {result['verified']} blob(s)")
            console.print(f"[bold]Duration:[/bold] {result['duration_ms']}ms")

            valid_count = len(result['valid'])
            invalid_count = len(result['invalid'])

            if valid_count > 0:
                console.print(f"\n[green]✓ Valid: {valid_count}[/green]")

            if invalid_count > 0:
                console.print(f"\n[red]✗ Invalid: {invalid_count}[/red]")
                for sha in result['invalid'][:10]:
                    console.print(f"  • {sha[:16]}...")

            if invalid_count == 0:
                output_success("All blobs verified successfully")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@inventory_app.command("migrate-manifests")
def inventory_migrate_manifests(
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview vs actually create manifests"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Create manifests for existing blobs that don't have them.

    Scans all blobs and creates .meta manifest files from pack.lock data
    for any blob missing a manifest. This preserves metadata for orphan
    blob recovery.

    The operation is safe and idempotent - existing manifests are never
    overwritten.

    Example:
        synapse inventory migrate-manifests              # Preview what would be created
        synapse inventory migrate-manifests --execute    # Actually create manifests
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    store = get_store()
    require_initialized(store)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Scanning blobs...", total=None)
            result = store.inventory_service.migrate_manifests(dry_run=dry_run)
            progress.update(task, description="Done")

        if json:
            output_json(result.model_dump())
        else:
            output_header("Manifest Migration", "DRY RUN" if dry_run else "")

            console.print(f"[bold]Blobs scanned:[/bold] {result.blobs_scanned}")
            console.print(f"[bold]Already have manifest:[/bold] {result.manifests_existing}")
            console.print(f"[bold]Skipped (no pack refs):[/bold] {result.manifests_skipped}")

            action = "Would create" if dry_run else "Created"
            if result.manifests_created > 0:
                console.print(f"[green]{action}:[/green] {result.manifests_created} manifest(s)")
            else:
                output_info("No manifests to create")

            if result.errors:
                console.print(f"\n[yellow]Errors ({len(result.errors)}):[/yellow]")
                for err in result.errors[:5]:
                    console.print(f"  • {err}")

            if dry_run and result.manifests_created > 0:
                console.print(f"\n[dim]Run with --execute to create manifests[/dim]")
            elif not dry_run and result.manifests_created > 0:
                output_success(f"Created {result.manifests_created} manifest(s)")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Backup Commands
# =============================================================================

@backup_app.command("status")
def backup_status(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show backup storage status."""
    store = get_store()
    require_initialized(store)

    try:
        status = store.get_backup_status()

        if json:
            output_json(status.model_dump())
        else:
            output_header("Backup Status")

            if not status.enabled:
                output_info("Backup is [yellow]disabled[/yellow]")
                console.print("\n[dim]Enable with: synapse backup config --path /path/to/backup[/dim]")
                return

            console.print(f"[bold]Enabled:[/bold] [green]Yes[/green]")
            console.print(f"[bold]Path:[/bold] {status.path or 'Not set'}")
            console.print(f"[bold]Connected:[/bold] {'[green]Yes[/green]' if status.connected else '[red]No[/red]'}")

            if status.error:
                output_error(status.error)

            if status.connected:
                console.print(f"\n[bold]Blobs:[/bold] {status.total_blobs}")
                console.print(f"[bold]Size:[/bold] {_format_size(status.total_bytes)}")
                if status.free_space is not None:
                    console.print(f"[bold]Free Space:[/bold] {_format_size(status.free_space)}")
                if status.last_sync:
                    console.print(f"[bold]Last Sync:[/bold] {status.last_sync}")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@backup_app.command("sync")
def backup_sync(
    direction: str = typer.Option("to_backup", "--direction", "-d", help="Sync direction: to_backup or from_backup"),
    only_missing: bool = typer.Option(True, "--only-missing/--all", help="Only sync missing blobs"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview vs actually sync"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Synchronize blobs between local and backup storage."""
    from rich.progress import Progress, SpinnerColumn, TextColumn

    store = get_store()
    require_initialized(store)

    if direction not in ("to_backup", "from_backup"):
        output_error("Direction must be 'to_backup' or 'from_backup'")
        raise typer.Exit(1)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Syncing {direction}...", total=None)
            result = store.sync_backup(
                direction=direction,
                only_missing=only_missing,
                dry_run=dry_run,
            )
            progress.update(task, description="Done")

        if json:
            output_json(result.model_dump())
        else:
            action = "Would sync" if dry_run else "Synced"
            dir_text = "→ backup" if direction == "to_backup" else "← backup"

            output_header(f"Backup Sync {dir_text}", "DRY RUN" if dry_run else "")

            if not result.items:
                output_success("Nothing to sync")
            else:
                console.print(f"[bold]{action}:[/bold] {result.blobs_synced} blob(s)")
                console.print(f"[bold]Size:[/bold] {_format_size(result.bytes_synced)}")

                if result.items[:10]:
                    console.print("\n[dim]Items:[/dim]")
                    for item in result.items[:10]:
                        name = item.display_name or item.sha256[:12] + "..."
                        console.print(f"  • {name} ({_format_size(item.size_bytes)})")

                    if len(result.items) > 10:
                        console.print(f"  [dim]... and {len(result.items) - 10} more[/dim]")

                if result.errors:
                    console.print(f"\n[yellow]Errors ({len(result.errors)}):[/yellow]")
                    for err in result.errors[:5]:
                        console.print(f"  • {err}")

                if dry_run:
                    console.print(f"\n[dim]Run with --execute to sync[/dim]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@backup_app.command("blob")
def backup_blob_cmd(
    sha256: str = typer.Argument(..., help="SHA256 hash of blob to backup"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Verify after copy"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Backup a specific blob to backup storage."""
    store = get_store()
    require_initialized(store)

    try:
        result = store.backup_blob(sha256, verify_after=verify)

        if json:
            output_json(result.model_dump())
        else:
            if result.success:
                output_success(f"Backed up blob: {sha256[:16]}...")
                console.print(f"Size: {_format_size(result.bytes_copied)}")
                if result.verified:
                    console.print("[green]✓ Verified[/green]")
            else:
                output_error(f"Backup failed: {result.error}")
                raise typer.Exit(1)

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@backup_app.command("restore")
def backup_restore(
    sha256: str = typer.Argument(..., help="SHA256 hash of blob to restore"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Verify after copy"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Restore a blob from backup storage."""
    store = get_store()
    require_initialized(store)

    try:
        result = store.restore_blob(sha256, verify_after=verify)

        if json:
            output_json(result.model_dump())
        else:
            if result.success:
                output_success(f"Restored blob: {sha256[:16]}...")
                console.print(f"Size: {_format_size(result.bytes_copied)}")
                if result.verified:
                    console.print("[green]✓ Verified[/green]")
            else:
                output_error(f"Restore failed: {result.error}")
                raise typer.Exit(1)

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@backup_app.command("delete")
def backup_delete(
    sha256: str = typer.Argument(..., help="SHA256 hash of blob to delete from backup"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Delete a blob from backup storage."""
    store = get_store()
    require_initialized(store)

    try:
        # Check for warning first
        warning = store.backup_service.get_delete_warning(sha256, "backup")
        if warning and not confirm and not json:
            output_warning(warning)
            if not typer.confirm("Continue anyway?"):
                raise typer.Abort()

        result = store.delete_from_backup(sha256, confirm=True)

        if json:
            output_json(result.model_dump())
        else:
            if result.deleted:
                output_success(f"Deleted from backup: {sha256[:16]}...")
                console.print(f"Freed: {_format_size(result.bytes_freed)}")
                if result.warning:
                    output_warning(result.warning)
            else:
                output_error(f"Delete failed: {result.error}")
                raise typer.Exit(1)

    except typer.Abort:
        raise
    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@backup_app.command("config")
def backup_config(
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Set backup path"),
    enable: Optional[bool] = typer.Option(None, "--enable/--disable", help="Enable/disable backup"),
    auto_backup: Optional[bool] = typer.Option(None, "--auto/--no-auto", help="Auto-backup new blobs"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Configure backup storage."""
    store = get_store()
    require_initialized(store)

    try:
        # If any options provided, update config
        if path is not None or enable is not None or auto_backup is not None:
            current_status = store.get_backup_status()

            new_config = BackupConfig(
                enabled=enable if enable is not None else current_status.enabled,
                path=path if path is not None else current_status.path,
                auto_backup_new=auto_backup if auto_backup is not None else False,
            )
            store.configure_backup(new_config)
            output_success("Backup configuration updated")

        # Show current config
        status = store.get_backup_status()

        if json:
            output_json({
                "enabled": status.enabled,
                "path": status.path,
                "connected": status.connected,
            })
        else:
            output_header("Backup Configuration")
            console.print(f"[bold]Enabled:[/bold] {'[green]Yes[/green]' if status.enabled else '[red]No[/red]'}")
            console.print(f"[bold]Path:[/bold] {status.path or '[dim]Not set[/dim]'}")
            console.print(f"[bold]Connected:[/bold] {'[green]Yes[/green]' if status.connected else '[red]No[/red]'}")

            if not status.enabled:
                console.print("\n[dim]Enable with: synapse backup config --enable --path /path/to/backup[/dim]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# Pack-Level Backup Operations (pull/push)
# =============================================================================

@backup_app.command("pull")
def backup_pull(
    pack_name: str = typer.Argument(..., help="Pack name to pull from backup"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview vs actually restore"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Pull (restore) all blobs for a pack from backup.

    Restores pack blobs without activating any profile.
    Use this when you need pack models locally but want to stay on global profile.

    Example:
        synapse backup pull MyPack              # Preview what would be restored
        synapse backup pull MyPack --execute    # Actually restore
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    store = get_store()
    require_initialized(store)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Pulling {pack_name}...", total=None)
            result = store.pull_pack(pack_name, dry_run=dry_run)
            progress.update(task, description="Done")

        if json:
            output_json(result.model_dump())
        else:
            action = "Would restore" if dry_run else "Restored"

            output_header(f"Backup Pull: {pack_name}", "DRY RUN" if dry_run else "")

            if not result.items and not result.errors:
                output_success("All pack blobs already local")
            elif result.errors and "Backup not connected" in result.errors:
                output_error("Backup not connected. Configure with: synapse backup config --enable --path /path")
                raise typer.Exit(1)
            else:
                console.print(f"[bold]{action}:[/bold] {result.blobs_synced if not dry_run else result.blobs_to_sync} blob(s)")
                console.print(f"[bold]Size:[/bold] {_format_size(result.bytes_synced if not dry_run else result.bytes_to_sync)}")

                if result.items[:10]:
                    console.print("\n[dim]Items:[/dim]")
                    for item in result.items[:10]:
                        name = item.display_name or item.sha256[:12] + "..."
                        console.print(f"  • {name} ({_format_size(item.size_bytes)})")

                    if len(result.items) > 10:
                        console.print(f"  [dim]... and {len(result.items) - 10} more[/dim]")

                if result.errors:
                    real_errors = [e for e in result.errors if not e.startswith("note:")]
                    if real_errors:
                        console.print(f"\n[yellow]Errors ({len(real_errors)}):[/yellow]")
                        for err in real_errors[:5]:
                            console.print(f"  • {err}")

                if dry_run:
                    console.print(f"\n[dim]Run with --execute to restore[/dim]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


@backup_app.command("push")
def backup_push(
    pack_name: str = typer.Argument(..., help="Pack name to push to backup"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview vs actually backup"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Delete local copies after backup"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Push (backup) all blobs for a pack to backup storage.

    Backs up pack blobs. Use --cleanup to free local disk space after backup.

    Example:
        synapse backup push MyPack                      # Preview what would be backed up
        synapse backup push MyPack --execute            # Actually backup
        synapse backup push MyPack --execute --cleanup  # Backup and free local space
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    store = get_store()
    require_initialized(store)

    try:
        if cleanup and dry_run:
            output_warning("--cleanup requires --execute to actually delete files")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Pushing {pack_name}...", total=None)
            result = store.push_pack(pack_name, dry_run=dry_run, cleanup=cleanup and not dry_run)
            progress.update(task, description="Done")

        if json:
            output_json(result.model_dump())
        else:
            action = "Would backup" if dry_run else "Backed up"

            output_header(f"Backup Push: {pack_name}", "DRY RUN" if dry_run else "")

            if not result.items and not result.errors:
                output_success("All pack blobs already on backup")
            elif result.errors and "Backup not connected" in result.errors:
                output_error("Backup not connected. Configure with: synapse backup config --enable --path /path")
                raise typer.Exit(1)
            else:
                console.print(f"[bold]{action}:[/bold] {result.blobs_synced if not dry_run else result.blobs_to_sync} blob(s)")
                console.print(f"[bold]Size:[/bold] {_format_size(result.bytes_synced if not dry_run else result.bytes_to_sync)}")

                if result.items[:10]:
                    console.print("\n[dim]Items:[/dim]")
                    for item in result.items[:10]:
                        name = item.display_name or item.sha256[:12] + "..."
                        console.print(f"  • {name} ({_format_size(item.size_bytes)})")

                    if len(result.items) > 10:
                        console.print(f"  [dim]... and {len(result.items) - 10} more[/dim]")

                # Check for cleanup note
                cleanup_note = [e for e in result.errors if e.startswith("note:cleaned_up_")]
                if cleanup_note:
                    count = cleanup_note[0].split("_")[2]
                    console.print(f"\n[green]✓ Cleaned up {count} local copies[/green]")

                real_errors = [e for e in result.errors if not e.startswith("note:")]
                if real_errors:
                    console.print(f"\n[yellow]Errors ({len(real_errors)}):[/yellow]")
                    for err in real_errors[:5]:
                        console.print(f"  • {err}")

                if dry_run:
                    console.print(f"\n[dim]Run with --execute to backup[/dim]")
                    if cleanup:
                        console.print(f"[dim]Add --cleanup to also delete local copies[/dim]")

    except Exception as e:
        output_error(str(e))
        raise typer.Exit(1)


# =============================================================================
# State Sync Commands
# =============================================================================

@backup_app.command("state-status")
def state_status():
    """
    Show sync status of the state/ directory.

    Compares local state/ with backup state/ and shows differences.
    """
    store = get_store()

    with console.status("Analyzing state files..."):
        result = store.backup_service.get_state_sync_status()

    if result.errors:
        for err in result.errors:
            if "not enabled" in err.lower():
                output_warning("Backup not enabled")
                console.print("\n[dim]Enable with: synapse backup config --enable --path /path/to/backup[/dim]")
                return
            elif "not connected" in err.lower():
                output_warning("Backup not connected")
                return
            else:
                output_error(err)
        return

    output_header("State Sync Status")

    # Summary
    summary = result.summary
    console.print(f"[bold]Total files:[/bold] {summary.total_files}")
    console.print(f"[green]Synced:[/green] {summary.synced}")
    console.print(f"[cyan]Local only:[/cyan] {summary.local_only}")
    console.print(f"[yellow]Backup only:[/yellow] {summary.backup_only}")
    console.print(f"[magenta]Modified:[/magenta] {summary.modified}")

    if summary.conflicts > 0:
        console.print(f"[red]Conflicts:[/red] {summary.conflicts}")

    if summary.last_sync:
        console.print(f"\n[dim]Last sync: {summary.last_sync}[/dim]")

    # Show files that need sync
    needs_sync = [i for i in result.items if i.status.value != "synced"]
    if needs_sync:
        console.print(f"\n[bold]Files needing sync ({len(needs_sync)}):[/bold]")
        for item in needs_sync[:20]:
            status_color = {
                "local_only": "cyan",
                "backup_only": "yellow",
                "modified": "magenta",
                "conflict": "red",
            }.get(item.status.value, "white")
            console.print(f"  [{status_color}]{item.status.value:12}[/{status_color}] {item.relative_path}")

        if len(needs_sync) > 20:
            console.print(f"  [dim]... and {len(needs_sync) - 20} more[/dim]")

        console.print(f"\n[dim]Sync with: synapse backup state-sync --direction to_backup[/dim]")
    else:
        output_success("All state files are synced!")


@backup_app.command("state-sync")
def state_sync(
    direction: str = typer.Option(
        "to_backup",
        "--direction", "-d",
        help="Sync direction: to_backup, from_backup, or bidirectional"
    ),
    execute: bool = typer.Option(
        False,
        "--execute", "-x",
        help="Actually perform the sync (default is dry-run)"
    ),
):
    """
    Sync the state/ directory with backup storage.

    Examples:
        synapse backup state-sync                           # Preview sync to backup
        synapse backup state-sync --execute                 # Sync to backup
        synapse backup state-sync --direction from_backup   # Preview restore from backup
        synapse backup state-sync -d bidirectional -x       # Bidirectional sync (newer wins)
    """
    store = get_store()
    dry_run = not execute

    action = "Would sync" if dry_run else "Syncing"
    with console.status(f"{action} state files..."):
        result = store.backup_service.sync_state(
            direction=direction,
            dry_run=dry_run,
        )

    if result.errors:
        for err in result.errors:
            if "not enabled" in err.lower():
                output_error("Backup not enabled. Configure with: synapse backup config --enable --path /path")
                raise typer.Exit(1)
            elif "not connected" in err.lower():
                output_error("Backup not connected")
                raise typer.Exit(1)

    output_header(f"State Sync: {direction}", "DRY RUN" if dry_run else "")

    summary = result.summary
    console.print(f"[bold]Total files:[/bold] {summary.total_files}")
    console.print(f"[green]Already synced:[/green] {summary.synced}")

    if summary.local_only > 0:
        console.print(f"[cyan]Local only:[/cyan] {summary.local_only}")
    if summary.backup_only > 0:
        console.print(f"[yellow]Backup only:[/yellow] {summary.backup_only}")
    if summary.modified > 0:
        console.print(f"[magenta]Modified:[/magenta] {summary.modified}")

    if not dry_run:
        console.print(f"\n[green]✓ Synced {result.synced_files} file(s)[/green]")
    else:
        needs_sync = summary.local_only + summary.backup_only + summary.modified
        if needs_sync > 0:
            console.print(f"\n[dim]Run with --execute to sync {needs_sync} file(s)[/dim]")
        else:
            output_success("All state files are already synced!")

    # Show errors
    real_errors = [e for e in result.errors if not e.startswith("note:")]
    if real_errors:
        console.print(f"\n[yellow]Errors ({len(real_errors)}):[/yellow]")
        for err in real_errors[:5]:
            console.print(f"  • {err}")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
