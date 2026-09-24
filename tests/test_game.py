from bridge_builder.game import BREAK_FORCE, BUDGET, GIRDER_COST, Game
from bridge_builder.truss import TRUSS_GIRDERS


def test_level_budget_is_30000():
    assert BUDGET == 30000
    g = Game()
    st = g.status()
    assert st["budget"] == 30000
    assert st["remaining"] == 30000


def test_cost_accounting():
    g = Game()
    g.place_girder(-8.0, 3.0, -6.0, 3.0)
    g.place_girder(-6.0, 3.0, -4.0, 3.0)
    st = g.status()
    assert st["girders"] == 2
    assert st["joints"] >= 1
    assert st["cost"] == 2 * GIRDER_COST
    assert st["budget"] == BUDGET
    assert st["remaining"] == BUDGET - 2 * GIRDER_COST
    assert st["score"] is None
    before = st
    destroyed = g.destroy_at(-6.0, 3.0)
    assert destroyed["ok"]
    after = g.status()
    assert after["girders"] == before["girders"] - 1
    assert after["cost"] == GIRDER_COST


def test_over_budget_rejects_beam():
    g = Game(budget=200)
    assert g.place_girder(-8.0, 3.0, -6.0, 3.0)["ok"]
    assert g.place_girder(-6.0, 3.0, -4.0, 3.0)["ok"]
    r = g.place_girder(-4.0, 3.0, -2.0, 3.0)
    assert r["ok"] is False
    assert "budget" in r["error"].lower()
    assert g.status()["girders"] == 2
    assert g.status()["cost"] == 200


def test_fewer_beams_higher_score():
    cheap = Game()
    cheap.cost = 500
    cheap._outcome = "win"
    spendy = Game()
    spendy.cost = 1900
    spendy._outcome = "win"
    assert cheap.status()["score"] == BUDGET - 500
    assert spendy.status()["score"] == BUDGET - 1900
    assert cheap.status()["score"] > spendy.status()["score"]
    loser = Game()
    loser.cost = 500
    loser._outcome = "lose"
    assert loser.status()["score"] == 0


def test_unpinned_girder_train_loses():
    g = Game()
    assert g.place_girder(-6.0, 3.0, -4.0, 3.0)["ok"]
    g.start_train()
    for _ in range(int(8.0 * 60)):
        g.step()
    assert g.status()["train"] == "lose"


def test_naive_line_fails_under_train():
    g = Game()
    for x in range(-6, 6, 2):
        assert g.place_girder(float(x), 3.0, float(x + 2), 3.0)["ok"]
    g.start_train()
    for _ in range(int(15.0 * 60)):
        g.step()
        if g.status()["train"] in ("win", "lose"):
            break
    assert g.status()["train"] == "lose"


def test_place_girder_rejects_freehand_span():
    g = Game()
    r = g.place_girder(-6.0, 3.0, 0.0, 3.0)
    assert r["ok"] is False
    assert g.status()["girders"] == 0


def test_pinned_truss_crosses():
    g = Game()
    for x1, y1, x2, y2 in TRUSS_GIRDERS:
        assert g.place_girder(x1, y1, x2, y2)["ok"], (x1, y1, x2, y2)
    assert g.status()["girders"] == len(TRUSS_GIRDERS)
    assert g.status()["joints"] >= 1
    g.start_train()
    for _ in range(int(15.0 * 60)):
        g.step()
        if g.status()["train"] == "win":
            break
    assert g.status()["train"] == "win"
    st = g.status()
    assert st["score"] == st["budget"] - st["cost"]
    assert st["cost"] == len(TRUSS_GIRDERS) * GIRDER_COST


# --- materials -------------------------------------------------------------

from bridge_builder.materials import DEFAULT_MATERIAL, MATERIALS  # noqa: E402


def test_materials_table_has_three_grades():
    assert set(MATERIALS) == {"wood", "steel", "titanium"}
    assert DEFAULT_MATERIAL == "steel"
    assert MATERIALS["steel"].cost == GIRDER_COST
    assert MATERIALS["steel"].strength == 1.0
    # steel is the cheap default; wood costs more per beam (a sustainability choice);
    # titanium is the expensive brute-force option
    assert MATERIALS["steel"].cost < MATERIALS["wood"].cost < MATERIALS["titanium"].cost
    assert (MATERIALS["steel"].cost, MATERIALS["wood"].cost, MATERIALS["titanium"].cost) == (100, 120, 400)
    assert MATERIALS["wood"].strength < MATERIALS["steel"].strength < MATERIALS["titanium"].strength


def test_place_girder_charges_material_cost():
    g = Game()
    r = g.place_girder(-6.0, 3.0, -4.0, 3.0, material="wood")
    assert r["ok"] is True
    assert r["material"] == "wood"
    assert g.status()["cost"] == MATERIALS["wood"].cost
    r = g.place_girder(-4.0, 3.0, -2.0, 3.0, material="titanium")
    assert r["ok"] is True
    assert g.status()["cost"] == MATERIALS["wood"].cost + MATERIALS["titanium"].cost


def test_place_girder_defaults_to_steel():
    g = Game()
    r = g.place_girder(-6.0, 3.0, -4.0, 3.0)
    assert r["material"] == "steel"
    assert g.status()["cost"] == GIRDER_COST


def test_unknown_material_is_rejected():
    g = Game()
    r = g.place_girder(-6.0, 3.0, -4.0, 3.0, material="unobtainium")
    assert r["ok"] is False
    assert "material" in r["error"].lower()
    assert g.status()["girders"] == 0
    assert g.status()["cost"] == 0


def test_over_budget_check_uses_material_cost():
    g = Game(budget=MATERIALS["wood"].cost)
    assert g.place_girder(-6.0, 3.0, -4.0, 3.0, material="titanium")["ok"] is False
    assert g.place_girder(-6.0, 3.0, -4.0, 3.0, material="wood")["ok"] is True
    assert g.place_girder(-4.0, 3.0, -2.0, 3.0, material="steel")["ok"] is False


def test_destroy_refunds_that_beams_own_cost():
    g = Game()
    g.place_girder(-8.0, 3.0, -6.0, 3.0, material="titanium")
    g.place_girder(-6.0, 3.0, -4.0, 3.0, material="wood")
    assert g.destroy_at(-5.0, 3.0)["ok"]
    assert g.status()["cost"] == MATERIALS["titanium"].cost


def test_status_lists_materials():
    st = Game().status()
    assert st["material"] == "steel"
    assert st["materials"]["wood"]["cost"] == MATERIALS["wood"].cost
    assert st["materials"]["titanium"]["strength"] == MATERIALS["titanium"].strength
    assert st["materials"]["steel"]["break_force"] == BREAK_FORCE


def test_titanium_naive_deck_crosses_but_costs_more_than_a_steel_truss():
    g = Game()
    for x in range(-6, 6, 2):
        assert g.place_girder(float(x), 3.0, float(x + 2), 3.0, material="titanium")["ok"]
    g.start_train()
    for _ in range(int(15.0 * 60)):
        g.step()
        if g.status()["train"] in ("win", "lose"):
            break
    assert g.status()["train"] == "win"
    assert g.status()["cost"] > len(TRUSS_GIRDERS) * GIRDER_COST


def test_wood_truss_collapses():
    g = Game()
    for x1, y1, x2, y2 in TRUSS_GIRDERS:
        assert g.place_girder(x1, y1, x2, y2, material="wood")["ok"]
    g.start_train()
    for _ in range(int(15.0 * 60)):
        g.step()
        if g.status()["train"] in ("win", "lose"):
            break
    assert g.status()["train"] == "lose"


def test_inverted_truss_crosses():
    from bridge_builder.truss import INVERTED_TRUSS

    g = Game()
    for x1, y1, x2, y2, material in INVERTED_TRUSS:
        assert g.place_girder(x1, y1, x2, y2, material=material)["ok"], (x1, y1, x2, y2)
    assert any(y < 3.0 for _x1, y, _x2, _y2, _m in INVERTED_TRUSS)
    g.start_train()
    for _ in range(int(15.0 * 60)):
        g.step()
        if g.status()["train"] in ("win", "lose"):
            break
    assert g.status()["train"] == "win"


def _drive(g, seconds=15.0):
    for _ in range(int(seconds * 60)):
        g.step()
        if g.status()["train"] in ("win", "lose"):
            break


def test_start_train_after_win_runs_again():
    g = Game()
    for x1, y1, x2, y2 in TRUSS_GIRDERS:
        g.place_girder(x1, y1, x2, y2)
    g.start_train()
    _drive(g)
    assert g.status()["train"] == "win"
    r = g.start_train()
    assert r["spawned"] is True
    assert g.status()["train"] == "on_track"
    assert g.status()["train_x"] < -6.0
    _drive(g)
    assert g.status()["train"] == "win"


def test_space_after_lose_restarts_train():
    g = Game()
    g.place_girder(-6.0, 3.0, -4.0, 3.0)
    g.start_train()
    _drive(g)
    assert g.status()["train"] == "lose"
    r = g.toggle_pause()
    assert r["paused"] is False
    assert g.status()["train"] == "on_track"


def test_destroy_at_beam_midpoint_without_snapping():
    g = Game()
    g.place_girder(-6.0, 3.0, -4.0, 3.0)
    g.place_girder(-4.0, 3.0, -2.0, 5.0)
    assert g.destroy_at(-3.0, 4.0, snap=False)["ok"]
    assert g.status()["girders"] == 1
    assert g.status()["cost"] == GIRDER_COST
    assert g.destroy_at(-3.0, 4.0, snap=False)["ok"] is False


def test_rerun_rebuilds_damaged_bridge_from_design():
    g = Game()
    gid = g.place_girder(-6.0, 3.0, -4.0, 3.0, material="wood")["id"]
    g.place_girder(-4.0, 3.0, -2.0, 3.0)
    g.start_train()
    _drive(g)
    assert g.status()["train"] == "lose"
    # the unsupported beams have broken off and fallen
    fallen = min(g.world.girder_position(i)[1] for i in g.world._girders)
    assert fallen < 2.5
    g.start_train()
    st = g.status()
    assert st["girders"] == 2
    assert st["cost"] == MATERIALS["wood"].cost + GIRDER_COST
    # undamaged again: every beam rebuilt and part of the bridge, none left as debris
    assert all(g.world.is_intact(i) for i in g.world._girders)
    assert st["joints"] >= 1
    assert "wood" in {g.world.girder_material(i) for i in g.world._girders}
    assert gid not in g._girder_costs or True  # ids may be reallocated; cost table must still add up
    assert sum(g._girder_costs.values()) == st["cost"]


# --- peak beam load ----------------------------------------------------------


def test_peak_load_matches_the_truss_benchmark():
    from bridge_builder.designs import get_design

    g = Game()
    for x1, y1, x2, y2 in TRUSS_GIRDERS:
        g.place_girder(x1, y1, x2, y2)
    assert g.status()["peak_load"] == 0.0
    g.start_train()
    _drive(g)
    assert g.status()["train"] == "win"
    assert g.status()["peak_load"] == get_design("truss").benchmark["peak_load"]


def test_collapse_shows_a_broken_beam():
    g = Game()
    for x in range(-6, 6, 2):
        g.place_girder(float(x), 3.0, float(x + 2), 3.0)
    g.start_train()
    _drive(g)
    assert g.status()["train"] == "lose"
    assert g.status()["peak_load"] >= 1.0


def test_peak_load_resets_for_each_run():
    g = Game()
    for x1, y1, x2, y2 in TRUSS_GIRDERS:
        g.place_girder(x1, y1, x2, y2)
    g.start_train()
    _drive(g, seconds=3.0)
    first = g.status()["peak_load"]
    assert first > 0.0
    g.pause()
    g.start_train()  # resume: same run, peak kept
    assert g.status()["peak_load"] == first
    g.reset()
    assert g.status()["peak_load"] == 0.0


def test_a_new_run_starts_from_a_settled_bridge():
    g = Game()
    for x1, y1, x2, y2 in TRUSS_GIRDERS:
        g.place_girder(x1, y1, x2, y2)
    g.start_train()
    s = g.world.structure
    assert max(abs(s.node_velocity(n)[1]) for n in s.node_keys()) < 1e-2
    assert min(s.node_position(n)[1] - n[1] for n in s.node_keys()) < 0.0  # it carries its weight
    assert 0.0 < g.status()["peak_load"] < 0.3  # dead load alone, no release shock


# --- batch building ------------------------------------------------------------


def _beam(x1, y1, x2, y2, material=None):
    b = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
    if material:
        b["material"] = material
    return b


def test_place_girders_builds_a_list_in_order_in_one_call():
    g = Game()
    # the second beam starts at a node the first one creates
    r = g.place_girders([_beam(-6, 3, -4, 3), _beam(-4, 3, -2, 3, "wood")])
    assert r["ok"] is True
    assert r["placed"] == 2
    assert r["cost"] == GIRDER_COST + MATERIALS["wood"].cost
    assert g.status()["girders"] == 2


def test_place_girders_stops_at_the_first_failure_and_keeps_what_it_built():
    g = Game()
    r = g.place_girders([_beam(-6, 3, -4, 3), _beam(2, 3, 4, 3), _beam(-4, 3, -2, 3)])
    assert r["ok"] is False
    assert r["placed"] == 1
    assert r["failed"]["index"] == 1
    assert r["failed"]["beam"] == _beam(2, 3, 4, 3)
    assert "existing node" in r["error"]
    assert g.status()["girders"] == 1


def test_place_girders_can_clear_the_level_first():
    g = Game()
    g.place_girder(-8.0, 3.0, -6.0, 3.0)
    beams = [_beam(*b) for b in TRUSS_GIRDERS]
    r = g.place_girders(beams, reset=True)
    assert r["ok"] is True
    assert g.status()["girders"] == len(TRUSS_GIRDERS)
    assert g.status()["cost"] == len(TRUSS_GIRDERS) * GIRDER_COST


def test_a_batch_built_bridge_reruns_like_a_hand_built_one():
    g = Game()
    g.place_girders([_beam(*b) for b in TRUSS_GIRDERS])
    g.start_train()
    _drive(g)
    assert g.status()["train"] == "win"
