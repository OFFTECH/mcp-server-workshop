"""Workshop stage 2: what comes with the resources. Importing this module switches it on.

The resources themselves (level facts and the tested reference designs) are the
stage 2 exercise in ``my_resources.py``; the answers are in ``solution/mcp_resources.py``.
This module adds what uses them: the stage 2 server instructions, which point the
model at the resources and tell it how to use them, and one tool, ``build_design``.

A later stage can add tools too: ``build_design`` knows the catalog, so it
lives here rather than in stage 1, and builds a whole reference design in one call.
"""

from __future__ import annotations

from typing import Annotated

from mcp.types import ToolAnnotations
from pydantic import Field

from bridge_builder.designs import get_design, load_designs
from bridge_builder.mcp_server import DESIGN_ADVICE, _submit, add_instructions, mcp

add_instructions(DESIGN_ADVICE)
add_instructions(
    "Level facts (anchors, gap, materials, win and lose conditions): bridge://level. "
    "Tested reference designs are published as resources, cheapest first: start at "
    "bridge://designs. When asked to build a bridge, first offer the user a choice: one of "
    "the reference designs (name, cost, peak load) or a custom design of your own. "
    "build_design builds a reference design in one call."
)


# ---------------------------------------------------------------------------
# Tool: build a whole reference design at once
# ---------------------------------------------------------------------------
# Computed once at startup; this also fails fast if a knowledge file is malformed.
DESIGN_CHOICES = "One of: " + ", ".join(load_designs())


@mcp.tool(annotations=ToolAnnotations(destructive_hint=True, open_world_hint=False))
def build_design(name: Annotated[str, Field(description=DESIGN_CHOICES)]) -> dict:
    """Clear the level and build a reference design from bridge://designs in one call.

    Returns what was placed, the cost, and the design's benchmark to compare with.
    Test it afterwards with start_train.
    """
    try:
        design = get_design(name.strip().lower().replace("-", "_").replace(" ", "_"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    beams = [
        {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "material": material}
        for x1, y1, x2, y2, material in design.beams
    ]
    out = _submit("place_girders", {"beams": beams, "reset": True})
    return {**out, "design": design.name, "benchmark": design.benchmark}
