"""Client briefs: what a client wants from their bridge, stored in ``knowledge/clients/``.

Each brief is one Markdown file, ``<client>.md``:

* first line ``# Title``: the client's name as shown to the model (the file
  name stands in when the heading is missing),
* first paragraph: a one-line summary for the index,
* the rest: requirements in priority order, how to decide, what to report.

This module only reads and renders them; ``mcp_clients`` publishes them as
resources and a prompt. Files are re-read on every call, so a new or edited
brief shows up without restarting the game.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CLIENTS_DIR = Path(__file__).parent / "knowledge" / "clients"


@dataclass(frozen=True)
class Brief:
    name: str
    title: str
    summary: str
    text: str


def load_briefs(folder: Path = CLIENTS_DIR) -> dict[str, Brief]:
    """Every brief in ``folder``, by client name.

    Never fails on a rough brief: attendees write these live, and one file
    without a heading must not hide everybody else's.
    """
    return {path.stem: _load(path) for path in sorted(folder.glob("*.md"))}


def _load(path: Path) -> Brief:
    text = path.read_text(encoding="utf-8").strip()
    first, _, rest = text.partition("\n")
    if first.startswith("# "):
        title = first[2:].strip()
    else:
        title, rest = path.stem, text
    paragraphs = [p.strip() for p in rest.split("\n\n") if p.strip()]
    summary = paragraphs[0].replace("\n", " ") if paragraphs else ""
    return Brief(name=path.stem, title=title, summary=summary, text=text)


def get_brief(name: str, folder: Path = CLIENTS_DIR) -> Brief:
    briefs = load_briefs(folder)
    if name not in briefs:
        raise ValueError(f"unknown client {name!r}; choose one of {', '.join(briefs)}")
    return briefs[name]


def client_uri(name: str) -> str:
    return f"bridge://clients/{name}"


def render_client_index(briefs: dict[str, Brief]) -> str:
    rows = "\n".join(f"| `{b.name}` | {b.title} | {b.summary} |" for b in briefs.values())
    return (
        "# Client briefs\n\n"
        "What each client requires of their bridge. Read a brief at "
        f"`{client_uri('{client}')}`.\n\n"
        "| client | name | wants |\n"
        "|---|---|---|\n"
        f"{rows}\n"
    )
