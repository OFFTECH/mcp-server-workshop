import math

import pytest

from bridge_builder.structure import Structure, compression_limit

DT = 1.0 / 60.0


def _settle(s, seconds=3.0):
    for _ in range(int(seconds / DT)):
        s.step(DT)


def test_two_bar_truss_matches_hand_statics():
    # apex (0,2) on two 45-degree bars from fixed (-2,0) and (2,0); load P down at the apex
    s = Structure(fixed={(-2.0, 0.0), (2.0, 0.0)}, gravity=0.0)
    s.add_member(1, (-2.0, 0.0), (0.0, 2.0), stiffness=1e5, mass=1.0)
    s.add_member(2, (2.0, 0.0), (0.0, 2.0), stiffness=1e5, mass=1.0)
    for _ in range(int(3.0 / DT)):
        s.add_node_load((0.0, 2.0), 0.0, -100.0)
        s.step(DT)
    # each bar pushes with P / (2 sin 45) = 70.7 N
    assert s.member_force(1) == pytest.approx(-100.0 / math.sqrt(2.0), rel=0.02)
    assert s.member_force(2) == pytest.approx(-100.0 / math.sqrt(2.0), rel=0.02)


def test_straight_chain_needs_far_more_pull_than_the_load():
    # six pinned links in a straight line between two anchors: a mechanism that can
    # only carry a load by sagging, so its tension dwarfs the load
    s = Structure(fixed={(-6.0, 0.0), (6.0, 0.0)}, gravity=0.0)
    for i, x in enumerate(range(-6, 6, 2)):
        s.add_member(i, (float(x), 0.0), (float(x + 2), 0.0), stiffness=1e5, mass=0.6)
    for _ in range(int(4.0 / DT)):
        s.add_node_load((0.0, 0.0), 0.0, -100.0)
        s.step(DT)
    assert s.member_force(0) > 5 * 100.0
    assert s.node_position((0.0, 0.0))[1] < -0.05  # it sagged


def test_single_beam_from_a_fixed_node_swings_down():
    s = Structure(fixed={(0.0, 0.0)})
    s.add_member(1, (0.0, 0.0), (2.0, 0.0), stiffness=1e5, mass=0.6)
    _settle(s, 4.0)
    x, y = s.node_position((2.0, 0.0))
    assert y < -1.5
    assert math.hypot(x, y) == pytest.approx(2.0, abs=0.02)


def test_overloaded_beam_breaks_and_leaves_the_structure():
    s = Structure(fixed={(0.0, 0.0)}, gravity=0.0)
    s.add_member(1, (0.0, 0.0), (0.0, -2.0), stiffness=1e5, mass=0.6, tension_limit=50.0)
    broken: list[int] = []
    for _ in range(60):
        s.add_node_load((0.0, -2.0), 0.0, -100.0)
        broken += s.step(DT)
    assert broken == [1]
    assert not s.has_member(1)
    assert s.peak_load >= 1.0


def test_load_fraction_uses_tension_and_buckling_limits():
    s = Structure(fixed={(-2.0, 0.0), (2.0, 0.0)}, gravity=0.0)
    s.add_member(1, (-2.0, 0.0), (0.0, 2.0), stiffness=1e5, mass=1.0, tension_limit=1000.0)
    s.add_member(2, (2.0, 0.0), (0.0, 2.0), stiffness=1e5, mass=1.0, tension_limit=1000.0)
    for _ in range(int(3.0 / DT)):
        s.add_node_load((0.0, 2.0), 0.0, -100.0)
        s.step(DT)
    # 70.7 N push against a buckling limit of 1000 * (2 / 2.83)^2 = 500 N
    assert s.load_fraction(1) == pytest.approx(70.7 / 500.0, rel=0.03)


def test_compression_limit_falls_with_length_squared():
    assert compression_limit(1000.0, 2.0) == pytest.approx(1000.0)
    assert compression_limit(1000.0, 2.0 * math.sqrt(2.0)) == pytest.approx(500.0)
    assert compression_limit(1000.0, 1.0) == pytest.approx(1000.0)  # short beams yield before buckling


def test_point_load_on_a_beam_splits_between_its_end_nodes():
    s = Structure(fixed=set(), gravity=0.0)
    s.add_member(1, (0.0, 0.0), (2.0, 0.0), stiffness=1e5, mass=1.0)
    s.apply_load(1, 0.5, 0.0, 0.0, -100.0)
    assert s.node_load((0.0, 0.0)) == pytest.approx((0.0, -75.0))
    assert s.node_load((2.0, 0.0)) == pytest.approx((0.0, -25.0))


def test_removing_a_beam_drops_nodes_nothing_else_holds():
    s = Structure(fixed={(0.0, 0.0)})
    s.add_member(1, (0.0, 0.0), (2.0, 0.0), stiffness=1e5, mass=0.6)
    s.add_member(2, (2.0, 0.0), (4.0, 0.0), stiffness=1e5, mass=0.6)
    s.remove_member(2)
    assert s.has_node((2.0, 0.0))
    assert not s.has_node((4.0, 0.0))


def test_a_riding_load_adds_its_mass_to_the_end_nodes():
    s = Structure(fixed=set(), gravity=0.0)
    s.add_member(1, (0.0, 0.0), (2.0, 0.0), stiffness=1e5, mass=1.0)
    s.apply_load(1, 1.5, 0.0, 0.0, -98.0, mass=10.0)
    assert s.node_extra_mass((0.0, 0.0)) == pytest.approx(2.5)
    assert s.node_extra_mass((2.0, 0.0)) == pytest.approx(7.5)
    s.step(DT)
    assert s.node_extra_mass((2.0, 0.0)) == 0.0  # only for the step it was applied to


def test_riding_mass_slows_the_response_to_a_load():
    def drop_after_one_frame(mass):
        s = Structure(fixed={(-2.0, 0.0), (2.0, 0.0)}, gravity=0.0)
        s.add_member(1, (-2.0, 0.0), (0.0, 2.0), stiffness=1e5, mass=1.0)
        s.add_member(2, (2.0, 0.0), (0.0, 2.0), stiffness=1e5, mass=1.0)
        s.apply_load(1, 0.0, 2.0, 0.0, -500.0, mass=mass)
        s.step(DT)
        return 2.0 - s.node_position((0.0, 2.0))[1]

    assert drop_after_one_frame(50.0) < drop_after_one_frame(0.0)


def test_a_piece_cut_off_from_every_anchor_is_released():
    s = Structure(fixed={(0.0, 0.0)}, gravity=0.0)
    s.add_member(1, (0.0, 0.0), (2.0, 0.0), stiffness=1e5, mass=0.6, tension_limit=50.0)
    s.add_member(2, (2.0, 0.0), (4.0, 0.0), stiffness=1e5, mass=0.6)
    s.add_member(3, (4.0, 0.0), (4.0, 2.0), stiffness=1e5, mass=0.6)
    released: list[int] = []
    for _ in range(60):
        s.add_node_load((4.0, 0.0), 100.0, 0.0)
        released += s.step(DT)
    assert sorted(released) == [1, 2, 3]  # 1 snapped; 2 and 3 fall away with nothing to hold them
    assert s.member_ids() == []


def test_settle_brings_the_truss_to_rest_under_its_own_weight_without_overshoot():
    s = Structure(fixed={(-2.0, 0.0), (2.0, 0.0)})
    s.add_member(1, (-2.0, 0.0), (0.0, 2.0), stiffness=1e5, mass=1.0, tension_limit=1000.0)
    s.add_member(2, (2.0, 0.0), (0.0, 2.0), stiffness=1e5, mass=1.0, tension_limit=1000.0)
    s.settle()
    assert max(math.hypot(*s.node_velocity(k)) for k in s.node_keys()) < 1e-3
    # apex carries half of each bar's weight: 9.8 N, so each bar pushes 9.8 / (2 sin 45) = 6.93 N
    assert s.member_force(1) == pytest.approx(-6.93, rel=0.03)
    assert s.peak_load == pytest.approx(6.93 / 500.0, rel=0.05)  # no dynamic overshoot
