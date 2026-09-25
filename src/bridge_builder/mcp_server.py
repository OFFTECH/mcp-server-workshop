"""The bare MCP server for the live Bridge Builder window: a name, instructions, a line to the game.

This is where the workshop starts. The server runs and Claude can connect to it,
but it has no tools yet, so the model can read the instructions and do nothing
else. Everything the model can do is added on top, one module per stage
(``load_stage``, or ``python -m bridge_builder --stage N``):

1. tools: ``my_tools.py`` (yours to finish), or ``solution/mcp_tools.py``.
2. resources: ``my_resources.py`` (yours to write), or ``solution/mcp_resources.py``:
   level facts and the tested reference designs. ``mcp_designs`` adds the
   stage 2 instructions and the ``build_design`` tool.
3. prompts: ``my_prompts.py`` (yours to finish), or ``solution/mcp_prompts.py``:
   ``design`` builds one reference design, ``brief`` follows a client's brief.
   ``mcp_clients`` publishes the client briefs as resources.

Each stage runs your file for that stage's exercise and the reference answers for
the stages before it, so everyone starts a stage from the same working server.
``--solution`` uses the reference everywhere, ``--mine`` uses your files everywhere.
"""

from __future__ import annotations

import importlib
from typing import Any

from mcp.server import MCPServer

from bridge_builder.materials import MATERIALS

_wood, _steel, _titanium = MATERIALS["wood"], MATERIALS["steel"], MATERIALS["titanium"]

# The rules of the game only: what is allowed, what it costs, how it is scored. How to
# build a bridge that holds is knowledge, and arrives in stage 2 (DESIGN_ADVICE), so with
# tools alone the model has to improvise.
mcp = MCPServer(
    "bridge-engineer",
    instructions=(
        "You are playing original-style Bridge Builder. Units are metres, y-up. "
        "Red anchors sit on both banks at y=3: x=-14,-12,-10,-8,-6 and x=6,8,10,12,14. "
        "Beams only join neighbouring 2 m grid nodes (2 m ortho or 2√2 m diagonal). "
        "A beam must start from an existing node (an anchor or a joint you already built). "
        "Nodes exist at y=3,5,7,... everywhere, and also below the deck inside the gap only: "
        "x=-4,-2,0,2,4 at y=1 and y=-1 (the wall faces x=±6 and the banks are solid below y=3). "
        "Beams that end on the same node are pinned there automatically. "
        "Beams carry pull or push along their length and break when it is too much: "
        f"steel (cost {_steel.cost}, {_steel.strength:g}x strength, default), "
        f"wood (cost {_wood.cost}, {_wood.strength:g}x, the sustainable choice), "
        f"titanium (cost {_titanium.cost}, {_titanium.strength:g}x, lighter than steel). "
        "Level budget is 30000. Stay under budget. "
        "Score on a successful crossing is leftover budget (cheaper bridge = higher score). "
        "After building, call start_train."
    ),
)

# How to build a bridge that holds. Stage 2 adds it to the instructions with the designs.
DESIGN_ADVICE = (
    "Beams pinned at a node turn freely, so only triangles are rigid: a four-sided panel "
    "of beams shears flat. Long beams (the 2.83 m diagonals) buckle under push at half the "
    "load a 2 m beam takes. A straight deck across the gap is a chain: it sags and snaps "
    "under the train; a triangulated truss holds, and the nodes below the deck in the gap "
    "let you hang an inverted truss under the road."
)

_api: Any = None


def bind_api(api: Any) -> None:
    global _api
    _api = api


def _submit(op: str, payload: dict | None = None) -> dict:
    """Send one command to the game and wait for its result dict.

    ``op`` is the game operation (``"place_girder"``, ``"start_train"``, ...), ``payload``
    its arguments. The result is ``{"ok": True, ...}`` or ``{"ok": False, "error": ...}``.
    """
    if _api is None:
        return {"ok": False, "error": "game is not running"}
    return _api.submit(op, payload or {})


def add_instructions(text: str) -> None:
    """Append a later stage's guidance to the server instructions the client receives.

    MCPServer exposes ``instructions`` read-only; the low-level server holds the
    string it sends to the client, so a stage extends that.
    """
    low = mcp._lowlevel_server
    low.instructions = f"{low.instructions} {text}"


# The exercise files, one per part, and the stage each part first appears in. Importing a
# module registers its tools or resources on ``mcp``. "blank" is the untouched exercise, for tests.
PARTS = {
    "tools": (1, {
        "mine": "bridge_builder.my_tools",
        "solution": "bridge_builder.solution.mcp_tools",
        "blank": "bridge_builder.solution.my_tools_blank",
    }),
    "resources": (2, {
        "mine": "bridge_builder.my_resources",
        "solution": "bridge_builder.solution.mcp_resources",
        "blank": "bridge_builder.solution.my_resources_blank",
    }),
    "prompts": (3, {
        "mine": "bridge_builder.my_prompts",
        "solution": "bridge_builder.solution.mcp_prompts",
        "blank": "bridge_builder.solution.my_prompts_blank",
    }),
}
TOOL_MODULES = PARTS["tools"][1]
RESOURCE_MODULES = PARTS["resources"][1]

# Workshop stages: the modules that come with a stage besides the exercise files.
STAGE_MODULES = {
    1: [],
    2: ["bridge_builder.mcp_designs"],
    3: ["bridge_builder.mcp_designs", "bridge_builder.mcp_clients"],
}

_loaded: dict[str, str] = {}


def default_choice(part: str, stage: int) -> str:
    """Your file in the stage that introduces the part; the reference answers after it."""
    return "mine" if stage == PARTS[part][0] else "solution"


def default_tools(stage: int) -> str:
    return default_choice("tools", stage)


def load_stage(
    stage: int, tools: str | None = None, resources: str | None = None, prompts: str | None = None
) -> dict[str, str]:
    """Switch the server on up to ``stage`` (1 tools, 2 + resources, 3 + prompts).

    ``tools``, ``resources`` and ``prompts`` pick where each part comes from ("mine", "solution" or
    "blank"); by default ``default_choice``. Returns the module each part was loaded from.
    """
    if stage not in STAGE_MODULES:
        raise ValueError(f"stage must be 1, 2 or 3, not {stage!r}")
    loaded = {}
    for part, choice in (("tools", tools), ("resources", resources), ("prompts", prompts)):
        first, modules = PARTS[part]
        if stage < first:
            continue
        choice = choice or default_choice(part, stage)
        if choice not in modules:
            raise ValueError(f"{part} must be one of {', '.join(modules)}, not {choice!r}")
        # Two modules of one part would both register on the one server: one per process.
        if _loaded.get(part, choice) != choice:
            raise RuntimeError(f"{part} already loaded from {_loaded[part]!r}; restart to switch")
        importlib.import_module(modules[choice])
        _loaded[part] = choice
        loaded[part] = modules[choice]
    for module in STAGE_MODULES[stage]:
        importlib.import_module(module)
    return loaded
