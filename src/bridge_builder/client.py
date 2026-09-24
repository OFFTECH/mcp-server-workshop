"""Sync helper so notebook cells can call the running MCP server."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from mcp import Client

MCP_URL = "http://127.0.0.1:8765/mcp"
SERVER_NAME = "bridge-engineer"

_MCP_SERVER = {
    "type": "http",
    "url": MCP_URL,
}


def _extract(result: Any) -> dict[str, Any]:
    text = None
    content = getattr(result, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", None)
    if text is None:
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            if "result" in structured and isinstance(structured["result"], str):
                text = structured["result"]
            else:
                return structured
    if text is None:
        return {"ok": False, "error": f"unrecognised tool result: {result!r}"}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"ok": True, "text": text}
    if isinstance(parsed, dict):
        return parsed
    return {"ok": True, "value": parsed}


async def _call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with Client(MCP_URL) as client:
        result = await client.call_tool(name, arguments)
        return _extract(result)


def _sync(make_coro: Any) -> Any:
    """Run ``make_coro()`` to completion; inside Jupyter's running loop, on a worker thread."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(make_coro())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(make_coro())).result(timeout=10)


def list_tools() -> list[str]:
    """Names of tools currently registered on the running game server."""

    async def runner() -> list[str]:
        async with Client(MCP_URL) as client:
            result = await client.list_tools()
            tools = getattr(result, "tools", result)
            return [getattr(t, "name", str(t)) for t in tools]

    return _sync(runner)


def call_tool(name: str, **kwargs: Any) -> dict[str, Any]:
    """Blocking call to the running game MCP server. Safe inside Jupyter."""
    return _sync(lambda: _call(name, kwargs))


def list_resources() -> list[str]:
    """URIs of the resources and resource templates the running server publishes."""

    async def runner() -> list[str]:
        async with Client(MCP_URL) as client:
            fixed = [str(r.uri) for r in (await client.list_resources()).resources]
            templates = [t.uri_template for t in (await client.list_resource_templates()).resource_templates]
            return fixed + templates

    return _sync(runner)


def read_resource(uri: str) -> str:
    """Text of one resource, exactly as the model would read it."""

    async def runner() -> str:
        async with Client(MCP_URL) as client:
            result = await client.read_resource(uri)
            return "\n".join(getattr(c, "text", "") for c in result.contents)

    return _sync(runner)


def list_prompts() -> list[str]:
    """Names of the prompts (slash commands) the running server publishes."""

    async def runner() -> list[str]:
        async with Client(MCP_URL) as client:
            return [p.name for p in (await client.list_prompts()).prompts]

    return _sync(runner)


def _render_prompt(result: Any) -> str:
    parts = []
    for message in result.messages:
        content = message.content
        if getattr(content, "type", "") == "resource":
            parts.append(f"[{message.role}] resource {content.resource.uri}\n{content.resource.text}")
        else:
            parts.append(f"[{message.role}] {content.text}")
    return "\n\n".join(parts)


def get_prompt(name: str, **arguments: str) -> str:
    """The messages a prompt puts in front of the model, as readable text."""

    async def runner() -> str:
        async with Client(MCP_URL) as client:
            return _render_prompt(await client.get_prompt(name, arguments))

    return _sync(runner)


def _merge_mcp_json(path: Path) -> None:
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    servers = data.setdefault("mcpServers", {})
    servers[SERVER_NAME] = dict(_MCP_SERVER)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def find_project_root(start: Path | None = None) -> Path:
    """The nearest folder at or above ``start`` (default: cwd) holding ``pyproject.toml``.

    Jupyter runs the notebook with ``notebooks/`` as the working directory, but
    Claude Code reads ``.mcp.json`` from the repo root. Falls back to ``start``.
    """
    here = Path(start) if start is not None else Path.cwd()
    for folder in (here, *here.parents):
        if (folder / "pyproject.toml").is_file():
            return folder
    return here


def register_claude(
    project_root: Path | None = None,
    include_desktop: bool | None = None,
) -> dict[str, Any]:
    """Write project ``.mcp.json`` so Claude Code can discover the live game server.

    Without ``project_root`` it writes to the repo root (see ``find_project_root``),
    also merges into Claude Desktop config if present, and runs ``claude mcp add``
    when the CLI is on PATH.
    """
    root = Path(project_root) if project_root is not None else find_project_root()
    if include_desktop is None:
        include_desktop = project_root is None
    written: list[str] = []
    project_cfg = root / ".mcp.json"
    _merge_mcp_json(project_cfg)
    written.append(str(project_cfg))

    if include_desktop:
        desktop = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
        if desktop.parent.is_dir():
            _merge_mcp_json(desktop)
            written.append(str(desktop))

    claude = shutil.which("claude") if project_root is None else None
    cli: str | None = None
    if claude:
        try:
            proc = subprocess.run(
                [
                    claude,
                    "mcp",
                    "add",
                    "--transport",
                    "http",
                    SERVER_NAME,
                    MCP_URL,
                    "-s",
                    "project",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=str(root),
                timeout=15,
            )
            cli = (proc.stdout or proc.stderr or "").strip() or f"exit {proc.returncode}"
        except (OSError, subprocess.TimeoutExpired) as exc:
            cli = str(exc)

    return {
        "ok": True,
        "url": MCP_URL,
        "wrote": written,
        "claude_cli": cli,
        "hint": "If Claude Code is already open, reload MCP servers or reconnect once.",
    }

