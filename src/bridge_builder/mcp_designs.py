"""Workshop stage 2: resources and a prompt. Importing this module switches them on.

Resources inform. ``@mcp.resource(uri)`` publishes read-only content the model
(or the user) can pull into context. A URI with ``{placeholders}`` is a
template: one function serves a whole family of URIs. Here: the level's fixed
facts, and the tested reference designs from ``knowledge/designs/``.

Prompts guide. ``@mcp.prompt()`` publishes a reusable workflow with arguments;
in Claude Code it becomes the slash command ``/bridge-engineer:<name>``. The
``design`` prompt hands the model a design and the steps to build and test it.

A later stage can add tools too: ``build_design`` knows the catalog, so it
lives here rather than in stage 1, and builds a whole reference design in one call.
"""

from __future__ import annotations

import json
from typing import Annotated

from mcp.server.mcpserver import UserMessage
from mcp.server.mcpserver.exceptions import ResourceError, ResourceNotFoundError
from mcp.types import EmbeddedResource, TextResourceContents, ToolAnnotations
from pydantic import Field

from bridge_builder.designs import (
    Design,
    beams_uri,
    card_uri,
    get_design,
    load_designs,
    render_beams,
    render_card,
    render_catalog,
)
from bridge_builder.mcp_tools import _submit, add_instructions, mcp

add_instructions(
    "Level facts (anchors, gap, materials, win and lose conditions): bridge://level. "
    "Tested reference designs are published as resources, cheapest first: start at "
    "bridge://designs. When asked to build a bridge, first offer the user a choice: one of "
    "the reference designs (name, cost, peak load) or a custom design of your own. "
    "build_design builds a reference design in one call."
)


# ---------------------------------------------------------------------------
# Resources: level facts
# ---------------------------------------------------------------------------
@mcp.resource("bridge://level", mime_type="application/json")
def level() -> str:
    """Level facts that never change: budget, grid rules, anchors, gap, win and lose
    conditions, how beams break, and the materials table."""
    facts = _submit("level")
    if not facts.pop("ok"):
        raise ResourceError(facts["error"])
    return json.dumps(facts, indent=1)


# ---------------------------------------------------------------------------
# Resources: the design knowledge base (src/bridge_builder/knowledge/designs/)
# ---------------------------------------------------------------------------
# The SDK only forwards the message of errors it expects; anything else reaches the
# client as a generic "Error reading resource". ResourceNotFoundError is MCP's
# "no such resource", so the model learns which design names exist.
def _design_or_not_found(name: str) -> Design:
    try:
        return get_design(name)
    except ValueError as exc:
        raise ResourceNotFoundError(str(exc)) from exc


@mcp.resource("bridge://designs", mime_type="text/markdown")
def design_catalog() -> str:
    """Catalog of tested reference bridges, cheapest first, with materials, cost and peak beam load."""
    return render_catalog(load_designs())


@mcp.resource("bridge://designs/{name}", mime_type="text/markdown")
def design_card(name: str) -> str:
    """Design card: how the bridge carries load, key geometry, when to choose it, benchmark."""
    return render_card(_design_or_not_found(name))


@mcp.resource("bridge://designs/{name}/beams", mime_type="application/json")
def design_beams(name: str) -> str:
    """Exact beams of a design in build order, keyed like the place_girder arguments."""
    return render_beams(_design_or_not_found(name))


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


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


def embed(uri: str, text: str, mime_type: str) -> UserMessage:
    """A message that carries a resource, exactly as the client would read it."""
    return UserMessage(
        EmbeddedResource(
            type="resource",
            resource=TextResourceContents(uri=uri, text=text, mime_type=mime_type),
        )
    )


def build_steps() -> str:
    """How to build and test a design; shared by the design and brief prompts."""
    return (
        "call build_design with the design's name (for a custom design: reset, then place_girders "
        "with all its beams in build order), check the cost, call start_train, and poll status "
        "until train is win or lose"
    )


def _choose_design(requested: str) -> list[UserMessage]:
    """No or unknown design: hand the model the catalog and let it ask the user.

    Returned as a normal prompt rather than an error, because clients may hide
    error details (Claude Code shows only "failed").
    """
    designs = load_designs()
    unknown = f"{requested!r} is not one of the reference designs. " if requested else ""
    return [
        embed("bridge://designs", render_catalog(designs), "text/markdown"),
        UserMessage(
            f"{unknown}Show the user the reference designs from the catalog above "
            "(name, what it is, cost, peak beam load) and ask which one to build, "
            "or a custom design instead. "
            f"For the chosen design: {build_steps()}; then "
            "report result, cost, and peak_load against the benchmark.\n\n"
            f"Tip for the user: /bridge-engineer:design <name> skips this question "
            f"(<name> is one of {', '.join(designs)})."
        ),
    ]


@mcp.prompt(name="design", title="Build a reference design")
def design_prompt(
    design: Annotated[str, Field(description=DESIGN_CHOICES + ". Leave empty to list them.")] = "",
) -> list[UserMessage]:
    """Build one of the reference designs in the live window, test it, and compare with its
    benchmark. Without a design, lists the designs to choose from."""
    requested = design.strip().lower().replace("-", "_").replace(" ", "_")
    try:
        d = get_design(requested)
    except ValueError:
        return _choose_design(requested)
    b = d.benchmark
    return [
        embed(card_uri(d.name), render_card(d), "text/markdown"),
        embed(beams_uri(d.name), render_beams(d), "application/json"),
        UserMessage(
            f"Build the {d.title} from the design above in the live Bridge Builder window.\n\n"
            f'1. Call build_design with name "{d.name}": it clears the level and places all '
            f"{len(d.beams)} beams listed above in one call. If it fails, stop and report which "
            "beam and why.\n"
            f"2. Check that the cost is {b['cost']}.\n"
            "3. Call start_train, then poll status until train is win or lose.\n"
            "4. Report result, cost, and peak_load from status against the benchmark: "
            f"{b['result']}, cost {b['cost']}, peak_load {b['peak_load']:.2f}."
        ),
    ]
