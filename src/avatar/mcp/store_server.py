"""
Synapse Store MCP Server — Read-only tools for AI avatar.

Provides 10 tools for querying packs, inventory, backup status,
and storage statistics. Uses FastMCP with stdio transport.

All tool implementations are in _*_impl() functions for testability
without requiring the mcp package.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Guard MCP import — module is usable without mcp installed (for tests)
try:
    from mcp.server.fastmcp import FastMCP

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# Lazy Store singleton (thread-safe)
_store_instance = None
_store_lock = threading.Lock()


def _get_store() -> Any:
    """Get or create Store singleton (same pattern as src/store/api.py)."""
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                from src.store import Store
                from config.settings import get_config

                cfg = get_config()
                civitai_api_key = None
                if hasattr(cfg, "api") and hasattr(cfg.api, "civitai_token"):
                    civitai_api_key = cfg.api.civitai_token

                _store_instance = Store(root=cfg.store.root, civitai_api_key=civitai_api_key)
    return _store_instance


def _reset_store() -> None:
    """Reset Store singleton (for testing)."""
    global _store_instance
    with _store_lock:
        _store_instance = None


def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


# =============================================================================
# Tool implementations (_impl functions for testability)
# =============================================================================


def _list_packs_impl(store: Any = None, name_filter: str = "", limit: int = 20) -> str:
    """List all packs in the Synapse store."""
    try:
        if store is None:
            store = _get_store()

        pack_names = store.list_packs()

        # Apply filter
        if name_filter:
            filter_lower = name_filter.lower()
            pack_names = [n for n in pack_names if filter_lower in n.lower()]

        # Apply limit
        total = len(pack_names)
        pack_names = pack_names[:limit]

        if not pack_names:
            if name_filter:
                return f"No packs found matching '{name_filter}'."
            return "No packs in the store."

        lines = [f"Found {total} pack{'s' if total != 1 else ''}:"]
        if total > limit:
            lines[0] += f" (showing first {limit})"
        lines.append("")

        for i, name in enumerate(pack_names, 1):
            try:
                pack = store.get_pack(name)
                pack_type = pack.pack_type.value if hasattr(pack.pack_type, "value") else str(pack.pack_type)
                base = f" — Base: {pack.base_model}" if pack.base_model else ""
                dep_count = len(pack.dependencies)
                source = pack.source.provider.value if pack.source else "unknown"
                lines.append(
                    f"{i}. {name} ({pack_type}){base}"
                )
                lines.append(
                    f"   {dep_count} dependenc{'y' if dep_count == 1 else 'ies'}, Source: {source}"
                )
            except Exception:
                lines.append(f"{i}. {name} (error loading details)")

        return "\n".join(lines)
    except Exception as e:
        logger.error("list_packs failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _get_pack_details_impl(store: Any = None, pack_name: str = "") -> str:
    """Get detailed information about a specific pack."""
    try:
        if store is None:
            store = _get_store()

        if not pack_name:
            return "Error: pack_name is required."

        try:
            pack = store.get_pack(pack_name)
        except Exception as e:
            logger.debug("get_pack('%s') failed: %s", pack_name, e)
            return f"Error: Pack '{pack_name}' not found."

        pack_type = pack.pack_type.value if hasattr(pack.pack_type, "value") else str(pack.pack_type)
        source_provider = pack.source.provider.value if pack.source else "unknown"

        lines = [
            f"Pack: {pack.name}",
            f"Type: {pack_type}",
        ]

        if pack.base_model:
            lines.append(f"Base Model: {pack.base_model}")
        if pack.version:
            lines.append(f"Version: {pack.version}")
        if pack.author:
            lines.append(f"Author: {pack.author}")
        if pack.description:
            desc = pack.description[:200] + "..." if len(pack.description) > 200 else pack.description
            lines.append(f"Description: {desc}")

        lines.append(f"Source: {source_provider}")
        if pack.source and pack.source.url:
            lines.append(f"URL: {pack.source.url}")

        if pack.trigger_words:
            lines.append(f"Trigger Words: {', '.join(pack.trigger_words)}")

        if pack.tags:
            lines.append(f"Tags: {', '.join(pack.tags[:10])}")

        # Dependencies
        if pack.dependencies:
            lines.append(f"\nDependencies ({len(pack.dependencies)}):")
            for dep in pack.dependencies:
                kind = dep.kind.value if hasattr(dep.kind, "value") else str(dep.kind)
                filename = dep.expose.filename if dep.expose else dep.id
                lines.append(f"  - {filename} ({kind})")

        # Parameters (directly on Pack, not under resources)
        if pack.parameters:
            params = pack.parameters
            lines.append("\nGeneration Parameters:")
            if params.sampler:
                lines.append(f"  Sampler: {params.sampler}")
            if params.scheduler:
                lines.append(f"  Scheduler: {params.scheduler}")
            if params.steps:
                lines.append(f"  Steps: {params.steps}")
            if params.cfg_scale:
                lines.append(f"  CFG Scale: {params.cfg_scale}")
            if params.clip_skip:
                lines.append(f"  Clip Skip: {params.clip_skip}")
            if params.width and params.height:
                lines.append(f"  Size: {params.width}x{params.height}")
            if params.strength:
                lines.append(f"  Strength: {params.strength}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("get_pack_details failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _search_packs_impl(store: Any = None, query: str = "") -> str:
    """Search packs by name or metadata."""
    try:
        if store is None:
            store = _get_store()

        if not query:
            return "Error: query is required."

        result = store.search(query)

        if not result.items:
            return f"No packs found matching '{query}'."

        lines = [f"Found {len(result.items)} pack{'s' if len(result.items) != 1 else ''} matching '{query}':", ""]

        for i, item in enumerate(result.items, 1):
            source = f", Source: {item.provider}" if item.provider else ""
            lines.append(f"{i}. {item.pack_name} ({item.pack_type}){source}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("search_packs failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _get_pack_parameters_impl(store: Any = None, pack_name: str = "") -> str:
    """Get generation parameters for a pack."""
    try:
        if store is None:
            store = _get_store()

        if not pack_name:
            return "Error: pack_name is required."

        try:
            pack = store.get_pack(pack_name)
        except Exception as e:
            logger.debug("get_pack('%s') failed: %s", pack_name, e)
            return f"Error: Pack '{pack_name}' not found."

        params = pack.parameters

        if not params:
            return f"Pack '{pack_name}' has no generation parameters defined."

        lines = [f"Generation Parameters for {pack_name}:", ""]

        fields = [
            ("Sampler", params.sampler),
            ("Scheduler", params.scheduler),
            ("Steps", params.steps),
            ("CFG Scale", params.cfg_scale),
            ("Clip Skip", params.clip_skip),
            ("Denoise", params.denoise),
            ("Width", params.width),
            ("Height", params.height),
            ("Strength", params.strength),
            ("Eta", params.eta),
        ]

        found_any = False
        for label, value in fields:
            if value is not None:
                lines.append(f"  {label}: {value}")
                found_any = True

        # Hires settings
        if getattr(params, "hires_fix", None):
            lines.append("  Hires Fix: enabled")
            if getattr(params, "hires_scale", None):
                lines.append(f"  Hires Scale: {params.hires_scale}")
            if getattr(params, "hires_steps", None):
                lines.append(f"  Hires Steps: {params.hires_steps}")
            found_any = True

        if not found_any:
            return f"Pack '{pack_name}' has no generation parameters defined."

        return "\n".join(lines)
    except Exception as e:
        logger.error("get_pack_parameters failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _get_inventory_summary_impl(store: Any = None) -> str:
    """Get a summary of the blob inventory."""
    try:
        if store is None:
            store = _get_store()

        summary = store.get_inventory_summary()

        lines = [
            "Inventory Summary:",
            "",
            f"  Total blobs: {summary.blobs_total}",
            f"  Referenced: {summary.blobs_referenced}",
            f"  Orphan: {summary.blobs_orphan}",
            f"  Missing: {summary.blobs_missing}",
            f"  Backup only: {summary.blobs_backup_only}",
            "",
            f"  Total size: {_format_size(summary.bytes_total)}",
            f"  Referenced size: {_format_size(summary.bytes_referenced)}",
            f"  Orphan size: {_format_size(summary.bytes_orphan)}",
        ]

        if summary.disk_total is not None and summary.disk_free is not None:
            lines.append("")
            lines.append(f"  Disk total: {_format_size(summary.disk_total)}")
            lines.append(f"  Disk free: {_format_size(summary.disk_free)}")

        if summary.bytes_by_kind:
            lines.append("")
            lines.append("  Size by kind:")
            for kind, size in sorted(summary.bytes_by_kind.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"    {kind}: {_format_size(size)}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("get_inventory_summary failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _find_orphan_blobs_impl(store: Any = None) -> str:
    """Find orphan blobs not referenced by any pack."""
    try:
        if store is None:
            store = _get_store()

        from src.store.models import BlobStatus

        response = store.get_inventory(status_filter=BlobStatus.ORPHAN)
        orphans = response.items

        if not orphans:
            return "No orphan blobs found. All blobs are referenced by packs."

        total_size = sum(item.size_bytes for item in orphans)
        lines = [
            f"Found {len(orphans)} orphan blob{'s' if len(orphans) != 1 else ''} ({_format_size(total_size)} total):",
            "",
        ]

        for item in orphans:
            kind = item.kind.value if hasattr(item.kind, "value") else str(item.kind)
            lines.append(
                f"  - {item.display_name} ({kind}, {_format_size(item.size_bytes)})"
            )
            lines.append(f"    SHA256: {item.sha256[:16]}...")

        return "\n".join(lines)
    except Exception as e:
        logger.error("find_orphan_blobs failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _find_missing_blobs_impl(store: Any = None) -> str:
    """Find blobs referenced by packs but missing from local storage."""
    try:
        if store is None:
            store = _get_store()

        from src.store.models import BlobStatus

        response = store.get_inventory(status_filter=BlobStatus.MISSING)
        missing = response.items

        if not missing:
            return "No missing blobs. All referenced blobs are present locally."

        lines = [
            f"Found {len(missing)} missing blob{'s' if len(missing) != 1 else ''}:",
            "",
        ]

        for item in missing:
            kind = item.kind.value if hasattr(item.kind, "value") else str(item.kind)
            packs = ", ".join(item.used_by_packs) if item.used_by_packs else "unknown"
            lines.append(
                f"  - {item.display_name} ({kind})"
            )
            lines.append(f"    Used by: {packs}")
            lines.append(f"    SHA256: {item.sha256[:16]}...")

        return "\n".join(lines)
    except Exception as e:
        logger.error("find_missing_blobs failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _get_backup_status_impl(store: Any = None) -> str:
    """Get backup storage status."""
    try:
        if store is None:
            store = _get_store()

        status = store.get_backup_status()

        if not status.enabled:
            return "Backup storage is not enabled.\n\nConfigure backup in store settings to protect your models."

        if not status.connected:
            error_msg = f"\nError: {status.error}" if status.error else ""
            return f"Backup storage is enabled but NOT connected.{error_msg}\n\nCheck backup path and drive availability."

        lines = [
            "Backup Storage: Connected",
            "",
            f"  Path: {status.path}",
            f"  Blobs: {status.total_blobs}",
            f"  Size: {_format_size(status.total_bytes)}",
        ]

        if status.free_space is not None:
            lines.append(f"  Free space: {_format_size(status.free_space)}")

        if status.last_sync:
            lines.append(f"  Last sync: {status.last_sync}")

        lines.append("")
        lines.append(f"  Auto-backup new: {'yes' if status.auto_backup_new else 'no'}")
        lines.append(f"  Warn on last copy delete: {'yes' if status.warn_before_delete_last_copy else 'no'}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("get_backup_status failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _check_pack_updates_impl(store: Any = None, pack_name: str = "") -> str:
    """Check for available updates on packs."""
    try:
        if store is None:
            store = _get_store()

        if pack_name:
            # Check specific pack
            try:
                plan = store.check_updates(pack_name)
            except Exception as e:
                logger.debug("check_updates('%s') failed: %s", pack_name, e)
                return f"Error: Pack '{pack_name}' not found or update check failed."

            if not plan.changes:
                return f"Pack '{pack_name}' is up to date."

            lines = [f"Updates available for '{pack_name}':", ""]
            for change in plan.changes:
                lines.append(f"  - {change.dependency_id}")
                old_name = change.old.get("filename", "")
                new_name = change.new.get("filename", "")
                if old_name or new_name:
                    lines.append(f"    Current: {old_name}")
                    lines.append(f"    New: {new_name}")

            return "\n".join(lines)
        else:
            # Check all packs
            updates = store.check_all_updates()

            packs_with_updates = {
                name: plan for name, plan in updates.items() if plan.changes
            }

            if not packs_with_updates:
                return "All packs are up to date."

            lines = [
                f"{len(packs_with_updates)} pack{'s have' if len(packs_with_updates) != 1 else ' has'} updates available:",
                "",
            ]

            for name, plan in packs_with_updates.items():
                lines.append(f"  - {name}: {len(plan.changes)} update{'s' if len(plan.changes) != 1 else ''}")

            return "\n".join(lines)
    except Exception as e:
        logger.error("check_pack_updates failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _get_storage_stats_impl(store: Any = None) -> str:
    """Get detailed storage statistics."""
    try:
        if store is None:
            store = _get_store()

        summary = store.get_inventory_summary()

        lines = [
            "Storage Statistics:",
            "",
            f"  Total blobs: {summary.blobs_total}",
            f"  Total size: {_format_size(summary.bytes_total)}",
        ]

        if summary.disk_total is not None:
            used = summary.disk_total - (summary.disk_free or 0)
            pct = (used / summary.disk_total * 100) if summary.disk_total > 0 else 0
            lines.append(f"  Disk usage: {_format_size(used)} / {_format_size(summary.disk_total)} ({pct:.1f}%)")

        # Per-kind breakdown
        if summary.bytes_by_kind:
            lines.append("")
            lines.append("  Size by kind:")
            for kind, size in sorted(summary.bytes_by_kind.items(), key=lambda x: x[1], reverse=True):
                pct = (size / summary.bytes_total * 100) if summary.bytes_total > 0 else 0
                lines.append(f"    {kind}: {_format_size(size)} ({pct:.1f}%)")

        # Top 5 largest packs
        pack_names = store.list_packs()
        pack_sizes = []
        for name in pack_names:
            try:
                pack = store.get_pack(name)
                lock = store.get_pack_lock(name)
                if lock:
                    total = sum(
                        r.artifact.size_bytes or 0
                        for r in lock.resolved
                        if r.artifact and r.artifact.size_bytes
                    )
                    if total > 0:
                        pack_sizes.append((name, total))
            except Exception as e:
                logger.debug("Failed to compute size for pack '%s': %s", name, e)

        if pack_sizes:
            pack_sizes.sort(key=lambda x: x[1], reverse=True)
            top = pack_sizes[:5]
            lines.append("")
            lines.append(f"  Top {len(top)} largest packs:")
            for name, size in top:
                lines.append(f"    {name}: {_format_size(size)}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("get_storage_stats failed: %s", e, exc_info=True)
        return f"Error: {e}"


# =============================================================================
# MCP Tool registration (only when mcp is available)
# =============================================================================

if MCP_AVAILABLE:
    mcp = FastMCP("synapse-store")

    @mcp.tool()
    def list_packs(name_filter: str = "", limit: int = 20) -> str:
        """List all packs in the Synapse store. Optionally filter by name and limit results."""
        return _list_packs_impl(name_filter=name_filter, limit=limit)

    @mcp.tool()
    def get_pack_details(pack_name: str) -> str:
        """Get detailed information about a specific pack including dependencies and parameters."""
        return _get_pack_details_impl(pack_name=pack_name)

    @mcp.tool()
    def search_packs(query: str) -> str:
        """Search packs by name or dependency ID."""
        return _search_packs_impl(query=query)

    @mcp.tool()
    def get_pack_parameters(pack_name: str) -> str:
        """Get generation parameters (sampler, steps, CFG, size) for a pack."""
        return _get_pack_parameters_impl(pack_name=pack_name)

    @mcp.tool()
    def get_inventory_summary() -> str:
        """Get a summary of the blob inventory: counts, sizes, orphans, missing."""
        return _get_inventory_summary_impl()

    @mcp.tool()
    def find_orphan_blobs() -> str:
        """Find blobs not referenced by any pack (candidates for cleanup)."""
        return _find_orphan_blobs_impl()

    @mcp.tool()
    def find_missing_blobs() -> str:
        """Find blobs referenced by packs but missing from local storage."""
        return _find_missing_blobs_impl()

    @mcp.tool()
    def get_backup_status() -> str:
        """Get backup storage status: connection, blob count, free space."""
        return _get_backup_status_impl()

    @mcp.tool()
    def check_pack_updates(pack_name: str = "") -> str:
        """Check for available updates. Leave pack_name empty to check all packs. Note: checking all packs makes one API call per pack to Civitai, which may be slow for large libraries."""
        return _check_pack_updates_impl(pack_name=pack_name)

    @mcp.tool()
    def get_storage_stats() -> str:
        """Get detailed storage statistics: total size, per-kind breakdown, largest packs."""
        return _get_storage_stats_impl()
else:
    mcp = None
