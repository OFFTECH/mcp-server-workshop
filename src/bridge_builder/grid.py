"""Construction grid. Girders only join neighbouring nodes.

Nodes exist on and above the bank top (y=3) everywhere. Inside the gap
(strictly between the bank walls) they also exist below the deck, down to
GAP_FLOOR_Y, so an inverted truss can hang under the road. The wall faces at
x=-6 and x=6 are not buildable below the anchors.
"""

from __future__ import annotations

import math

GRID = 2.0
GRID_ORIGIN_X = 0.0
GRID_ORIGIN_Y = 3.0  # bank top
GAP_X = (-6.0, 6.0)  # bank wall faces; below-deck nodes are strictly inside
GAP_FLOOR_Y = -1.0  # lowest below-deck node
NEIGHBOURS = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
)


def grid_index(x: float, y: float) -> tuple[int, int]:
    ix = int(round((x - GRID_ORIGIN_X) / GRID))
    iy = int(round((y - GRID_ORIGIN_Y) / GRID))
    return ix, iy


def point_from_index(ix: int, iy: int) -> tuple[float, float]:
    return GRID_ORIGIN_X + ix * GRID, GRID_ORIGIN_Y + iy * GRID


def _in_gap(x: float) -> bool:
    return GAP_X[0] < x < GAP_X[1]


def node_allowed(x: float, y: float) -> bool:
    """True when a grid node may carry a joint: on/above the banks, or in the gap down to the floor."""
    if y >= GRID_ORIGIN_Y - 1e-6:
        return True
    return _in_gap(x) and y >= GAP_FLOOR_Y - 1e-6


def snap_point(x: float, y: float) -> tuple[float, float]:
    """Nearest grid node (may be a disallowed one; check node_allowed)."""
    return point_from_index(*grid_index(x, y))


def snap_mouse(x: float, y: float) -> tuple[float, float]:
    """Mouse-friendly snap: over the banks a click below the top lands on the top node,
    and nothing snaps below the gap floor."""
    ix, iy = grid_index(x, y)
    px, _py = point_from_index(ix, 0)
    if not _in_gap(px):
        iy = max(0, iy)
    iy = max(iy, grid_index(0.0, GAP_FLOOR_Y)[1])
    return point_from_index(ix, iy)


def is_valid_member(x1: float, y1: float, x2: float, y2: float) -> bool:
    i1 = grid_index(x1, y1)
    i2 = grid_index(x2, y2)
    dx, dy = abs(i1[0] - i2[0]), abs(i1[1] - i2[1])
    return (dx, dy) in {(1, 0), (0, 1), (1, 1)}


def snap_member(
    x1: float, y1: float, x2: float, y2: float
) -> tuple[float, float, float, float] | None:
    a = snap_point(x1, y1)
    b = snap_point(x2, y2)
    if not (node_allowed(*a) and node_allowed(*b)):
        return None
    if not is_valid_member(*a, *b):
        return None
    return (*a, *b)


def aim_member(
    x1: float, y1: float, mx: float, my: float
) -> tuple[float, float, float, float] | None:
    """Rubber-band: snap the start, pick the closest *allowed* neighbouring node to the mouse."""
    sx, sy = snap_point(x1, y1)
    i0 = grid_index(sx, sy)
    if math.hypot(mx - sx, my - sy) < GRID * 0.35:
        return None
    best: tuple[float, float] | None = None
    best_d = float("inf")
    for dx, dy in NEIGHBOURS:
        nx, ny = point_from_index(i0[0] + dx, i0[1] + dy)
        if not node_allowed(nx, ny):
            continue
        d = math.hypot(mx - nx, my - ny)
        if d < best_d:
            best_d = d
            best = (nx, ny)
    if best is None:
        return None
    return (sx, sy, best[0], best[1])


def iter_grid_points(
    x_min: float = -16.0, x_max: float = 16.0, y_max: float = 15.0
) -> list[tuple[float, float]]:
    """Every buildable node in view, including the below-deck nodes inside the gap."""
    ix0, _ = grid_index(x_min, GRID_ORIGIN_Y)
    ix1, iy1 = grid_index(x_max, y_max)
    iy0 = grid_index(0.0, GAP_FLOOR_Y)[1]
    points: list[tuple[float, float]] = []
    for iy in range(iy0, iy1 + 1):
        for ix in range(ix0, ix1 + 1):
            p = point_from_index(ix, iy)
            if node_allowed(*p):
                points.append(p)
    return points
