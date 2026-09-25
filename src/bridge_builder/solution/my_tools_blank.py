# The untouched exercise: `uv run workshop restore` copies it over ../my_tools.py. Do not edit it.
"""Stage 1: YOUR tools. This is the file you edit today.

The server is ready in ``mcp_server.py``: it has a name and instructions, it talks
to the game, and Claude can connect to it. It has no tools yet, so the model can
read about the level but cannot touch it.

The functions below are written already: each one sends a command to the game and
returns the answer. But they are plain Python: the model cannot see them. Your job
is to turn them into tools by adding ``@mcp.tool()`` above each ``def``. Every tool
you add shows up in Claude Code after you restart the game and run ``/mcp`` (reconnect).

The SDK builds the schema the model sees from the function itself:

* the function name is the tool name,
* the docstring is the tool description: the model's only manual,
* type hints become the input schema: ``Annotated[..., Field(description=...)]``
  documents an argument, ``Literal[...]`` becomes an enum, a default makes it optional,
* ``ToolAnnotations`` in the decorator tell the client how the tool behaves:
  ``@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))``.

    Check your tools     uv run workshop check
    Stuck?               uv run python -m bridge_builder --stage 1 --solution
                         (the answers are in solution/mcp_tools.py)
    Broke this file?     uv run workshop restore   (keeps a copy of yours)
"""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from bridge_builder.mcp_server import _submit, mcp

# A coordinate that carries its description into every schema that uses it.
Metres = Annotated[float, Field(description="Coordinate in metres, y-up. Grid nodes are every 2 m.")]

# What status returns: only what changes during play, so the model's frequent calls stay small.
LIVE_FIELDS = (
    "ok", "error", "paused", "train", "train_x", "train_y",
    "cost", "remaining", "score", "girders", "joints", "peak_load",
)


# ---------------------------------------------------------------------------
# Together: make place_girder a tool
# ---------------------------------------------------------------------------
def place_girder(
    x1: Metres,
    y1: Metres,
    x2: Metres,
    y2: Metres,
    material: Literal["wood", "steel", "titanium"] = "steel",
) -> dict:
    """Place a beam between two neighbouring 2 m grid nodes (ortho or diagonal).

    One end must already exist: a red anchor or a joint you built.
    """
    return _submit("place_girder", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "material": material})


# ---------------------------------------------------------------------------
# Your turn: make these three tools
# ---------------------------------------------------------------------------
def start_train() -> dict:
    """Run the test: spawn the train on the left bank and start physics.

    After a win or lose it first rebuilds the bridge (undoing damage), so you can
    edit and test again. Poll status for the outcome.
    """
    return _submit("start_train")


# Hint: it deletes everything. Which annotation warns the client?
def reset() -> dict:
    """Delete the whole bridge and the train, set cost back to 0, and pause."""
    return _submit("reset")


# Hint: the model calls it all the time, and it changes nothing.
def status() -> dict:
    """Live state: train (absent, on_track, win, lose) and position, cost, remaining,
    score, beam and joint counts, and peak_load: the worst beam force this run as a
    fraction of that beam's limit (1.0 or more = a beam broke)."""
    full = _submit("status")
    return {k: full[k] for k in LIVE_FIELDS if k in full}


# ---------------------------------------------------------------------------
# Stretch
# ---------------------------------------------------------------------------
class Beam(BaseModel):
    """One beam between two neighbouring grid nodes, as for place_girder."""

    x1: Metres
    y1: Metres
    x2: Metres
    y2: Metres
    material: Literal["wood", "steel", "titanium"] = "steel"


def place_girders(
    beams: Annotated[
        list[Beam],
        Field(description="Beams in build order. Each must touch an existing node: an anchor, "
              "a joint already built, or the end of an earlier beam in this list."),
    ],
) -> dict:
    """Place many beams in one call, in order: a whole bridge at once.

    Stops at the first beam that fails and reports its index and the reason; the
    beams before it stay built.
    """
    return _submit("place_girders", {"beams": [b.model_dump() for b in beams]})


def destroy_at(
    x: Metres,
    y: Metres,
    snap: Annotated[bool, Field(description="Snap to the nearest grid node; false hits the exact point")] = True,
) -> dict:
    """Remove the beam at (x, y) and refund its cost.

    With snap=false, aim at a point on the beam itself, e.g. its midpoint.
    """
    return _submit("destroy_at", {"x": x, "y": y, "snap": snap})


def pause() -> dict:
    """Pause physics. start_train resumes."""
    return _submit("pause")
