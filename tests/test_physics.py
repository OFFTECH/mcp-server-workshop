from bridge_builder.physics import BANK_TOP_Y, GAP, GIRDER_THICKNESS, ROAD_Y, World
from bridge_builder.truss import INVERTED_TRUSS


def test_new_world_has_two_banks_and_a_gap():
    w = World()
    hits_left = w.bodies_at(-10.0, BANK_TOP_Y - 0.1)
    hits_gap = w.bodies_at(0.0, BANK_TOP_Y - 0.1)
    hits_right = w.bodies_at(10.0, BANK_TOP_Y - 0.1)
    assert len(hits_left) >= 1
    assert hits_gap == []
    assert len(hits_right) >= 1
    assert GAP == (-6.0, 6.0)


def test_place_girder_rejects_non_neighbour_span():
    w = World()
    assert w.place_girder(-6.0, 3.0, -2.0, 3.0) is None
    assert w.girder_count() == 0


def test_place_girder_snaps_to_grid_and_fixed_length():
    w = World()
    gid = w.place_girder(-5.8, 3.2, -4.1, 3.1)
    assert gid is not None
    assert abs(w.girder_length(gid) - 2.0) < 1e-6


def test_world_has_anchor_nodes_on_both_banks():
    w = World()
    assert (-6.0, 3.0) in w.anchors
    assert (6.0, 3.0) in w.anchors
    assert (0.0, 3.0) not in w.anchors
    assert w.has_node(-6.0, 3.0)
    assert not w.has_node(-4.0, 3.0)


def test_cannot_place_floating_member_away_from_nodes():
    w = World()
    assert w.place_girder(-2.0, 3.0, 0.0, 3.0) is None
    assert w.girder_count() == 0


def test_placing_from_anchor_auto_pins():
    w = World()
    gid = w.place_girder(-6.0, 3.0, -4.0, 3.0)
    assert gid is not None
    assert w.has_node(-4.0, 3.0)
    assert w.joint_count() >= 1


def test_member_from_anchor_stays_up():
    w = World()
    gid = w.place_girder(-8.0, 3.0, -6.0, 3.0)
    _x0, y0 = w.girder_position(gid)
    for _ in range(int(2.0 / w.DT)):
        w.step()
    _x1, y1 = w.girder_position(gid)
    assert y1 > y0 - 0.3


def test_joint_pins_girder_to_bank():
    w = World()
    w.place_girder(-8.0, 3.0, -6.0, 3.0)
    assert w.joint_count() >= 1


def test_add_joint_in_empty_space_returns_none():
    w = World()
    assert w.add_joint(0.0, 8.0) is None


def test_train_spawns_on_left_bank():
    w = World()
    assert w.spawn_train() is True
    pos = w.first_train_position()
    assert pos is not None
    assert pos[0] < -6.0
    assert pos[1] > 2.0
    assert w.spawn_train() is False
    assert w.spawn_train(force=True) is True


# --- road level ------------------------------------------------------------


def test_bank_surface_is_flush_with_the_top_of_a_deck_beam():
    w = World()
    gid = w.place_girder(-6.0, 3.0, -4.0, 3.0)
    deck_top = w.girder_position(gid)[1] + GIRDER_THICKNESS / 2.0
    assert ROAD_Y == deck_top
    assert w.bodies_at(-10.0, ROAD_Y - 0.01)
    assert not w.bodies_at(-10.0, ROAD_Y + 0.01)


def test_train_rolls_onto_the_deck_without_a_bump():
    w = World()
    for x1, y1, x2, y2, material in INVERTED_TRUSS:
        w.place_girder(x1, y1, x2, y2, material=material)
    w.spawn_train()
    start_y = w.first_train_position()[1]
    highest = start_y
    while w.first_train_position()[0] < -2.0:
        w.step()
        highest = max(highest, w.first_train_position()[1])
    assert highest - start_y < 0.1


# --- materials -------------------------------------------------------------


def test_girder_records_material():
    w = World()
    gid = w.place_girder(-6.0, 3.0, -4.0, 3.0, material="wood")
    assert gid is not None
    assert w.girder_material(gid) == "wood"
    assert w.girder_material(w.place_girder(-4.0, 3.0, -2.0, 3.0)) == "steel"


def test_beam_limits_follow_material_strength_and_length():
    w = World(break_force=1000.0)
    wood = w.place_girder(-6.0, 3.0, -4.0, 3.0, material="wood")
    titanium = w.place_girder(-6.0, 3.0, -4.0, 5.0, material="titanium")
    s = w.structure
    assert s._members[wood].tension_limit == 600.0
    assert s._members[wood].compression_limit == 600.0
    assert s._members[titanium].tension_limit == 2000.0
    assert abs(s._members[titanium].compression_limit - 1000.0) < 1e-6  # 2.83 m buckles at half


def test_beams_ending_on_one_node_share_a_single_pin():
    w = World()
    w.place_girder(-6.0, 3.0, -4.0, 3.0)
    w.place_girder(-4.0, 3.0, -2.0, 3.0)
    w.place_girder(-6.0, 3.0, -4.0, 5.0)  # AABB covers (-4,3) but does not end there
    assert w.structure.node_degree((-4.0, 3.0)) == 2
    assert w.joint_count() == 2  # the anchor and (-4,3); (-2,3) and (-4,5) hold one beam each


def test_only_anchors_are_fixed():
    w = World()
    w.place_girder(-6.0, 3.0, -4.0, 5.0)  # a strut leaning off an anchor, free at the top
    for _ in range(int(3.0 / w.DT)):
        w.step()
    x, y = w.structure.node_position((-4.0, 5.0))
    assert y < 3.0  # it swung down: a pinned beam cannot hold itself up


def test_broken_beam_becomes_falling_debris():
    w = World(break_force=1.0)  # far too weak to carry its own weight
    w.place_girder(-6.0, 3.0, -4.0, 3.0)
    gid = w.place_girder(-4.0, 3.0, -2.0, 3.0)
    for _ in range(30):
        w.step()
    assert not w.is_intact(gid)
    assert w.girder_position(gid)[1] < 3.0
    assert w.peak_load >= 1.0


def test_destroy_reports_girder_id():
    w = World()
    gid = w.place_girder(-6.0, 3.0, -4.0, 3.0, material="wood")
    result = w.destroy_at(-5.0, 3.0)
    assert result["destroyed"] is True
    assert result["girder_id"] == gid


# --- below-deck construction ----------------------------------------------


def test_can_hang_member_from_anchor_into_gap():
    w = World()
    gid = w.place_girder(-6.0, 3.0, -4.0, 1.0)
    assert gid is not None
    assert w.has_node(-4.0, 1.0)
    assert w.joint_count() >= 1


def test_cannot_build_into_bank_wall():
    w = World()
    assert w.place_girder(-6.0, 3.0, -8.0, 1.0) is None
    assert w.place_girder(-6.0, 3.0, -6.0, 1.0) is None
    assert w.girder_count() == 0


# --- beam contacts ---------------------------------------------------------


def _filter_allows(w, gid_a, gid_b):
    return w._contact_filter.ShouldCollide(
        w._girders[gid_a].fixtures[0], w._girders[gid_b].fixtures[0]
    )


def test_debris_sharing_a_joint_does_not_push_apart():
    w = World()
    deck = w.place_girder(-6.0, 3.0, -4.0, 3.0)
    diagonal = w.place_girder(-6.0, 3.0, -4.0, 1.0)
    post = w.place_girder(-4.0, 3.0, -4.0, 1.0)
    assert not _filter_allows(w, deck, diagonal)
    assert not _filter_allows(w, deck, post)
    assert not _filter_allows(w, diagonal, post)


def test_beams_without_a_shared_joint_may_collide():
    w = World()
    w.place_girder(-6.0, 3.0, -4.0, 3.0)
    w.place_girder(-6.0, 3.0, -4.0, 1.0)
    one = w.place_girder(-4.0, 3.0, -2.0, 1.0)
    other = w.place_girder(-4.0, 1.0, -2.0, 3.0)  # crosses `one` mid-span
    assert _filter_allows(w, one, other)


def test_intact_beams_follow_their_nodes():
    w = World()
    w.place_girder(-6.0, 3.0, -4.0, 3.0)
    gid = w.place_girder(-4.0, 3.0, -2.0, 3.0)
    for _ in range(20):
        w.step()
    (ax, ay), (bx, by) = w.structure.member_ends(gid)
    x, y = w.girder_position(gid)
    assert abs(x - (ax + bx) / 2) < 1e-6 and abs(y - (ay + by) / 2) < 1e-6


def test_train_weight_reaches_the_truss():
    from bridge_builder.truss import INVERTED_TRUSS

    w = World()
    for x1, y1, x2, y2, material in INVERTED_TRUSS:
        w.place_girder(x1, y1, x2, y2, material=material)
    for _ in range(int(2.0 / w.DT)):
        w.step()
    empty = w.structure.member_force(13)  # bottom chord (-2,1)-(0,1)
    w.spawn_train()
    while w.first_train_position()[0] < 1.0:
        w.step()
    loaded = w.structure.member_force(13)
    assert loaded > empty + 150.0  # the train pulls the bottom chord much harder


def test_grab_tool_pulls_a_bridge_node():
    w = World()
    w.place_girder(-6.0, 3.0, -4.0, 3.0)
    w.place_girder(-4.0, 3.0, -2.0, 3.0)
    w.place_girder(-2.0, 3.0, 0.0, 3.0)
    node = w.grab_node(-3.9, 3.1)
    assert node == (-4.0, 3.0)
    assert w.grab_node(-6.0, 3.0) is None  # anchors do not move
    w.drag_node(node, (-4.0, 1.0))
    for _ in range(30):
        w.step()
    assert w.structure.node_position(node)[1] < 2.5
    w.drag_node(None)
    assert w._drag is None
