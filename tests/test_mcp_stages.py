"""Each workshop stage exposes a known set of MCP tools, resources and prompts.

Stages register by importing modules, so each check runs in a fresh interpreter.
"""

import json
import subprocess
import sys

import pytest

PROBE = """
import asyncio, json, sys
from bridge_builder.mcp_tools import load_stage, mcp
load_stage(int(sys.argv[1]))
print(json.dumps({
    "tools": sorted(t.name for t in asyncio.run(mcp.list_tools())),
    "resources": sorted(str(r.uri) for r in asyncio.run(mcp.list_resources())),
    "templates": sorted(t.uri_template for t in asyncio.run(mcp.list_resource_templates())),
    "prompts": sorted(p.name for p in asyncio.run(mcp.list_prompts())),
    "instructions": mcp.instructions,
}))
"""

TOOLS = ["add_joint", "destroy_at", "pause", "place_girder", "place_girders", "reset", "start_train", "status"]


def _stage(n: int) -> dict:
    out = subprocess.run(
        [sys.executable, "-c", PROBE, str(n)], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_stage_1_is_tools_only():
    s = _stage(1)
    assert s["tools"] == TOOLS
    assert s["resources"] == s["templates"] == s["prompts"] == []
    assert "bridge://" not in s["instructions"]


def test_stage_2_adds_level_and_design_resources_and_the_design_prompt():
    s = _stage(2)
    assert s["tools"] == sorted(TOOLS + ["build_design"])  # a tool that knows the designs
    assert s["resources"] == ["bridge://designs", "bridge://level"]
    assert s["templates"] == ["bridge://designs/{name}", "bridge://designs/{name}/beams"]
    assert s["prompts"] == ["design"]
    assert "bridge://designs" in s["instructions"]
    assert "custom design" in s["instructions"]
    assert "bridge://clients" not in s["instructions"]


def test_stage_3_adds_client_briefs_and_the_brief_prompt():
    s = _stage(3)
    assert s["resources"] == ["bridge://clients", "bridge://designs", "bridge://level"]
    assert "bridge://clients/{client}" in s["templates"]
    assert s["prompts"] == ["brief", "design"]
    assert "bridge://clients" in s["instructions"]


def test_unknown_stage_is_rejected():
    from bridge_builder.mcp_tools import load_stage

    with pytest.raises(ValueError, match="stage must be 1, 2 or 3"):
        load_stage(4)
