"""Each workshop stage exposes a known set of MCP tools, resources and prompts.

Stages register by importing modules, so each check runs in a fresh interpreter.
"""

import json
import subprocess
import sys

import pytest

PROBE = """
import asyncio, json, sys
from bridge_builder.mcp_server import load_stage, mcp
load_stage(int(sys.argv[1]), *sys.argv[2:5])
print(json.dumps({
    "tools": sorted(t.name for t in asyncio.run(mcp.list_tools())),
    "resources": sorted(str(r.uri) for r in asyncio.run(mcp.list_resources())),
    "templates": sorted(t.uri_template for t in asyncio.run(mcp.list_resource_templates())),
    "prompts": sorted(p.name for p in asyncio.run(mcp.list_prompts())),
    "instructions": mcp.instructions,
}))
"""

TOOLS = ["destroy_at", "pause", "place_girder", "place_girders", "reset", "start_train", "status"]


def _stage(n: int, tools: str = "solution", resources: str = "solution", prompts: str = "solution") -> dict:
    out = subprocess.run(
        [sys.executable, "-c", PROBE, str(n), tools, resources, prompts],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_stage_1_is_tools_only():
    s = _stage(1)
    assert s["tools"] == TOOLS
    assert s["resources"] == s["templates"] == s["prompts"] == []
    assert "bridge://" not in s["instructions"]
    # Rules only: how to build a bridge that holds is stage 2 knowledge.
    for hint in ("triang", "truss", "chain", "buckle", "shears"):
        assert hint not in s["instructions"], hint


def test_stage_2_adds_level_and_design_resources_and_no_prompt_yet():
    s = _stage(2)
    assert s["tools"] == sorted(TOOLS + ["build_design"])  # a tool that knows the designs
    assert s["resources"] == ["bridge://designs", "bridge://level"]
    assert s["templates"] == ["bridge://designs/{name}", "bridge://designs/{name}/beams"]
    assert s["prompts"] == []  # prompts are stage 3
    assert "bridge://designs" in s["instructions"]
    assert "custom design" in s["instructions"]
    assert "only triangles are rigid" in s["instructions"]
    assert "buckle under push" in s["instructions"]
    assert "bridge://clients" not in s["instructions"]


def test_stage_3_adds_both_prompts_and_the_client_briefs():
    s = _stage(3)
    assert s["resources"] == ["bridge://clients", "bridge://designs", "bridge://level"]
    assert "bridge://clients/{client}" in s["templates"]
    assert s["prompts"] == ["brief", "design"]
    assert "bridge://clients" in s["instructions"]


def test_unknown_stage_is_rejected():
    from bridge_builder.mcp_server import load_stage

    with pytest.raises(ValueError, match="stage must be 1, 2 or 3"):
        load_stage(4)


def test_each_stage_runs_your_file_for_its_exercise_and_the_reference_before_it():
    from bridge_builder.mcp_server import default_choice

    assert default_choice("tools", 1) == "mine"
    assert default_choice("tools", 2) == default_choice("tools", 3) == "solution"
    assert default_choice("resources", 2) == "mine"
    assert default_choice("resources", 3) == "solution"
    assert default_choice("prompts", 3) == "mine"


def test_the_exercise_starts_as_a_bare_server():
    s = _stage(1, "blank")
    assert s["tools"] == s["resources"] == s["templates"] == s["prompts"] == []
    assert s["instructions"].startswith("You are playing original-style Bridge Builder.")


def test_the_exercises_still_get_stage_2_and_3_on_top():
    s = _stage(3, "blank", "blank", "blank")
    assert s["tools"] == ["build_design"]
    assert s["resources"] == ["bridge://clients"]  # the briefs are not an exercise
    assert s["templates"] == ["bridge://clients/{client}"]
    assert s["prompts"] == []


def test_the_stage_3_exercise_starts_with_no_prompts():
    s = _stage(3, "solution", "solution", "blank")
    assert s["prompts"] == []
    assert "bridge://clients" in s["resources"]
    assert "/bridge-engineer:brief" in s["instructions"]


def test_the_stage_2_exercise_starts_with_no_resources():
    s = _stage(2, "solution", "blank")
    assert s["resources"] == s["templates"] == []
    assert s["prompts"] == []
    assert "bridge://designs" in s["instructions"]


def test_one_tool_module_per_process():
    code = """
from bridge_builder.mcp_server import load_stage
load_stage(1, "solution")
load_stage(2, "solution")  # the same tools again is fine
try:
    load_stage(1, "blank")
except RuntimeError as e:
    print(e)
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert "tools already loaded from 'solution'" in out.stdout
