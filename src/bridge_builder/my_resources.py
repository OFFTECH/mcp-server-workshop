"""Stage 2: YOUR resources. This is the file you edit in stage 2.

Resources inform. ``@mcp.resource(uri)`` publishes read-only content the model
(or the user) can pull into context, the way a GET endpoint returns a page. A URI
with ``{placeholders}`` is a template: one function serves a whole family of URIs,
and each placeholder arrives as a function argument.

The knowledge is ready: four tested bridge designs in ``knowledge/designs/`` (a
card and the exact beams for each). The functions below are written too: each one
reads or renders a piece of it. But they are plain Python: nothing is published, so
the model cannot read them. Your job is to publish each one by adding
``@mcp.resource(uri, mime_type=...)`` above its ``def``; the comment above each
function gives the URI and the mime type. The docstring becomes the resource
description.

    Check your resources   uv run workshop check --stage 2
    Stuck?                 uv run python -m bridge_builder --stage 2 --solution
                           (the answers are in solution/mcp_resources.py)
    Broke this file?       uv run workshop restore --stage 2   (keeps a copy of yours)
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
def design_catalog() -> str:
    """Catalog of tested reference bridges, cheapest first, with materials, cost and peak beam load."""
    return render_catalog(load_designs())


# ---------------------------------------------------------------------------
# Your turn: publish these three
# ---------------------------------------------------------------------------
# 1. A template: URI "bridge://designs/{name}", mime_type="text/markdown"
#    The {name} in the URI arrives as the argument.
def design_card(name: str) -> str:
    """Design card: how the bridge carries load, key geometry, when to choose it, benchmark."""
    return render_card(_design_or_not_found(name))


# 2. A template: URI "bridge://designs/{name}/beams", mime_type="application/json"
def design_beams(name: str) -> str:
    """Exact beams of a design in build order, keyed like the place_girder arguments."""
    return render_beams(_design_or_not_found(name))


# 3. URI "bridge://level", mime_type="application/json"
def level() -> str:
    """Level facts that never change: budget, grid rules, anchors, gap, win and lose
    conditions, how beams break, and the materials table."""
    facts = _submit("level")
    if not facts.pop("ok"):
        raise ResourceError(facts["error"])
    return json.dumps(facts, indent=1)
