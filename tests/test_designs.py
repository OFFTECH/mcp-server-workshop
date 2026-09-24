import json

import pytest

from bridge_builder.benchmark import run_benchmark
from bridge_builder.designs import get_design, load_designs, render_beams, render_card, render_catalog

NAMES = ["cable_stayed", "inverted_truss", "timber_arch", "truss"]


def test_knowledge_folder_has_the_four_designs():
    assert sorted(load_designs()) == NAMES


@pytest.mark.parametrize("name", NAMES)
def test_design_matches_its_recorded_benchmark(name):
    design = get_design(name)
    measured = run_benchmark(design.beams)
    assert measured["result"] == design.benchmark["result"] == "win"
    assert measured["cost"] == design.benchmark["cost"]
    assert measured["peak_load"] == pytest.approx(design.benchmark["peak_load"], abs=0.05), (
        f"{name}: re-run `python -m bridge_builder.benchmark` and update {name}.json"
    )


def test_unknown_design_names_the_choices():
    with pytest.raises(ValueError, match="unknown design 'bridge'; choose one of cable_stayed, inverted_truss"):
        get_design("bridge")


def test_card_includes_benchmark_and_beams_link():
    card = render_card(get_design("timber_arch"))
    assert card.startswith("# Timber arch")
    assert "## How it carries load" in card
    assert "| 28 | steel, wood | 3160 | win | 0.74 |" in card
    assert "bridge://designs/timber_arch/beams" in card


def test_catalog_lists_every_design():
    catalog = render_catalog(load_designs())
    for name in NAMES:
        assert f"| `{name}` |" in catalog


def test_catalog_runs_cheapest_first_then_by_margin():
    catalog = render_catalog(load_designs())
    order = [line.split("`")[1] for line in catalog.splitlines() if line.startswith("| `")]
    assert order == ["inverted_truss", "truss", "timber_arch", "cable_stayed"]


def test_catalog_shows_materials():
    catalog = render_catalog(load_designs())
    assert "| materials |" in catalog
    (arch_row,) = [line for line in catalog.splitlines() if line.startswith("| `timber_arch`")]
    assert "| steel, wood |" in arch_row


def test_beams_are_place_girder_arguments():
    data = json.loads(render_beams(get_design("truss")))
    assert data["beams"][0] == {"x1": -6.0, "y1": 3.0, "x2": -4.0, "y2": 3.0, "material": "steel"}
    assert len(data["beams"]) == 21


def test_beams_are_one_per_line_with_whole_coordinates():
    text = render_beams(get_design("truss"))
    assert '\n  {"x1": -6, "y1": 3, "x2": -4, "y2": 3, "material": "steel"},\n' in text
    assert text.count("\n") == 21 + 2


def test_card_without_data_file_is_rejected(tmp_path):
    (tmp_path / "orphan.md").write_text("## How it carries load\n", encoding="utf-8")
    with pytest.raises(ValueError, match="orphan.md has no matching orphan.json"):
        load_designs(tmp_path)


def test_unknown_material_is_rejected(tmp_path):
    (tmp_path / "gold.md").write_text("card", encoding="utf-8")
    (tmp_path / "gold.json").write_text(
        json.dumps({"title": "t", "summary": "s", "benchmark": {}, "beams": [[-6, 3, -4, 3, "gold"]]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown materials"):
        load_designs(tmp_path)


# Claims the cards make beyond the benchmark table ---------------------------


def test_inverted_truss_without_inner_diagonals_hangs_like_a_chain():
    inner = {(-4.0, 3.0, -2.0, 1.0), (-2.0, 3.0, 0.0, 1.0), (0.0, 1.0, 2.0, 3.0), (2.0, 1.0, 4.0, 3.0)}
    design = get_design("inverted_truss")
    beams = [b for b in design.beams if b[:4] not in inner]
    assert run_benchmark(beams)["peak_load"] > 2 * design.benchmark["peak_load"]


@pytest.mark.parametrize("name", ["truss", "inverted_truss", "timber_arch"])
def test_trusses_are_triangulated_and_barely_sag(name):
    # a four-sided panel of pinned beams can shear flat; the braces prevent it
    from bridge_builder.physics import World

    w = World()
    for x1, y1, x2, y2, material in get_design(name).beams:
        w.place_girder(x1, y1, x2, y2, material=material)
    for _ in range(int(3.0 / w.DT)):
        w.step()
    sag = max(abs(w.structure.node_position(n)[1] - n[1]) for n in w.structure.node_keys())
    assert sag < 0.05


def test_arch_without_braces_sways_and_sags():
    from bridge_builder.physics import World

    braces = {
        (-4.0, 3.0, -2.0, 5.0), (-4.0, 5.0, -2.0, 3.0), (4.0, 3.0, 2.0, 5.0), (4.0, 5.0, 2.0, 3.0),
        (-2.0, 3.0, 0.0, 5.0), (2.0, 3.0, 0.0, 5.0), (-2.0, 5.0, 0.0, 5.0), (0.0, 5.0, 2.0, 5.0),
    }
    w = World()
    for x1, y1, x2, y2, material in get_design("timber_arch").beams:
        if (x1, y1, x2, y2) not in braces:
            w.place_girder(x1, y1, x2, y2, material=material)
    for _ in range(int(3.0 / w.DT)):
        w.step()
    sag = max(abs(w.structure.node_position(n)[1] - n[1]) for n in w.structure.node_keys())
    assert sag > 0.05


def test_timber_arch_needs_steel_in_its_sloped_rib():
    design = get_design("timber_arch")
    steel_deck_only = [(*b[:4], "steel" if b[1] == b[3] == 3.0 else "wood") for b in design.beams]
    assert run_benchmark(steel_deck_only)["result"] == "lose"
    assert run_benchmark([(*b[:4], "wood") for b in design.beams])["result"] == "lose"


def test_timber_arch_has_the_highest_wood_share():
    def wood_share(d):
        return sum(b[4] == "wood" for b in d.beams) / len(d.beams)

    designs = load_designs()
    assert max(designs.values(), key=wood_share).name == "timber_arch"


def test_cable_stayed_backstays_add_margin():
    design = get_design("cable_stayed")
    without = [b for b in design.beams if abs(b[0]) <= 6 and abs(b[2]) <= 6]
    measured = run_benchmark(without)
    assert measured["peak_load"] > design.benchmark["peak_load"] + 0.1
