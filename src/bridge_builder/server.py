"""One process: pygame on the main thread, the MCP HTTP server on a daemon thread.

``--stage N`` picks how much of the MCP server is switched on (workshop stages):
1 tools, 2 + level and design resources and the design prompt, 3 + client briefs.
"""

from __future__ import annotations

import argparse
import socket
import threading
from pathlib import Path

from bridge_builder.api import GameAPI
from bridge_builder.client import register_claude
from bridge_builder.game import Game
from bridge_builder.mcp_tools import STAGE_MODULES, bind_api, load_stage, mcp
from bridge_builder.view import run

HOST, PORT = "127.0.0.1", 8765


def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bridge-builder", description=__doc__)
    parser.add_argument(
        "--stage",
        type=int,
        choices=sorted(STAGE_MODULES),
        default=max(STAGE_MODULES),
        help="workshop stage: 1 tools, 2 + designs, 3 + client briefs (default: 3)",
    )
    parser.add_argument("--stdio", action="store_true", help="also serve MCP over stdio")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    load_stage(args.stage)
    if not port_free(HOST, PORT):
        raise SystemExit(f"port {PORT} already in use; stop the other bridge-engineer first")
    game = Game()
    api = GameAPI(game)
    bind_api(api)
    register_claude(project_root=Path(__file__).resolve().parents[2], include_desktop=True)
    thread = threading.Thread(
        target=lambda: mcp.run(transport="streamable-http", host=HOST, port=PORT),
        daemon=True,
        name="mcp-http",
    )
    thread.start()
    if args.stdio:
        threading.Thread(
            target=lambda: mcp.run(transport="stdio"),
            daemon=True,
            name="mcp-stdio",
        ).start()
    run(game, api=api, mcp_ok=thread.is_alive)
