import asyncio
import json
import threading
import time

import pytest

from bridge_builder.api import GameAPI
from bridge_builder.game import Game
from bridge_builder.materials import MATERIAL_ORDER
from bridge_builder.mcp_server import bind_api, load_stage, mcp
from bridge_builder.solution.mcp_tools import (
    LIVE_FIELDS,
    place_girder,
    place_girders,
    start_train,
    status,
)
from bridge_builder.mcp_designs import build_design  # noqa: E402

load_stage(3, "solution", "solution", "solution")  # everything, from the reference answers


def _call(fn, *args, **kwargs):
    game = Game()
    api = GameAPI(game)
    bind_api(api)
    box: dict = {}

    def worker():
        box["r"] = fn(*args, **kwargs)

    t = threading.Thread(target=worker)
    t.start()
    deadline = time.time() + 1.0
    while time.time() < deadline:
        api.drain()
        if "r" in box:
            break
        time.sleep(0.01)
    t.join(1)
    return box["r"], game


def test_status_tool_returns_only_live_fields():
    payload, _game = _call(status)
    assert payload["ok"] is True
    assert payload["girders"] == 0
    assert payload["peak_load"] == 0.0
    assert set(payload) <= set(LIVE_FIELDS)
    assert "materials" not in payload and "anchors" not in payload


def test_place_girder_plain_function():
    payload, game = _call(place_girder, -6.0, 3.0, -4.0, 3.0)
    assert payload["ok"] is True
    assert game.status()["girders"] == 1


def test_start_train_spawns_and_unpauses():
    payload, game = _call(start_train)
    assert payload["ok"] is True
    assert payload["paused"] is False
    assert game.status()["train"] in ("on_track", "absent")


def _listed_tools() -> dict:
    return {t.name: t for t in asyncio.run(mcp.list_tools())}


def test_all_tools_are_exposed():
    assert set(_listed_tools()) == {
        "status",
        "place_girder",
        "place_girders",
        "build_design",
        "destroy_at",
        "start_train",
        "pause",
        "reset",
    }


def test_place_girder_schema():
    schema = _listed_tools()["place_girder"].input_schema
    assert schema["required"] == ["x1", "y1", "x2", "y2"]
    assert schema["properties"]["x1"]["description"].startswith("Coordinate in metres")
    material = schema["properties"]["material"]
    assert material["enum"] == MATERIAL_ORDER
    assert material["default"] == "steel"


def test_place_girders_schema_is_a_list_of_beams():
    schema = _listed_tools()["place_girders"].input_schema
    assert schema["required"] == ["beams"]
    beams = schema["properties"]["beams"]
    assert beams["type"] == "array"
    assert "build order" in beams["description"]
    beam = schema["$defs"]["Beam"]
    assert beam["required"] == ["x1", "y1", "x2", "y2"]
    assert beam["properties"]["material"]["enum"] == MATERIAL_ORDER
    assert beam["properties"]["material"]["default"] == "steel"


def test_place_girders_tool_builds_in_one_call():
    from bridge_builder.solution.mcp_tools import Beam

    beams = [Beam(x1=-6, y1=3, x2=-4, y2=3), Beam(x1=-4, y1=3, x2=-2, y2=3, material="wood")]
    payload, game = _call(place_girders, beams)
    assert payload["ok"] is True
    assert payload["placed"] == 2
    assert game.status()["girders"] == 2


def test_build_design_tool_resets_and_builds_a_reference_design():
    payload, game = _call(build_design, "truss")
    assert payload["ok"] is True
    assert payload["design"] == "truss"
    assert payload["placed"] == 21
    assert payload["benchmark"] == {"cost": 2100, "result": "win", "peak_load": 0.75}
    assert game.status()["cost"] == 2100


def test_build_design_tool_names_the_choices_for_an_unknown_design():
    payload, _game = _call(build_design, "suspension")
    assert payload["ok"] is False
    assert "choose one of cable_stayed" in payload["error"]


def test_tool_annotations():
    tools = _listed_tools()
    assert tools["status"].annotations.read_only_hint is True
    assert tools["reset"].annotations.destructive_hint is True
    assert tools["destroy_at"].annotations.destructive_hint is True
    assert tools["place_girder"].annotations.destructive_hint is False
    assert tools["place_girders"].annotations.destructive_hint is False
    assert tools["build_design"].annotations.destructive_hint is True  # it resets the level first


def test_place_girder_tool_accepts_material():
    payload, game = _call(place_girder, -6.0, 3.0, -4.0, 3.0, material="titanium")
    assert payload["ok"] is True
    assert payload["material"] == "titanium"
    assert game.status()["cost"] == game.status()["materials"]["titanium"]["cost"]


def test_level_resource_holds_the_fixed_facts():
    text, _game = _call(lambda: _read("bridge://level"))
    facts = json.loads(text)
    assert set(facts["materials"]) == {"wood", "steel", "titanium"}
    assert facts["materials"]["wood"]["break_force"] == 0.6 * facts["materials"]["steel"]["break_force"]
    assert facts["gap"] == [-6.0, 6.0]
    assert [-6.0, 3.0] in facts["anchors"]
    assert facts["budget"] == 30000
    assert "ok" not in facts
    assert "bridge://level" in mcp.instructions


def test_level_resource_without_game_is_an_error():
    bind_api(None)
    with pytest.raises(Exception, match="game is not running"):
        _read("bridge://level")


# --- resources ---------------------------------------------------------------


def test_catalog_level_and_clients_are_listed_resources():
    resources = {str(r.uri): r for r in asyncio.run(mcp.list_resources())}
    assert resources["bridge://designs"].mime_type == "text/markdown"
    assert resources["bridge://level"].mime_type == "application/json"
    assert resources["bridge://clients"].mime_type == "text/markdown"


def test_design_and_client_uris_are_templates():
    templates = {t.uri_template for t in asyncio.run(mcp.list_resource_templates())}
    assert templates == {
        "bridge://designs/{name}",
        "bridge://designs/{name}/beams",
        "bridge://clients/{client}",
    }


def _read(uri: str) -> str:
    (content,) = asyncio.run(mcp.read_resource(uri))
    return content.content


def test_read_catalog_card_and_beams():
    assert "| `cable_stayed` |" in _read("bridge://designs")
    assert _read("bridge://designs/timber_arch").startswith("# Timber arch")
    beams = json.loads(_read("bridge://designs/timber_arch/beams"))
    assert beams["name"] == "timber_arch"
    assert len(beams["beams"]) == 28


def test_unknown_design_resource_is_an_error():
    with pytest.raises(Exception, match="unknown design 'bridge'"):
        _read("bridge://designs/bridge")


# --- prompts -----------------------------------------------------------------


def _prompts() -> dict:
    return {p.name: p for p in asyncio.run(mcp.list_prompts())}


def test_build_design_prompt_is_listed_with_choices():
    prompt = _prompts()["design"]
    (arg,) = prompt.arguments
    assert arg.name == "design"
    assert arg.required is False
    assert arg.description.startswith("One of: cable_stayed, inverted_truss, timber_arch, truss")


def test_build_design_prompt_embeds_card_and_beams():
    result = asyncio.run(mcp.get_prompt("design", {"design": "timber_arch"}))
    card, beams, instructions = result.messages
    assert str(card.content.resource.uri) == "bridge://designs/timber_arch"
    assert str(beams.content.resource.uri) == "bridge://designs/timber_arch/beams"
    assert 'build_design with name "timber_arch"' in instructions.content.text
    assert "all 28 beams" in instructions.content.text
    assert "cost is 3160" in instructions.content.text


@pytest.mark.parametrize("args", [None, {}, {"design": ""}])
def test_build_design_without_a_design_lists_the_choices(args):
    result = asyncio.run(mcp.get_prompt("design", args))
    catalog, ask = result.messages
    assert str(catalog.content.resource.uri) == "bridge://designs"
    assert "| `cable_stayed` |" in catalog.content.resource.text
    assert "ask which one to build" in ask.content.text
    assert "or a custom design" in ask.content.text
    assert "cable_stayed, inverted_truss, timber_arch, truss" in ask.content.text
    assert "is not one of" not in ask.content.text


def test_build_design_with_an_unknown_design_lists_the_choices():
    result = asyncio.run(mcp.get_prompt("design", {"design": "suspension"}))
    _catalog, ask = result.messages
    assert ask.content.text.startswith("'suspension' is not one of the reference designs.")


def test_build_design_accepts_loose_spelling():
    result = asyncio.run(mcp.get_prompt("design", {"design": " Cable-Stayed "}))
    assert str(result.messages[0].content.resource.uri) == "bridge://designs/cable_stayed"


# --- client briefs -------------------------------------------------------------


def test_client_index_and_brief_resources():
    assert "| `fetnis` | FETNIS |" in _read("bridge://clients")
    assert _read("bridge://clients/fetnis").startswith("# FETNIS")


def test_unknown_client_resource_is_an_error():
    with pytest.raises(Exception, match="unknown client 'nasa'"):
        _read("bridge://clients/nasa")


def test_brief_prompt_takes_an_optional_client():
    (arg,) = _prompts()["brief"].arguments
    assert arg.name == "client"
    assert arg.required is False
    assert "bridge://clients" in arg.description


def test_brief_prompt_embeds_brief_and_catalog_then_asks_for_a_checked_build():
    result = asyncio.run(mcp.get_prompt("brief", {"client": "fetnis"}))
    brief, catalog, instructions = result.messages
    assert str(brief.content.resource.uri) == "bridge://clients/fetnis"
    assert str(catalog.content.resource.uri) == "bridge://designs"
    text = instructions.content.text
    assert "FETNIS" in text
    for step in ("Screen every reference design", "build_design", "place_girders", "start_train", "Verify", "cheapest"):
        assert step in text


@pytest.mark.parametrize("args", [None, {"client": ""}, {"client": "nasa"}])
def test_brief_prompt_without_a_known_client_lists_the_briefs(args):
    result = asyncio.run(mcp.get_prompt("brief", args))
    index, ask = result.messages
    assert str(index.content.resource.uri) == "bridge://clients"
    assert "ask which client" in ask.content.text


def test_brief_prompt_accepts_loose_spelling():
    result = asyncio.run(mcp.get_prompt("brief", {"client": " FETNIS "}))
    assert str(result.messages[0].content.resource.uri) == "bridge://clients/fetnis"
