"""Stage 3: YOUR prompts. This is the file you edit in stage 3.

Prompts guide. ``@mcp.prompt(name=..., title=...)`` publishes a reusable workflow
with arguments; in Claude Code it becomes the slash command ``/bridge-engineer:<name>``.
The user starts it, and it returns messages for the model. A message can embed a
resource, so the facts travel with the task.

Both prompts below are written: ``design`` builds one reference design, ``brief``
builds what a client's brief asks for. But they are plain Python: nothing is
published, so no slash command appears. Your job is to publish each one by adding
``@mcp.prompt(...)`` above its ``def``; the comment above each function gives the
name and title. Function arguments become the prompt's arguments, the docstring its
description.

    Check your prompts   uv run workshop check --stage 3
    Stuck?               uv run python -m bridge_builder --stage 3 --solution
                         (the answers are in solution/mcp_prompts.py)
    Broke this file?     uv run workshop restore --stage 3   (keeps a copy of yours)
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import UserMessage
from mcp.types import EmbeddedResource, TextResourceContents
from pydantic import Field

from bridge_builder.clients import client_uri, get_brief, load_briefs, render_client_index
from bridge_builder.designs import (
    beams_uri,
    card_uri,
    get_design,
    load_designs,
    render_beams,
    render_card,
    render_catalog,
)
from bridge_builder.mcp_designs import DESIGN_CHOICES
from bridge_builder.mcp_server import mcp


# ---------------------------------------------------------------------------
# Helpers, shared by both prompts
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


# ---------------------------------------------------------------------------
# Together: the design prompt
# ---------------------------------------------------------------------------
# name="design", title="Build a reference design"
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


# ---------------------------------------------------------------------------
# Your turn: the brief prompt
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


# name="brief", title="Build to a client's brief"
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
