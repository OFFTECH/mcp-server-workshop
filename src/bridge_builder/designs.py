"""Reference bridge designs, stored as documents in ``knowledge/designs/``.

Each design is a pair of files named after it:

* ``<name>.md``   the card: how it carries load, key geometry, when to choose it
* ``<name>.json`` title, summary, measured benchmark, and the beams in build order

This module only reads and renders them; ``mcp_tools`` publishes them as
resources. The files are re-read on every call, so an edited card shows up
without restarting the game.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from bridge_builder.materials import MATERIALS

DESIGNS_DIR = Path(__file__).parent / "knowledge" / "designs"

Beam = tuple[float, float, float, float, str]


@dataclass(frozen=True)
class Design:
    name: str
    title: str
    summary: str
    card: str
    benchmark: dict
    beams: list[Beam]


def load_designs(folder: Path = DESIGNS_DIR) -> dict[str, Design]:
    """Every design in ``folder``, by name. Raises ``ValueError`` on a malformed design."""
    designs: dict[str, Design] = {}
    for data_path in sorted(folder.glob("*.json")):
        designs[data_path.stem] = _load(data_path)
    for card_path in folder.glob("*.md"):
        if card_path.stem not in designs:
            raise ValueError(f"{card_path.name} has no matching {card_path.stem}.json")
    return designs


def _load(data_path: Path) -> Design:
    name = data_path.stem
    card_path = data_path.with_suffix(".md")
    if not card_path.exists():
        raise ValueError(f"{data_path.name} has no matching {card_path.name}")
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
        beams = [
            (float(x1), float(y1), float(x2), float(y2), str(material))
            for x1, y1, x2, y2, material in data["beams"]
        ]
        title, summary, benchmark = data["title"], data["summary"], data["benchmark"]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{data_path.name} is malformed: {exc}") from exc
    unknown = sorted({b[4] for b in beams} - set(MATERIALS))
    if unknown:
        raise ValueError(f"{data_path.name} uses unknown materials {unknown}")
    return Design(
        name=name,
        title=title,
        summary=summary,
        card=card_path.read_text(encoding="utf-8").strip(),
        benchmark=benchmark,
        beams=beams,
    )


def get_design(name: str, folder: Path = DESIGNS_DIR) -> Design:
    designs = load_designs(folder)
    if name not in designs:
        raise ValueError(f"unknown design {name!r}; choose one of {', '.join(designs)}")
    return designs[name]


# ---------------------------------------------------------------------------
# Rendering: what the model reads
# ---------------------------------------------------------------------------
def card_uri(name: str) -> str:
    return f"bridge://designs/{name}"


def beams_uri(name: str) -> str:
    return f"bridge://designs/{name}/beams"


def _materials(design: Design) -> str:
    return ", ".join(sorted({b[4] for b in design.beams}))


def render_catalog(designs: dict[str, Design]) -> str:
    """Cheapest first; equal cost goes to the lower peak load (more margin)."""
    ranked = sorted(designs.values(), key=lambda d: (d.benchmark["cost"], d.benchmark["peak_load"]))
    rows = "\n".join(
        f"| `{d.name}` | {d.title} | {d.summary} | {_materials(d)} | {len(d.beams)} "
        f"| {d.benchmark['cost']} | {d.benchmark['result']} | {d.benchmark['peak_load']:.2f} |"
        for d in ranked
    )
    return (
        "# Reference bridge designs\n\n"
        "Tested designs for this level, cheapest first. Each one crossed with the numbers below.\n"
        f"Read a card at `{card_uri('{name}')}` and its beams in build order at "
        f"`{beams_uri('{name}')}`.\n\n"
        "| name | design | summary | materials | beams | cost | result | peak beam load |\n"
        "|---|---|---|---|---|---|---|---|\n"
        f"{rows}\n\n"
        "Peak beam load is the worst beam force during the crossing as a fraction "
        "of that beam's limit, pull or buckling (1.0 = it breaks).\n"
    )


def render_card(design: Design) -> str:
    b = design.benchmark
    return (
        f"# {design.title}\n\n{design.summary}\n\n{design.card}\n\n"
        "## Benchmark\n\n"
        "| beams | materials | cost | result | peak beam load |\n"
        "|---|---|---|---|---|\n"
        f"| {len(design.beams)} | {_materials(design)} | {b['cost']} | {b['result']} "
        f"| {b['peak_load']:.2f} |\n\n"
        f"Exact beams in build order: `{beams_uri(design.name)}`\n"
    )


def _num(v: float) -> float | int:
    return int(v) if float(v).is_integer() else v


def render_beams(design: Design) -> str:
    """JSON with one beam per line, keyed like the place_girder arguments."""
    rows = ",\n".join(
        "  " + json.dumps({"x1": _num(x1), "y1": _num(y1), "x2": _num(x2), "y2": _num(y2), "material": m})
        for x1, y1, x2, y2, m in design.beams
    )
    head = json.dumps({"name": design.name, "title": design.title, "benchmark": design.benchmark})
    return f'{head[:-1]}, "beams": [\n{rows}\n]}}\n'
