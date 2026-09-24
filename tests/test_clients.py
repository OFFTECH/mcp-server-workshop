import pytest

from bridge_builder.clients import client_uri, get_brief, load_briefs, render_client_index


def test_fetnis_brief_ships_with_the_game():
    brief = get_brief("fetnis")
    assert brief.title == "FETNIS"
    assert "ships" in brief.summary
    assert brief.text.startswith("# FETNIS")


def test_fetnis_brief_states_clearance_wood_share_and_cost_order():
    text = get_brief("fetnis").text
    assert "Clearance" in text and "y >= 3" in text
    assert "wood share" in text
    assert text.index("Clearance") < text.index("Sustainability") < text.index("Cost")


def test_a_new_brief_file_is_picked_up_without_a_restart(tmp_path):
    (tmp_path / "harbour.md").write_text(
        "# Harbour Authority\n\nCheapest bridge that ships can pass under.\n\n## Requirements\n",
        encoding="utf-8",
    )
    briefs = load_briefs(tmp_path)
    assert list(briefs) == ["harbour"]
    assert briefs["harbour"].title == "Harbour Authority"
    assert briefs["harbour"].summary == "Cheapest bridge that ships can pass under."


def test_a_brief_without_a_title_still_loads_and_does_not_hide_the_others(tmp_path):
    # workshop attendees write briefs live: one rough file must not break the rest
    (tmp_path / "anon.md").write_text("Cheapest, please.\n", encoding="utf-8")
    (tmp_path / "fetnis.md").write_text("# FETNIS\n\nShips pass under.\n", encoding="utf-8")
    briefs = load_briefs(tmp_path)
    assert briefs["anon"].title == "anon"
    assert briefs["anon"].summary == "Cheapest, please."
    assert briefs["fetnis"].title == "FETNIS"


def test_unknown_client_names_the_choices(tmp_path):
    (tmp_path / "fetnis.md").write_text("# FETNIS\n", encoding="utf-8")
    (tmp_path / "harbour.md").write_text("# Harbour\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown client 'nasa'; choose one of fetnis, harbour"):
        get_brief("nasa", tmp_path)


def test_client_index_links_every_brief():
    index = render_client_index(load_briefs())
    assert "| `fetnis` | FETNIS |" in index
    assert client_uri("fetnis") == "bridge://clients/fetnis"
    assert "bridge://clients/{client}" in index
