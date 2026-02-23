"""
MCP servers providing Synapse tools for the AI avatar.

Servers:
  - store_server: Pack, inventory, backup, statistics tools
  - import_server: Civitai import and analysis tools (Iterace 6)
  - workflow_server: ComfyUI workflow generation tools (Iterace 6)
  - dependency_server: Model dependency resolution tools (Iterace 6)
"""

import logging

from .store_server import MCP_AVAILABLE

logger = logging.getLogger(__name__)

store_mcp = None
if MCP_AVAILABLE:
    try:
        from .store_server import mcp as store_mcp
    except Exception as e:
        logger.warning("Failed to import MCP store server: %s", e)
        store_mcp = None

__all__ = ["MCP_AVAILABLE", "store_mcp"]
