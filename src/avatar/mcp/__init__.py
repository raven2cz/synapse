"""
MCP servers providing Synapse tools for the AI avatar.

All 21 tools live in store_server.py:
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

import logging

from .store_server import MCP_AVAILABLE

logger = logging.getLogger(__name__)

store_mcp = None
if MCP_AVAILABLE:
    try:
        from .store_server import mcp as store_mcp
        logger.debug("MCP store server loaded (21 tools)")
    except Exception as e:
        logger.warning("Failed to import MCP store server: %s", e)
        store_mcp = None
else:
    logger.debug("MCP SDK not installed — store tools unavailable")

__all__ = ["MCP_AVAILABLE", "store_mcp"]
