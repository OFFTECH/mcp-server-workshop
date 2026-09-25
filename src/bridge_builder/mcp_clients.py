"""Workshop stage 3: the client briefs. Importing this module switches them on.

A prompt can carry knowledge the server's tools and designs do not have: here, what
a client wants. Each brief in ``knowledge/clients/<client>.md`` is published as a
resource; the ``brief`` prompt in ``my_prompts.py`` (the stage 3 exercise) puts a
brief and the design catalog in front of the model.

Add a brief by writing a new ``.md`` file in that folder; no restart needed.
"""

from __future__ import annotations

from mcp.server.mcpserver.exceptions import ResourceNotFoundError

from bridge_builder.clients import get_brief, load_briefs, render_client_index
from bridge_builder.mcp_server import add_instructions, mcp

add_instructions(
    "Clients publish their requirements as briefs: bridge://clients. When the user builds "
    "for a client, read that client's brief first and let it decide the design; the "
    "/bridge-engineer:brief prompt does this."
)


# ---------------------------------------------------------------------------
# Resources: client briefs (src/bridge_builder/knowledge/clients/)
# ---------------------------------------------------------------------------
@mcp.resource("bridge://clients", mime_type="text/markdown")
def client_index() -> str:
    """Every client with a brief, and in one line what they want."""
    return render_client_index(load_briefs())


@mcp.resource("bridge://clients/{client}", mime_type="text/markdown")
def client_brief(client: str) -> str:
    """A client's brief: requirements in priority order, how to decide, what to report."""
    try:
        return get_brief(client).text
    except ValueError as exc:
        raise ResourceNotFoundError(str(exc)) from exc
