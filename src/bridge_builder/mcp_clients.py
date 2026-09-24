"""Workshop stage 3: client briefs. Importing this module switches them on.

A prompt can carry knowledge the server's tools and designs do not have: here, what
a client wants. Each brief in ``knowledge/clients/<client>.md`` is published as a
resource, and the ``brief`` prompt puts the brief and the design catalog in front
of the model with one job: pick the design the client's requirements rank highest,
build it, check it, and explain the trade-off (it may well not be the cheapest).

Add a brief by writing a new ``.md`` file in that folder; no restart needed.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import UserMessage
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from pydantic import Field

from bridge_builder.clients import client_uri, get_brief, load_briefs, render_client_index
from bridge_builder.designs import load_designs, render_catalog
from bridge_builder.mcp_designs import build_steps, embed
from bridge_builder.mcp_tools import add_instructions, mcp

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


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
def _choose_client(requested: str) -> list[UserMessage]:
    """No or unknown client: hand the model the index and let it ask the user."""
    briefs = load_briefs()
    unknown = f"{requested!r} has no brief. " if requested else ""
    return [
        embed("bridge://clients", render_client_index(briefs), "text/markdown"),
        UserMessage(
            f"{unknown}Show the user the client briefs above and ask which client the bridge "
            "is for. Then read that client's brief at bridge://clients/<client> and follow it.\n\n"
            "Tip for the user: /bridge-engineer:brief <client> skips this question "
            f"(<client> is one of {', '.join(briefs)})."
        ),
    ]


@mcp.prompt(name="brief", title="Build to a client's brief")
def build_to_brief(
    client: Annotated[
        str, Field(description="Client name from bridge://clients, e.g. fetnis. Leave empty to list them.")
    ] = "",
) -> list[UserMessage]:
    """Choose, build and verify the bridge a client's brief asks for, and explain the
    trade-off against the cheapest design. Without a client, lists the briefs."""
    requested = client.strip().lower().replace("-", "_").replace(" ", "_")
    try:
        brief = get_brief(requested)
    except ValueError:
        return _choose_client(requested)
    return [
        embed(client_uri(brief.name), brief.text, "text/markdown"),
        embed("bridge://designs", render_catalog(load_designs()), "text/markdown"),
        UserMessage(
            f"Design and build the bridge for {brief.title}, following their brief above.\n\n"
            "1. Screen every reference design in the catalog against the brief, in the "
            "brief's priority order. Take the facts from each design's beams "
            "(bridge://designs/<name>/beams) and benchmark, and show them as a short table.\n"
            "2. Choose the design the brief ranks highest and say in one sentence why.\n"
            f"3. Build it: {build_steps()}.\n"
            "4. Verify the brief on the bridge you built: check its beams and the peak_load "
            "from status against every requirement.\n"
            "5. Report as the brief asks. Compare with the cheapest design in the catalog: if "
            "you did not choose it, say which requirement ruled it out and how much more "
            "the chosen bridge costs."
        ),
    ]
