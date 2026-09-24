from bridge_builder.grid import (
    GRID,
    aim_member,
    is_valid_member,
    iter_grid_points,
    node_allowed,
    snap_member,
    snap_mouse,
    snap_point,
)


def test_snap_point_to_two_metre_grid():
    assert snap_point(-5.7, 3.4) == (-6.0, 3.0)
    assert snap_point(1.1, 4.2) == (2.0, 5.0)


def test_mouse_snap_on_bank_does_not_go_below_bank_top():
    assert snap_mouse(-10.0, 0.5) == (-10.0, 3.0)
    assert snap_mouse(-6.0, 1.2) == (-6.0, 3.0)
    assert snap_mouse(0.0, -5.0) == (0.0, -1.0)
    assert snap_point(-10.0, 0.5) == (-10.0, 1.0)


def test_snap_in_gap_goes_below_deck():
    assert snap_point(0.0, 0.5) == (0.0, 1.0)
    assert snap_point(-3.9, -0.8) == (-4.0, -1.0)


def test_only_neighbour_members_are_valid():
    assert is_valid_member(-6.0, 3.0, -4.0, 3.0)
    assert is_valid_member(-6.0, 3.0, -4.0, 5.0)
    assert not is_valid_member(-6.0, 3.0, -2.0, 3.0)
    assert not is_valid_member(-6.0, 3.0, -6.0, 3.0)


def test_snap_member_snaps_both_ends_to_neighbours():
    placed = snap_member(-5.8, 3.2, -4.1, 3.1)
    assert placed == (-6.0, 3.0, -4.0, 3.0)
    assert abs((placed[2] - placed[0]) ** 2 + (placed[3] - placed[1]) ** 2 - GRID**2) < 1e-6


def test_snap_member_rejects_two_cell_span():
    assert snap_member(-6.0, 3.0, -2.0, 3.0) is None


def test_aim_member_picks_neighbour_not_freehand_length():
    aimed = aim_member(-6.0, 3.0, -1.0, 3.0)
    assert aimed == (-6.0, 3.0, -4.0, 3.0)
    assert aim_member(-6.0, 3.0, -6.1, 3.0) is None


# --- below-deck nodes in the gap ------------------------------------------


def test_nodes_below_deck_only_strictly_inside_gap():
    assert node_allowed(0.0, 1.0)
    assert node_allowed(-4.0, 1.0)
    assert node_allowed(4.0, -1.0)
    assert not node_allowed(-6.0, 1.0)  # wall face
    assert not node_allowed(6.0, 1.0)
    assert not node_allowed(-8.0, 1.0)  # inside the bank
    assert not node_allowed(0.0, -3.0)  # below the gap floor
    assert node_allowed(-8.0, 3.0)
    assert node_allowed(0.0, 9.0)


def test_snap_member_rejects_endpoint_in_wall():
    assert snap_member(-6.0, 3.0, -4.0, 1.0) == (-6.0, 3.0, -4.0, 1.0)
    assert snap_member(-6.0, 3.0, -8.0, 1.0) is None
    assert snap_member(-6.0, 3.0, -6.0, 1.0) is None
    assert snap_member(-4.0, 1.0, -6.0, 1.0) is None


def test_aim_member_skips_disallowed_neighbours():
    # from the left anchor, aiming down-left into the bank falls back to a legal neighbour
    aimed = aim_member(-6.0, 3.0, -7.0, 1.6)
    assert aimed is not None
    assert node_allowed(aimed[2], aimed[3])
    assert aim_member(-6.0, 3.0, -4.2, 1.1) == (-6.0, 3.0, -4.0, 1.0)


def test_grid_points_include_gap_below_deck():
    pts = set(iter_grid_points())
    assert (0.0, 1.0) in pts
    assert (-4.0, -1.0) in pts
    assert (-6.0, 1.0) not in pts
    assert (-8.0, 1.0) not in pts
