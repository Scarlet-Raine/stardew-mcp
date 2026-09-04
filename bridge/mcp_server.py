"""Entry wrapper: run the MCP server.

Usage: python -m mcp_server, or python mcp_server.py --ws-url ws://localhost:8765/game
"""
from __future__ import annotations

import sys
from stardew_bridge.cli import main

if __name__ == "__main__":
    sys.exit(main(["--mode", "mcp", *sys.argv[1:]]))