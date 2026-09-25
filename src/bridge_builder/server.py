"""One process: pygame on the main thread, the MCP HTTP server on a daemon thread.

``--stage N`` picks how much of the MCP server is switched on (workshop stages):
1 tools, 2 + level and design resources, 3 + prompts and client briefs.
Each stage serves your file for that stage's exercise (``my_tools.py`` in stage 1,
``my_resources.py`` in stage 2, ``my_prompts.py`` in stage 3) and the reference
answers for the stages before it.
``--solution`` serves the reference everywhere, ``--mine`` your files everywhere.
"""

from __future__ import annotations

import argparse
import asyncio
import socket
import threading
import traceback
from pathlib import Path

from bridge_builder.api import GameAPI
from bridge_builder.client import register_claude
from bridge_builder.game import Game
from bridge_builder.mcp_server import STAGE_MODULES, bind_api, load_stage, mcp
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
        help="workshop stage: 1 tools, 2 + resources, 3 + prompts (default: 3)",
    )
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument(
        "--solution", dest="choice", action="store_const", const="solution",
        help="serve the reference answers (solution/) instead of your files",
    )
    choice.add_argument(
        "--mine", dest="choice", action="store_const", const="mine",
        help="serve your files (my_tools.py, my_resources.py, my_prompts.py) in every stage",
    )
    parser.add_argument("--stdio", action="store_true", help="also serve MCP over stdio")
    return parser.parse_args(argv)


EXERCISE_FILES = ("my_tools.py", "my_resources.py", "my_prompts.py")


def _file(module: str) -> str:
    return module.removeprefix("bridge_builder.").replace(".", "/") + ".py"


def _published(part: str, module: str) -> list[str]:
    """The tool names or resource URIs that ``module`` registered on the server."""
    if part == "tools":
        return sorted(t.name for t in asyncio.run(mcp.list_tools()))
    if part == "prompts":
        return sorted(p.name for p in asyncio.run(mcp.list_prompts()))
    manager = mcp._resource_manager
    items = [*manager._resources.values(), *manager._templates.values()]
    return sorted(str(getattr(i, "uri", None) or i.uri_template) for i in items if i.fn.__module__ == module)


def load(stage: int, choice: str | None) -> None:
    """Load the stage and say what is live, or explain which exercise file would not load."""
    try:
        loaded = load_stage(stage, tools=choice, resources=choice, prompts=choice)
    except Exception as exc:
        frames = traceback.extract_tb(exc.__traceback__)
        if isinstance(exc, SyntaxError) and exc.filename:
            frames.append(traceback.FrameSummary(exc.filename, exc.lineno or 0, ""))
        mine = [f for f in frames if Path(f.filename).name in EXERCISE_FILES]
        if not mine:
            raise
        raise SystemExit(
            f"{Path(mine[-1].filename).name} does not load (line {mine[-1].lineno}): "
            f"{type(exc).__name__}: {exc}\n"
            "Fix it and start again, or run with --solution to use the reference answers."
        ) from exc
    for part, module in loaded.items():
        names = _published(part, module)
        print(f"bridge-engineer: stage {stage}, {part} from {_file(module)}: {', '.join(names) or 'none yet'}")


def main() -> None:
    args = parse_args()
    load(args.stage, args.choice)
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
