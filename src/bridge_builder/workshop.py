"""Workshop helpers for the exercises: tools in ``my_tools.py`` (stage 1), resources
in ``my_resources.py`` (stage 2) and prompts in ``my_prompts.py`` (stage 3).

``uv run workshop check [--stage 2|3]`` loads your file into the server, starts a game
with no window, and uses every tool, resource or prompt the way the client would,
through MCP. It prints one line each: done, broken (and why) or not written yet, plus tips
for the ones that work but could tell the model more.

``uv run workshop restore [--stage 2|3]`` puts back the untouched exercise file. Your
version is kept next to it as ``<name>.<time>.bak``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

os.environ["SDL_VIDEODRIVER"] = "dummy"  # the check never opens a window
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from bridge_builder.api import GameAPI  # noqa: E402
from bridge_builder.game import Game  # noqa: E402
from bridge_builder.materials import MATERIAL_ORDER  # noqa: E402
from bridge_builder.mcp_server import PARTS, _submit, bind_api, load_stage, mcp  # noqa: E402

PACKAGE = Path(__file__).resolve().parent
DECK = [{"x1": -6, "y1": 3, "x2": -4, "y2": 3}, {"x1": -4, "y1": 3, "x2": -2, "y2": 3}]


class Broken(Exception):
    """The tool exists but does not do its job; the message says what went wrong."""


@dataclass
class Check:
    name: str  # the tool name, or the resource URI
    job: str  # what it does when it works, for the done line
    run: Callable[[Any], list[str]]  # raises Broken; returns tips
    stretch: bool = False
    alias: str = ""  # the name it gets when the decorator leaves out name=


# ---------------------------------------------------------------------------
# Calling tools the way the model does
# ---------------------------------------------------------------------------
def call(name: str, **arguments: Any) -> dict:
    """Call a tool through MCP and return the dict it sent back."""
    try:
        result = asyncio.run(mcp.call_tool(name, arguments))
    except Exception as exc:
        raise Broken(first_line(exc)) from exc
    if result.is_error:
        raise Broken(first_line(result.content[0].text))
    try:
        out = json.loads(result.content[0].text)
    except (IndexError, AttributeError, ValueError):
        raise Broken("return the game's result dict: return _submit(...)") from None
    if not isinstance(out, dict):
        raise Broken("return the game's result dict: return _submit(...)")
    return out


def first_line(exc: Any) -> str:
    text = str(exc).strip().splitlines()
    return text[0] if text else type(exc).__name__


def game() -> dict:
    return _submit("status")


def fresh() -> None:
    """Start each check from an empty level, without relying on your reset tool."""
    _submit("reset")


def expect_ok(out: dict, what: str) -> None:
    if out.get("ok") is not True:
        raise Broken(f"{what}: {out.get('error', out)}")


def props(tool) -> dict:
    return tool.input_schema.get("properties", {})


def described(tool, *args: str) -> list[str]:
    missing = [a for a in args if not props(tool).get(a, {}).get("description")]
    if missing:
        return [f"describe {', '.join(missing)} with Annotated[float, Field(description=...)]"]
    return []


def hint(tool, name: str, want: bool) -> list[str]:
    got = getattr(tool.annotations, name, None) if tool.annotations else None
    return [] if got is want else [f"set ToolAnnotations({name}={want}) so the client knows"]


def docstring(tool) -> list[str]:
    return [] if (tool.description or "").strip() else ["add a docstring: it is the model's only manual"]


# ---------------------------------------------------------------------------
# One check per tool
# ---------------------------------------------------------------------------
def check_place_girder(tool) -> list[str]:
    required = set(tool.input_schema.get("required", []))
    if not {"x1", "y1", "x2", "y2"} <= required:
        raise Broken("it needs the arguments x1, y1, x2, y2 (no defaults)")
    fresh()
    expect_ok(call("place_girder", **DECK[0]), "a beam from the left anchor was refused")
    if game()["girders"] != 1:
        raise Broken("said ok but no beam appeared: does it pass all four coordinates?")
    tips = docstring(tool) + described(tool, "x1", "y1", "x2", "y2")
    material = props(tool).get("material")
    if material is None:
        return tips + ['add material: Literal["wood", "steel", "titanium"] = "steel"']
    if "material" in required:
        tips.append('give material a default: = "steel"')
    fresh()
    out = call("place_girder", **DECK[0], material="titanium")
    expect_ok(out, "a titanium beam was refused")
    if out.get("material") != "titanium":
        raise Broken(f"asked for titanium, got {out.get('material')}: pass material to the game")
    if sorted(material.get("enum", [])) != sorted(MATERIAL_ORDER):
        tips.append("type material as Literal[...] so the model sees the three choices")
    return tips


def check_start_train(tool) -> list[str]:
    fresh()
    out = call("start_train")
    expect_ok(out, "the game refused to start the train")
    if game()["paused"]:
        raise Broken("the game is still paused: send the op start_train")
    return docstring(tool)


def check_reset(tool) -> list[str]:
    fresh()
    _submit("place_girder", DECK[0])
    expect_ok(call("reset"), "reset failed")
    if game()["girders"]:
        raise Broken("the beam is still there after reset: send the op reset")
    return docstring(tool) + hint(tool, "destructive_hint", True)


def check_status(tool) -> list[str]:
    fresh()
    _submit("place_girder", DECK[0])
    out = call("status")
    expect_ok(out, "status failed")
    if out.get("girders") != 1:
        raise Broken("it should report the live state, e.g. girders: 1 after one beam")
    return docstring(tool) + hint(tool, "read_only_hint", True)


def check_place_girders(tool) -> list[str]:
    beams = props(tool).get("beams")
    if not beams or beams.get("type") != "array":
        raise Broken("it takes one argument, beams: a list of beams")
    fresh()
    out = call("place_girders", beams=DECK)
    expect_ok(out, "two beams in a row were refused")
    if game()["girders"] != 2:
        raise Broken(f"asked for 2 beams, the game has {game()['girders']}")
    return docstring(tool)


def check_destroy_at(tool) -> list[str]:
    fresh()
    _submit("place_girder", DECK[0])
    args = {"x": -5, "y": 3} | ({"snap": False} if "snap" in props(tool) else {})
    expect_ok(call("destroy_at", **args), "could not remove the beam at x=-5, y=3")
    if game()["girders"]:
        raise Broken("the beam is still there: pass x, y (and snap) to the game")
    tips = docstring(tool) + hint(tool, "destructive_hint", True)
    return tips + ([] if "snap" in props(tool) else ["add snap: bool = True"])


def check_pause(tool) -> list[str]:
    fresh()
    _submit("start_train")
    expect_ok(call("pause"), "pause failed")
    if not game()["paused"]:
        raise Broken("the game is still running: send the op pause")
    return docstring(tool)


CHECKS = [
    Check("place_girder", "builds a beam", check_place_girder),
    Check("start_train", "sends the train", check_start_train),
    Check("reset", "clears the level", check_reset),
    Check("status", "reports the live state", check_status),
    Check("place_girders", "builds many beams in one call", check_place_girders, stretch=True),
    Check("destroy_at", "removes a beam", check_destroy_at, stretch=True),
    Check("pause", "pauses the game", check_pause, stretch=True),
]


# ---------------------------------------------------------------------------
# Stage 2: reading resources the way the client does
# ---------------------------------------------------------------------------
def read(uri: str) -> str:
    """Read a resource through MCP and return its text."""
    try:
        (content,) = asyncio.run(mcp.read_resource(uri))
    except Exception as exc:
        raise Broken(first_line(exc)) from exc
    return content.content


def mime(res, want: str) -> list[str]:
    return [] if res.mime_type == want else [f'set mime_type="{want}" so the client knows what it gets']


def summary(res) -> list[str]:
    return [] if (res.description or "").strip() else ["add a docstring: it becomes the resource description"]


def check_catalog(res) -> list[str]:
    if "cable_stayed" not in read("bridge://designs"):
        raise Broken("it should list the designs: return render_catalog(load_designs())")
    return mime(res, "text/markdown") + summary(res)


def check_card(res) -> list[str]:
    if not read("bridge://designs/timber_arch").startswith("# Timber arch"):
        raise Broken("bridge://designs/timber_arch should be that card: render_card(...)")
    tips = mime(res, "text/markdown") + summary(res)
    try:
        read("bridge://designs/suspension")
    except Broken as exc:
        if "cable_stayed" in str(exc):
            return tips
    return tips + ["use _design_or_not_found(name): an unknown name then lists the real ones"]


def check_beams(res) -> list[str]:
    try:
        beams = json.loads(read("bridge://designs/timber_arch/beams"))
    except ValueError:
        raise Broken("return the JSON text: render_beams(...)") from None
    if beams.get("name") != "timber_arch" or len(beams.get("beams", [])) != 28:
        raise Broken("bridge://designs/timber_arch/beams should hold that design's 28 beams")
    return mime(res, "application/json") + summary(res)


def check_level(res) -> list[str]:
    try:
        facts = json.loads(read("bridge://level"))
    except ValueError:
        raise Broken("return JSON text: json.dumps(facts, indent=1)") from None
    if facts.get("budget") != 30000:
        raise Broken('it should return the game\'s answer to _submit("level")')
    tips = ['pop the "ok" flag: it is not a level fact'] if "ok" in facts else []
    return tips + mime(res, "application/json") + summary(res)


RESOURCE_CHECKS = [
    Check("bridge://designs", "the catalog, cheapest first", check_catalog),
    Check("bridge://designs/{name}", "one design card", check_card),
    Check("bridge://designs/{name}/beams", "one design's beams", check_beams),
    Check("bridge://level", "the level facts", check_level),
]


# ---------------------------------------------------------------------------
# Stage 3: getting prompts the way the client does
# ---------------------------------------------------------------------------
def get(name: str, arguments: dict | None = None) -> list:
    """Get a prompt through MCP and return its messages."""
    try:
        return asyncio.run(mcp.get_prompt(name, arguments or {})).messages
    except Exception as exc:
        raise Broken(first_line(exc)) from exc


def embedded(message) -> str | None:
    resource = getattr(message.content, "resource", None)
    return str(resource.uri) if resource is not None else None


def prompt_tips(prompt, title: str) -> list[str]:
    tips = [] if prompt.title else [f'add title="{title}": it is what the / menu shows']
    return tips + ([] if (prompt.description or "").strip() else ["keep the docstring: it becomes the description"])


def check_design_prompt(prompt) -> list[str]:
    if "design" not in {a.name for a in prompt.arguments or []}:
        raise Broken("it should take the argument design")
    messages = get("design", {"design": "timber_arch"})
    if not messages or embedded(messages[0]) != "bridge://designs/timber_arch":
        raise Broken("design=timber_arch should embed bridge://designs/timber_arch first")
    if embedded(get("design")[0]) != "bridge://designs":
        raise Broken("with no design it should embed the catalog, bridge://designs")
    return prompt_tips(prompt, "Build a reference design")


def check_brief_prompt(prompt) -> list[str]:
    if "client" not in {a.name for a in prompt.arguments or []}:
        raise Broken("it should take the argument client")
    messages = get("brief", {"client": "fetnis"})
    if not messages or embedded(messages[0]) != "bridge://clients/fetnis":
        raise Broken("client=fetnis should embed bridge://clients/fetnis first")
    return prompt_tips(prompt, "Build to a client's brief")


PROMPT_CHECKS = [
    Check("design", "builds one reference design", check_design_prompt, alias="design_prompt"),
    Check("brief", "builds to a client's brief", check_brief_prompt, alias="build_to_brief"),
]


def listed_prompts() -> dict:
    return {pr.name: pr for pr in asyncio.run(mcp.list_prompts())}


def listed_tools() -> dict:
    return {t.name: t for t in asyncio.run(mcp.list_tools())}


def listed_resources() -> dict:
    fixed = {str(r.uri): r for r in asyncio.run(mcp.list_resources())}
    templates = {t.uri_template: t for t in asyncio.run(mcp.list_resource_templates())}
    return fixed | templates


@dataclass
class Exercise:
    part: str  # the load_stage argument
    noun: str
    file: str  # the file you edit, in the package folder
    solution: str
    missing: str  # what to do when it is not there yet
    checks: list[Check]
    listed: Callable[[], dict]


EXERCISES = {
    1: Exercise("tools", "tool", "my_tools.py", "solution/mcp_tools.py",
                "not a tool yet: add @mcp.tool()", CHECKS, listed_tools),
    2: Exercise("resources", "resource", "my_resources.py", "solution/mcp_resources.py",
                "not a resource yet: add @mcp.resource(...)", RESOURCE_CHECKS, listed_resources),
    3: Exercise("prompts", "prompt", "my_prompts.py", "solution/mcp_prompts.py",
                "not a prompt yet: add @mcp.prompt(...)", PROMPT_CHECKS, listed_prompts),
}


def source_file(stage: int, choice: str) -> str:
    ex = EXERCISES[stage]
    blank = "solution/" + ex.file.replace(".py", "_blank.py")
    return {"mine": ex.file, "solution": ex.solution, "blank": blank}[choice]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def check(choice: str = "mine", stage: int = 1) -> int:
    ex = EXERCISES[stage]
    source = source_file(stage, choice)
    print(f"Checking the {ex.noun}s in {source}\n")
    try:
        # Earlier stages come from the reference answers, so only your file is checked.
        parts = {part: "solution" for part, (first, _) in PARTS.items() if first < stage}
        load_stage(stage, **parts, **{ex.part: choice})
    except Exception as exc:
        name = Path(source).name
        lines = [f.lineno for f in traceback.extract_tb(exc.__traceback__) if f.filename.endswith(name)]
        if isinstance(exc, SyntaxError) and exc.lineno:
            lines.append(exc.lineno)
        where = f" (line {lines[-1]})" if lines else ""
        print(f"  x  {source} does not load{where}: {type(exc).__name__}: {first_line(exc)}")
        return 1

    api = GameAPI(Game())
    bind_api(api)
    stop = threading.Event()

    def owner() -> None:  # the game loop's job in the real app: run queued commands
        while not stop.is_set():
            api.drain()
            time.sleep(0.005)

    threading.Thread(target=owner, daemon=True).start()
    width = max(len(c.name) for c in ex.checks) + 1
    pad = width + (11 if any(c.stretch for c in ex.checks) else 0)
    try:
        listed = ex.listed()
        done = {False: 0, True: 0}
        broken, tips, todo = 0, [], []
        for c in ex.checks:
            label = f"{c.name:<{width}}" + ("  (stretch)" if c.stretch else "")
            item = listed.get(c.name)
            if item is None and c.alias in listed:
                broken += 1
                print(f'  x  {label:<{pad}} published as {c.alias!r}: add name="{c.name}" to the decorator')
                continue
            if item is None:
                print(f"  .  {label:<{pad}} {ex.missing}")
                todo.append(c.name)
                continue
            try:
                for tip in c.run(item):
                    tips.append(f"{c.name}: {tip}")
            except Broken as exc:
                broken += 1
                print(f"  x  {label:<{pad}} {exc}")
                continue
            done[c.stretch] += 1
            print(f"  ok {label:<{pad}} {c.job}")
        if stage == 1:  # stage 2 also lists what mcp_designs publishes; only tools are all yours
            for name in sorted(set(listed) - {c.name for c in ex.checks}):
                print(f"  +  {name:<{pad}} extra {ex.noun}, not checked")
    finally:
        stop.set()

    if tips:
        print("\nTips")
        for tip in tips:
            print(f"  -  {tip}")
    core = sum(not c.stretch for c in ex.checks)
    stretch = len(ex.checks) - core
    tail = f", {done[True]} of {stretch} stretch." if stretch else "."
    print(f"\n{done[False]} of {core} {ex.noun}s done{tail}", end=" ")
    if broken:
        print("Restart the game and /mcp after a fix.")
    elif done[False] == core:
        print("Restart the game, /mcp in Claude Code, and ask for a bridge.")
    else:
        print(f"Next: {todo[0]}.")
    return 1 if broken else 0


def restore(folder: Path = PACKAGE, stage: int = 1) -> Path | None:
    """Put back the untouched exercise file; keep the current one as <name>.<time>.bak."""
    name = EXERCISES[stage].file
    target, blank = folder / name, folder / source_file(stage, "blank")
    fresh_text = blank.read_text(encoding="utf-8").split("\n", 1)[1]  # drop the "untouched" note
    backup = None
    if target.exists() and target.read_text(encoding="utf-8") != fresh_text:
        backup = folder / f"{Path(name).stem}.{datetime.now():%Y%m%d-%H%M%S}.bak"
        shutil.copyfile(target, backup)
    target.write_text(fresh_text, encoding="utf-8", newline="\n")
    return backup


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="workshop", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    stage = argparse.ArgumentParser(add_help=False)
    stage.add_argument("--stage", type=int, choices=sorted(EXERCISES), default=1,
                       help="1: tools in my_tools.py (default), 2: resources in my_resources.py, 3: prompts in my_prompts.py")
    c = sub.add_parser("check", parents=[stage], help="use your tools, resources or prompts the way the client does")
    c.add_argument("--solution", dest="choice", action="store_const", const="solution", default="mine",
                   help="check the reference answers instead")
    c.add_argument("--blank", dest="choice", action="store_const", const="blank", help=argparse.SUPPRESS)
    sub.add_parser("restore", parents=[stage], help="put back the untouched exercise file (yours is kept as .bak)")
    args = parser.parse_args(argv)
    if args.command == "check":
        sys.exit(check(args.choice, args.stage))
    backup = restore(stage=args.stage)
    name = EXERCISES[args.stage].file
    print(f"{name} is back to the start." + (f" Yours is in {backup.name}." if backup else ""))


if __name__ == "__main__":
    main()
