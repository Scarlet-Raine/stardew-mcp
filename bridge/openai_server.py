"""Entry wrapper: expose tools as HTTP endpoints (OpenAI-style schemas).

GET  /v1/tools -> function schema list
POST /v1/tool  -> {"name": "...", "arguments": {...}}
"""
from __future__ import annotations

import sys
from stardew_bridge.cli import main

if __name__ == "__main__":
    sys.exit(main(["--mode", "http", *sys.argv[1:]]))