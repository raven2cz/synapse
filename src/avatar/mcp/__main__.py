"""
Entry point for running the MCP store server.

Usage:
    python -m src.avatar.mcp
"""

import sys


def main():
    from .store_server import mcp, MCP_AVAILABLE

    if not MCP_AVAILABLE:
        print("Error: MCP SDK not installed. Run: pip install 'mcp>=1.0'", file=sys.stderr)
        sys.exit(1)

    if mcp is None:
        print("Error: MCP server failed to initialize.", file=sys.stderr)
        sys.exit(1)

    mcp.run()


if __name__ == "__main__":
    main()
