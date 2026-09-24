"""MCP server for the live Bridge Builder window. Workshop stage 1: tools.

The server grows in three stages, one module each; a stage is switched on by
importing its module (``load_stage``, or ``python -m bridge_builder --stage N``):

1. ``mcp_tools``   (this file) tools: the model can look, build and test.
2. ``mcp_designs`` resources: level facts and tested reference designs,
   plus the ``design`` prompt.
3. ``mcp_clients`` client briefs: a client's requirements as resources,
   plus the ``brief`` prompt that makes the model follow them.

Tools act. A tool is an ordinary Python function plus ``@mcp.tool()``. The SDK
builds the schema the model sees from the function itself:

* the function name is the tool name,
* the docstring is the tool description,
* type hints become the input schema: ``Annotated[..., Field(description=...)]``
  documents an argument, ``Literal[...]`` becomes an enum, a default makes it optional,
* ``ToolAnnotations`` tell the client how the tool behaves (read-only, destructive, ...).

Every tool forwards to the game through ``GameAPI`` and returns the game's
result dict (``{"ok": true, ...}`` or ``{"ok": false, "error": ...}``),
which the SDK sends back to the model as JSON.

Resources (stage 2) and prompts (stages 2 and 3) are explained in their modules.
"""

from __future__ import annotations

import importlib
from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from bridge_builder.materials import MATERIALS

_wood, _steel, _titanium = MATERIALS["wood"], MATERIALS["steel"], MATERIALS["titanium"]

mcp = MCPServer(
    "bridge-engineer",
    instructions=(
        "You are playing original-style Bridge Builder. Units are metres, y-up. "
        "Red anchors sit on both banks at y=3: x=-14,-12,-10,-8,-6 and x=6,8,10,12,14. "
        "Beams only join neighbouring 2 m grid nodes (2 m ortho or 2√2 m diagonal). "
        "A beam must start from an existing node (an anchor or a joint you already built). "
        "Nodes exist at y=3,5,7,... everywhere, and also below the deck inside the gap only: "
        "x=-4,-2,0,2,4 at y=1 and y=-1 (the wall faces x=±6 and the banks are solid below y=3), "
        "so you can hang an inverted truss under the road. "
        "Beams that end on the same node are pinned there automatically and turn freely, "
        "so only triangles are rigid: a four-sided panel of beams shears flat. "
        "Beams carry pull or push along their length and break when it is too much: "
        f"steel (cost {_steel.cost}, {_steel.strength:g}x strength, default), "
        f"wood (cost {_wood.cost}, {_wood.strength:g}x, the sustainable choice), "
        f"titanium (cost {_titanium.cost}, {_titanium.strength:g}x, lighter than steel). "
        "Long beams (the 2.83 m diagonals) buckle under push at half the load a 2 m beam "
        "takes. Level budget is 30000. Stay under budget. "
        "Score on a successful crossing is leftover budget (cheaper bridge = higher score). "
        "A straight steel deck across the gap is a chain: it sags and snaps under the train; "
        "a triangulated truss will hold. After building, call start_train."
    ),
)

_api: Any = None


def bind_api(api: Any) -> None:
    global _api
    _api = api


def _submit(op: str, payload: dict | None = None) -> dict:
    if _api is None:
        return {"ok": False, "error": "game is not running"}
    return _api.submit(op, payload or {})


def add_instructions(text: str) -> None:
    """Append a later stage's guidance to the server instructions the client receives.

    MCPServer exposes ``instructions`` read-only; the low-level server holds the
    string it sends in the initialize response, so a stage extends that.
    """
    low = mcp._lowlevel_server
    low.instructions = f"{low.instructions} {text}"


# Workshop stages: importing a stage's module registers its resources and prompts.
STAGE_MODULES = {
    1: [],
    2: ["bridge_builder.mcp_designs"],
    3: ["bridge_builder.mcp_designs", "bridge_builder.mcp_clients"],
}


def load_stage(stage: int) -> None:
    """Switch the server on up to ``stage`` (1 tools, 2 + designs, 3 + client briefs)."""
    if stage not in STAGE_MODULES:
        raise ValueError(f"stage must be 1, 2 or 3, not {stage!r}")
    for module in STAGE_MODULES[stage]:
        importlib.import_module(module)


# What status returns: only what changes during play. Level facts are a resource.
LIVE_FIELDS = (
    "ok", "error", "paused", "train", "train_x", "train_y",
    "cost", "remaining", "score", "girders", "joints", "peak_load",
)

# Reusable argument types: the description travels with the type into the schema.
Metres = Annotated[float, Field(description="Coordinate in metres, y-up. Grid nodes are every 2 m.")]
Material = Literal["wood", "steel", "titanium"]


# ---------------------------------------------------------------------------
# Look
# ---------------------------------------------------------------------------
@mcp.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def status() -> dict:
    """Live state: train (absent, on_track, win, lose) and position, cost, remaining,
    score, beam and joint counts, and peak_load: the worst beam force this run as a
    fraction of that beam's limit (1.0 or more = a beam broke).
    Facts that never change are in the bridge://level resource."""
    full = _submit("status")
    return {k: full[k] for k in LIVE_FIELDS if k in full}


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
@mcp.tool(annotations=ToolAnnotations(destructive_hint=False, open_world_hint=False))
def place_girder(
    x1: Metres,
    y1: Metres,
    x2: Metres,
    y2: Metres,
    material: Annotated[
        Material,
        Field(
            description=f"steel ({_steel.cost}), wood ({_wood.cost}, weaker, sustainable), "
            f"titanium ({_titanium.cost}, strong)"
        ),
    ] = "steel",
) -> dict:
    """Place a beam between two neighbouring 2 m grid nodes (ortho or diagonal).

    One end must already exist: a red anchor or a joint you built. Joints are
    added automatically at both ends. Rejected if it would exceed the budget.
    """
    return _submit(
        "place_girder", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "material": material}
    )


class Beam(BaseModel):
    """One beam between two neighbouring grid nodes, as for place_girder."""

    x1: Metres
    y1: Metres
    x2: Metres
    y2: Metres
    material: Material = "steel"


@mcp.tool(annotations=ToolAnnotations(destructive_hint=False, open_world_hint=False))
def place_girders(
    beams: Annotated[
        list[Beam],
        Field(
            description="Beams in build order. Each must touch an existing node: an anchor, "
            "a joint already built, or the end of an earlier beam in this list."
        ),
    ],
) -> dict:
    """Place many beams in one call, in order: a whole bridge at once.

    Stops at the first beam that fails and reports its index and the reason; the
    beams before it stay built. Cheaper than one place_girder call per beam.
    """
    return _submit("place_girders", {"beams": [b.model_dump() for b in beams]})


@mcp.tool(annotations=ToolAnnotations(destructive_hint=True, open_world_hint=False))
def destroy_at(
    x: Metres,
    y: Metres,
    snap: Annotated[
        bool, Field(description="Snap to the nearest grid node; false hits the exact point")
    ] = True,
) -> dict:
    """Remove the beam at (x, y) and refund its cost.

    With snap=false, aim at a point on the beam itself, e.g. its midpoint.
    """
    return _submit("destroy_at", {"x": x, "y": y, "snap": snap})


@mcp.tool(annotations=ToolAnnotations(destructive_hint=False, open_world_hint=False))
def add_joint(x: Metres, y: Metres) -> dict:
    """Check for a pin at a grid node. Never needed: beams that end on the same
    node are always pinned there. Errors when no joint is at (x, y)."""
    return _submit("add_joint", {"x": x, "y": y})


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
@mcp.tool(annotations=ToolAnnotations(destructive_hint=False, open_world_hint=False))
def start_train() -> dict:
    """Run the test: spawn the train on the left bank and start physics.

    After a win or lose it first rebuilds the bridge from the design (undoing damage),
    so you can edit and test again as often as you like. Poll status for the outcome.
    """
    return _submit("start_train")


@mcp.tool(annotations=ToolAnnotations(idempotent_hint=True, open_world_hint=False))
def pause() -> dict:
    """Pause physics. start_train resumes."""
    return _submit("pause")


@mcp.tool(
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True, open_world_hint=False)
)
def reset() -> dict:
    """Delete the whole bridge and the train, set cost back to 0, and pause."""
    return _submit("reset")
