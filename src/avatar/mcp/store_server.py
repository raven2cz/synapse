"""
Synapse Store MCP Server — Tools for AI avatar.

Provides 21 tools for querying packs, inventory, backup status,
storage statistics, Civitai interaction, workflow analysis, and
dependency resolution. Uses FastMCP with stdio transport.

All tool implementations are in _*_impl() functions for testability
without requiring the mcp package.

Tool groups:
  - Store (10): list_packs, get_pack_details, search_packs, get_pack_parameters,
    get_inventory_summary, find_orphan_blobs, find_missing_blobs, get_backup_status,
    check_pack_updates, get_storage_stats
  - Civitai (4): search_civitai, analyze_civitai_model, compare_model_versions,
    import_civitai_model
  - Workflow (4): scan_workflow, scan_workflow_file, check_workflow_availability,
    list_custom_nodes
  - Dependencies (3): resolve_workflow_dependencies, find_model_by_hash,
    suggest_asset_sources
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
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
# Civitai tool implementations (Group A)
# =============================================================================


def _search_civitai_impl(
    store: Any = None,
    civitai: Any = None,
    query: str = "",
    types: str = "",
    sort: str = "Most Downloaded",
    limit: int = 10,
) -> str:
    """Search for models on Civitai."""
    try:
        if not query:
            return "Error: query is required."

        if civitai is None:
            if store is None:
                store = _get_store()
            civitai = store.pack_service.civitai

        type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None

        response = civitai.search_models(
            query=query,
            types=type_list,
            sort=sort,
            limit=limit,
        )

        items = response.get("items", [])
        if not items:
            return f"No models found on Civitai matching '{query}'."

        lines = [f"Found {len(items)} model{'s' if len(items) != 1 else ''} on Civitai:", ""]

        for i, model in enumerate(items, 1):
            name = model.get("name", "Unknown")
            model_type = model.get("type", "Unknown")
            model_id = model.get("id", 0)
            versions = model.get("modelVersions", [])
            version_count = len(versions)
            latest = versions[0].get("name", "") if versions else ""
            base = versions[0].get("baseModel", "") if versions else ""

            lines.append(f"{i}. {name} ({model_type}, ID: {model_id})")
            info_parts = []
            if version_count:
                info_parts.append(f"{version_count} version{'s' if version_count != 1 else ''}")
            if latest:
                info_parts.append(f"Latest: {latest}")
            if base:
                info_parts.append(f"Base: {base}")
            if info_parts:
                lines.append(f"   {', '.join(info_parts)}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("search_civitai failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _analyze_civitai_model_impl(
    store: Any = None,
    civitai: Any = None,
    url: str = "",
) -> str:
    """Analyze a Civitai model: versions, files, base model, tags."""
    try:
        if not url:
            return "Error: url is required."

        if civitai is None:
            if store is None:
                store = _get_store()
            civitai = store.pack_service.civitai

        model_id, version_id = civitai.parse_civitai_url(url)
        model_data = civitai.get_model(model_id)

        name = model_data.get("name", "Unknown")
        model_type = model_data.get("type", "Unknown")
        tags = model_data.get("tags", [])
        creator = model_data.get("creator", {})
        creator_name = creator.get("username", "Unknown") if creator else "Unknown"
        description = model_data.get("description", "")
        if description and len(description) > 300:
            description = description[:300] + "..."

        lines = [
            f"Model: {name}",
            f"Type: {model_type}",
            f"ID: {model_id}",
            f"Creator: {creator_name}",
        ]

        if tags:
            lines.append(f"Tags: {', '.join(tags[:10])}")
        if description:
            lines.append(f"Description: {description}")

        versions = model_data.get("modelVersions", [])
        lines.append(f"\nVersions ({len(versions)}):")

        for v in versions:
            v_name = v.get("name", "")
            v_id = v.get("id", 0)
            base = v.get("baseModel", "")
            files = v.get("files", [])
            total_size = sum(f.get("sizeKB", 0) for f in files)
            trained_words = v.get("trainedWords", [])

            lines.append(f"\n  {v_name} (ID: {v_id})")
            if base:
                lines.append(f"    Base Model: {base}")
            if files:
                lines.append(f"    Files: {len(files)}, Total: {_format_size(int(total_size * 1024))}")
                for f in files:
                    f_name = f.get("name", "")
                    f_size = f.get("sizeKB", 0)
                    primary = " [primary]" if f.get("primary") else ""
                    lines.append(f"      - {f_name} ({_format_size(int(f_size * 1024))}){primary}")
            if trained_words:
                lines.append(f"    Trigger Words: {', '.join(trained_words)}")

        return "\n".join(lines)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        logger.error("analyze_civitai_model failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _compare_model_versions_impl(
    store: Any = None,
    civitai: Any = None,
    url: str = "",
) -> str:
    """Compare versions of a Civitai model side-by-side."""
    try:
        if not url:
            return "Error: url is required."

        if civitai is None:
            if store is None:
                store = _get_store()
            civitai = store.pack_service.civitai

        model_id, _ = civitai.parse_civitai_url(url)
        model_data = civitai.get_model(model_id)

        name = model_data.get("name", "Unknown")
        versions = model_data.get("modelVersions", [])

        if len(versions) < 2:
            return f"Model '{name}' has only {len(versions)} version — nothing to compare."

        lines = [f"Version comparison for {name}:", ""]

        # Header
        lines.append(f"{'Property':<20} | " + " | ".join(
            f"{v.get('name', '?'):<20}" for v in versions[:5]
        ))
        lines.append("-" * (22 + 23 * min(len(versions), 5)))

        # Base model
        lines.append(f"{'Base Model':<20} | " + " | ".join(
            f"{v.get('baseModel', 'N/A'):<20}" for v in versions[:5]
        ))

        # File count
        lines.append(f"{'Files':<20} | " + " | ".join(
            f"{len(v.get('files', [])):<20}" for v in versions[:5]
        ))

        # Total size
        sizes = []
        for v in versions[:5]:
            total_kb = sum(f.get("sizeKB", 0) for f in v.get("files", []))
            sizes.append(_format_size(int(total_kb * 1024)))
        lines.append(f"{'Total Size':<20} | " + " | ".join(
            f"{s:<20}" for s in sizes
        ))

        # Trained words
        lines.append(f"{'Trigger Words':<20} | " + " | ".join(
            f"{len(v.get('trainedWords', [])):<20}" for v in versions[:5]
        ))

        # Published date
        lines.append(f"{'Published':<20} | " + " | ".join(
            f"{(v.get('publishedAt', 'N/A') or 'N/A')[:10]:<20}" for v in versions[:5]
        ))

        if len(versions) > 5:
            lines.append(f"\n... and {len(versions) - 5} more versions")

        return "\n".join(lines)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        logger.error("compare_model_versions failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _import_civitai_model_impl(
    store: Any = None,
    civitai: Any = None,
    url: str = "",
    pack_name: str = "",
    download_previews: bool = True,
) -> str:
    """Import a model from Civitai into the Synapse store.

    WARNING: This modifies the store. Creates pack directory, downloads model
    files (potentially several GB).
    """
    try:
        if not url:
            return "Error: url is required."

        if store is None:
            store = _get_store()

        kwargs: dict[str, Any] = {
            "url": url,
            "download_previews": download_previews,
        }
        if pack_name:
            kwargs["pack_name"] = pack_name

        pack = store.import_civitai(**kwargs)

        lines = [
            f"Successfully imported pack: {pack.name}",
            "",
            f"  Type: {pack.pack_type.value if hasattr(pack.pack_type, 'value') else pack.pack_type}",
        ]
        if pack.base_model:
            lines.append(f"  Base Model: {pack.base_model}")
        lines.append(f"  Dependencies: {len(pack.dependencies)}")
        if pack.source and pack.source.url:
            lines.append(f"  Source: {pack.source.url}")

        return "\n".join(lines)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        logger.error("import_civitai_model failed: %s", e, exc_info=True)
        return f"Error: {e}"


# =============================================================================
# Workflow tool implementations (Group B)
# =============================================================================


def _scan_workflow_impl(
    workflow_json: str = "",
) -> str:
    """Scan a ComfyUI workflow JSON for model dependencies and custom nodes."""
    try:
        if not workflow_json:
            return "Error: workflow_json is required."

        try:
            workflow_data = json.loads(workflow_json)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON — {e}"

        from src.workflows.scanner import WorkflowScanner

        scanner = WorkflowScanner()
        result = scanner.scan_workflow(workflow_data)
        unique_assets = scanner.get_unique_assets(result)

        lines = ["Workflow Scan Results:", ""]

        if result.errors:
            lines.append(f"Warnings: {', '.join(result.errors)}")
            lines.append("")

        lines.append(f"Nodes: {len(result.all_nodes)}")
        lines.append(f"Assets: {len(unique_assets)}")
        lines.append(f"Custom Nodes: {len(result.custom_node_types)}")

        if unique_assets:
            lines.append("\nModel Dependencies:")
            for asset in unique_assets:
                kind = asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)
                lines.append(f"  - {asset.name} ({kind}, from {asset.node_type})")

        if result.custom_node_types:
            lines.append("\nCustom Node Types:")
            for node_type in sorted(result.custom_node_types):
                lines.append(f"  - {node_type}")

        if not unique_assets and not result.custom_node_types:
            lines.append("\nNo model dependencies or custom nodes found.")

        return "\n".join(lines)
    except Exception as e:
        logger.error("scan_workflow failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _scan_workflow_file_impl(
    path: str = "",
) -> str:
    """Scan a ComfyUI workflow file for dependencies."""
    try:
        if not path:
            return "Error: path is required."

        file_path = Path(path).resolve()

        # Security: only allow .json files
        if file_path.suffix.lower() != ".json":
            return f"Error: Only .json workflow files are supported, got: {file_path.suffix}"

        if not file_path.exists():
            return f"Error: File not found: {path}"

        from src.workflows.scanner import WorkflowScanner

        scanner = WorkflowScanner()
        result = scanner.scan_file(file_path)

        if result.errors:
            return f"Error scanning file: {', '.join(result.errors)}"

        unique_assets = scanner.get_unique_assets(result)

        lines = [f"Workflow: {file_path.name}", ""]
        lines.append(f"Nodes: {len(result.all_nodes)}")
        lines.append(f"Assets: {len(unique_assets)}")
        lines.append(f"Custom Nodes: {len(result.custom_node_types)}")

        if unique_assets:
            lines.append("\nModel Dependencies:")
            for asset in unique_assets:
                kind = asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)
                lines.append(f"  - {asset.name} ({kind})")

        if result.custom_node_types:
            lines.append("\nCustom Node Types:")
            for node_type in sorted(result.custom_node_types):
                lines.append(f"  - {node_type}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("scan_workflow_file failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _check_workflow_availability_impl(
    store: Any = None,
    workflow_json: str = "",
) -> str:
    """Check which workflow dependencies are locally available."""
    try:
        if not workflow_json:
            return "Error: workflow_json is required."

        try:
            workflow_data = json.loads(workflow_json)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON — {e}"

        if store is None:
            store = _get_store()

        from src.workflows.scanner import WorkflowScanner

        scanner = WorkflowScanner()
        result = scanner.scan_workflow(workflow_data)
        unique_assets = scanner.get_unique_assets(result)

        if not unique_assets:
            return "No model dependencies found in workflow."

        # Cross-reference with inventory
        inventory_response = store.get_inventory()
        local_names = set()
        for item in inventory_response.items:
            local_names.add(item.display_name)

        available = []
        missing = []
        for asset in unique_assets:
            if asset.name in local_names:
                available.append(asset)
            else:
                missing.append(asset)

        lines = [f"Dependency Availability ({len(unique_assets)} total):", ""]

        if available:
            lines.append(f"Available locally ({len(available)}):")
            for a in available:
                kind = a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type)
                lines.append(f"  ✓ {a.name} ({kind})")

        if missing:
            lines.append(f"\nMissing ({len(missing)}):")
            for m in missing:
                kind = m.asset_type.value if hasattr(m.asset_type, "value") else str(m.asset_type)
                lines.append(f"  ✗ {m.name} ({kind})")

        if not missing:
            lines.append("\nAll dependencies are available locally!")

        return "\n".join(lines)
    except Exception as e:
        logger.error("check_workflow_availability failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _list_custom_nodes_impl(
    workflow_json: str = "",
) -> str:
    """List custom node packages required by a workflow with git URLs."""
    try:
        if not workflow_json:
            return "Error: workflow_json is required."

        try:
            workflow_data = json.loads(workflow_json)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON — {e}"

        from src.workflows.scanner import WorkflowScanner
        from src.workflows.resolver import DependencyResolver

        scanner = WorkflowScanner()
        result = scanner.scan_workflow(workflow_data)

        if not result.custom_node_types:
            return "No custom nodes found in workflow."

        resolver = DependencyResolver()
        node_deps = resolver.resolve_custom_nodes(result.custom_node_types)

        lines = [f"Custom Nodes ({len(result.custom_node_types)} types, {len(node_deps)} packages):", ""]

        if node_deps:
            lines.append("Resolved packages:")
            for dep in node_deps:
                lines.append(f"  - {dep.name}")
                lines.append(f"    URL: {dep.git_url}")
                if dep.pip_requirements:
                    lines.append(f"    Pip: {', '.join(dep.pip_requirements)}")

        # Show unresolved node types — check both KNOWN_CUSTOM_NODES and registry
        resolved_types = set()
        for nt in result.custom_node_types:
            if nt.startswith("cnr:"):
                continue
            if nt in DependencyResolver.KNOWN_CUSTOM_NODES:
                resolved_types.add(nt)
            elif resolver.node_registry.find_pack_for_node(nt):
                resolved_types.add(nt)

        truly_unresolved = result.custom_node_types - resolved_types - {
            nt for nt in result.custom_node_types if nt.startswith("cnr:")
        }
        if truly_unresolved:
            lines.append(f"\nUnresolved node types ({len(truly_unresolved)}):")
            for nt in sorted(truly_unresolved):
                lines.append(f"  ? {nt}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("list_custom_nodes failed: %s", e, exc_info=True)
        return f"Error: {e}"


# =============================================================================
# Dependency resolution tool implementations (Group C)
# =============================================================================


def _resolve_workflow_deps_impl(
    workflow_json: str = "",
) -> str:
    """Resolve all workflow dependencies with download sources."""
    try:
        if not workflow_json:
            return "Error: workflow_json is required."

        try:
            workflow_data = json.loads(workflow_json)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON — {e}"

        from src.workflows.scanner import WorkflowScanner
        from src.workflows.resolver import DependencyResolver

        scanner = WorkflowScanner()
        result = scanner.scan_workflow(workflow_data)

        resolver = DependencyResolver()
        asset_deps, node_deps = resolver.resolve_workflow_dependencies(result)

        if not asset_deps and not node_deps:
            return "No dependencies found in workflow."

        lines = ["Resolved Dependencies:", ""]

        if asset_deps:
            lines.append(f"Model Assets ({len(asset_deps)}):")
            for dep in asset_deps:
                kind = dep.asset_type.value if hasattr(dep.asset_type, "value") else str(dep.asset_type)
                source = dep.source.value if hasattr(dep.source, "value") else str(dep.source)
                lines.append(f"  - {dep.name} ({kind})")
                lines.append(f"    Source: {source}")
                if hasattr(dep, "huggingface") and dep.huggingface:
                    lines.append(f"    HF Repo: {dep.huggingface.repo_id}")
                    lines.append(f"    HF File: {dep.huggingface.filename}")

        if node_deps:
            lines.append(f"\nCustom Node Packages ({len(node_deps)}):")
            for dep in node_deps:
                lines.append(f"  - {dep.name}")
                lines.append(f"    Git: {dep.git_url}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("resolve_workflow_deps failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _find_model_by_hash_impl(
    store: Any = None,
    civitai: Any = None,
    hash_value: str = "",
) -> str:
    """Find a model on Civitai by SHA256 or AutoV2 hash."""
    try:
        if not hash_value:
            return "Error: hash_value is required."

        if civitai is None:
            if store is None:
                store = _get_store()
            civitai = store.pack_service.civitai

        result = civitai.get_model_by_hash(hash_value)

        if result is None:
            return f"No model found for hash: {hash_value}"

        lines = [f"Found model version for hash {hash_value[:16]}...:", ""]
        lines.append(f"  Version: {result.name} (ID: {result.id})")
        lines.append(f"  Model ID: {result.model_id}")
        if hasattr(result, "base_model") and result.base_model:
            lines.append(f"  Base Model: {result.base_model}")
        if hasattr(result, "model_name"):
            lines.append(f"  Model Name: {result.model_name}")

        if hasattr(result, "files") and result.files:
            lines.append(f"  Files: {len(result.files)}")
            for f in result.files:
                f_name = f.get("name", "") if isinstance(f, dict) else getattr(f, "name", "")
                lines.append(f"    - {f_name}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("find_model_by_hash failed: %s", e, exc_info=True)
        return f"Error: {e}"


def _suggest_asset_sources_impl(
    asset_names: str = "",
) -> str:
    """Suggest download sources for asset names."""
    try:
        if not asset_names:
            return "Error: asset_names is required (comma-separated list)."

        names = [n.strip() for n in asset_names.split(",") if n.strip()]
        if not names:
            return "Error: No valid asset names provided."

        from src.workflows.scanner import ScannedAsset
        from src.workflows.resolver import DependencyResolver
        from src.core.models import AssetType

        resolver = DependencyResolver()

        lines = [f"Source suggestions for {len(names)} asset{'s' if len(names) != 1 else ''}:", ""]

        for name in names:
            # Create a minimal ScannedAsset for pattern matching
            asset = ScannedAsset(
                name=name,
                asset_type=AssetType.UNKNOWN,
                node_type="Unknown",
                node_id=0,
            )
            source = resolver.suggest_asset_source(asset)
            source_str = source.value if hasattr(source, "value") else str(source)

            lines.append(f"  - {name}")
            lines.append(f"    Suggested source: {source_str}")

            # Add extra info for known HF models
            if name in resolver.KNOWN_HF_MODELS:
                hf_info = resolver.KNOWN_HF_MODELS[name]
                lines.append(f"    HF Repo: {hf_info['repo_id']}")
                lines.append(f"    HF File: {hf_info['filename']}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("suggest_asset_sources failed: %s", e, exc_info=True)
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

    # ----- Civitai tools (Group A) -----

    @mcp.tool()
    def search_civitai(query: str, types: str = "", sort: str = "Most Downloaded", limit: int = 10) -> str:
        """Search for models on Civitai. Filter by types (comma-separated: LORA, Checkpoint, etc.) and sort order."""
        return _search_civitai_impl(query=query, types=types, sort=sort, limit=limit)

    @mcp.tool()
    def analyze_civitai_model(url: str) -> str:
        """Analyze a Civitai model URL: all versions, files, sizes, base model, trigger words, tags."""
        return _analyze_civitai_model_impl(url=url)

    @mcp.tool()
    def compare_model_versions(url: str) -> str:
        """Compare all versions of a Civitai model side-by-side: base model, size, files, trigger words."""
        return _compare_model_versions_impl(url=url)

    @mcp.tool()
    def import_civitai_model(url: str, pack_name: str = "", download_previews: bool = True) -> str:
        """Import a model from Civitai into the Synapse store. WARNING: This modifies the store — creates pack directory and downloads model files (potentially several GB)."""
        return _import_civitai_model_impl(url=url, pack_name=pack_name, download_previews=download_previews)

    # ----- Workflow tools (Group B) -----

    @mcp.tool()
    def scan_workflow(workflow_json: str) -> str:
        """Analyze a ComfyUI workflow JSON string for model dependencies and custom node requirements."""
        return _scan_workflow_impl(workflow_json=workflow_json)

    @mcp.tool()
    def scan_workflow_file(path: str) -> str:
        """Analyze a ComfyUI workflow file (.json) for model dependencies and custom nodes."""
        return _scan_workflow_file_impl(path=path)

    @mcp.tool()
    def check_workflow_availability(workflow_json: str) -> str:
        """Check which workflow model dependencies are locally available in the Synapse store."""
        return _check_workflow_availability_impl(workflow_json=workflow_json)

    @mcp.tool()
    def list_custom_nodes(workflow_json: str) -> str:
        """List custom node packages required by a workflow with git repository URLs."""
        return _list_custom_nodes_impl(workflow_json=workflow_json)

    # ----- Dependency resolution tools (Group C) -----

    @mcp.tool()
    def resolve_workflow_dependencies(workflow_json: str) -> str:
        """Resolve all workflow dependencies: maps assets to download sources (Civitai/HuggingFace/local) and custom nodes to git repos."""
        return _resolve_workflow_deps_impl(workflow_json=workflow_json)

    @mcp.tool()
    def find_model_by_hash(hash_value: str) -> str:
        """Find a model on Civitai by SHA256 or AutoV2 hash. Useful for identifying unknown model files."""
        return _find_model_by_hash_impl(hash_value=hash_value)

    @mcp.tool()
    def suggest_asset_sources(asset_names: str) -> str:
        """Suggest download sources for model files. Provide comma-separated asset names (e.g. 'model.safetensors, vae.safetensors')."""
        return _suggest_asset_sources_impl(asset_names=asset_names)
else:
    mcp = None
