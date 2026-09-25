"""Reference solution for stage 2: ``my_resources.py`` with every decorator added.

Apart from this docstring, the only difference from ``my_resources.py`` is the
``@mcp.resource(...)`` line above each function; ``tests/test_workshop.py`` checks that.
The game serves these resources with ``--stage 2 --solution``, and by default for
stage 3, so everyone starts that stage from the same working server.
"""

from __future__ import annotations

import json

from mcp.server.mcpserver.exceptions import ResourceError, ResourceNotFoundError

from bridge_builder.designs import Design, get_design, load_designs, render_beams, render_card, render_catalog
from bridge_builder.mcp_server import _submit, mcp


# An unknown design name becomes MCP's "no such resource" with the valid names in the
# message; any other error would reach the client as a bare "Error reading resource".
def _design_or_not_found(name: str) -> Design:
    try:
        return get_design(name)
    except ValueError as exc:
        raise ResourceNotFoundError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Together: publish the catalog
# ---------------------------------------------------------------------------
# URI "bridge://designs", mime_type="text/markdown"
@mcp.resource("bridge://designs", mime_type="text/markdown")
def design_catalog() -> str:
    """Catalog of tested reference bridges, cheapest first, with materials, cost and peak beam load."""
    return render_catalog(load_designs())


# ---------------------------------------------------------------------------
# Your turn: publish these three
# ---------------------------------------------------------------------------
# 1. A template: URI "bridge://designs/{name}", mime_type="text/markdown"
#    The {name} in the URI arrives as the argument.
@mcp.resource("bridge://designs/{name}", mime_type="text/markdown")
def design_card(name: str) -> str:
    """Design card: how the bridge carries load, key geometry, when to choose it, benchmark."""
    return render_card(_design_or_not_found(name))


# 2. A template: URI "bridge://designs/{name}/beams", mime_type="application/json"
@mcp.resource("bridge://designs/{name}/beams", mime_type="application/json")
def design_beams(name: str) -> str:
    """Exact beams of a design in build order, keyed like the place_girder arguments."""
    return render_beams(_design_or_not_found(name))


# 3. URI "bridge://level", mime_type="application/json"
@mcp.resource("bridge://level", mime_type="application/json")
def level() -> str:
    """Level facts that never change: budget, grid rules, anchors, gap, win and lose
    conditions, how beams break, and the materials table."""
    facts = _submit("level")
    if not facts.pop("ok"):
        raise ResourceError(facts["error"])
    return json.dumps(facts, indent=1)
