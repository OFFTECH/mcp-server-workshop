"""The bridge as a pin-jointed truss: point-mass nodes joined by axial springs. No Box2D.

Every beam end that lands on the same grid node shares that node, so the node
is a true pin: beams turn freely about it and carry only pull or push along
their length. Anchors are fixed nodes. Each beam is a stiff spring (EA / L) with
a little damping, and the whole truss is integrated with small substeps, so a
triangle stays rigid while a chain of links sags and pulls hard on its ends.

A beam breaks when its pull exceeds ``tension_limit`` or its push exceeds its
buckling limit, which falls with the square of the beam's length (Euler).
Loads from outside (the train's wheels) arrive as point loads on a beam and are
split between its two end nodes by the lever rule. A load can bring its own mass
along (a car resting on the deck): that mass rides on the nodes for the step, so
a light deck is not flung about by a heavy train (the "moving mass" model).
"""

from __future__ import annotations

import math

from bridge_builder.grid import GRID

Node = tuple[float, float]

GRAVITY_Y = -9.8
SUBSTEPS = 16
DAMPING_RATIO = 0.3  # axial dashpot in every beam, as a fraction of critical
AIR_DAMPING = 0.5  # 1/s on every node: lets a swinging mechanism come to rest
FALL_Y = -20.0  # a node this low has left the level; its beams are released
SETTLE_DAMPING = 20.0  # 1/s on every node while settling: swinging parts creep to rest
SETTLE_RAMP_SECONDS = 1.0  # gravity grows from 0 to full over this time: no overshoot
SETTLE_MAX_SECONDS = 4.0
SETTLE_SPEED = 1e-3  # m/s: at rest


def compression_limit(tension_limit: float, length: float) -> float:
    """Push a beam survives: its tension limit, cut by (GRID / length)^2 once it is long enough to buckle."""
    return tension_limit * min(1.0, (GRID / length) ** 2)


class _Node:
    __slots__ = (
        "x", "y", "vx", "vy", "mass", "extra_mass", "fixed", "load_x", "load_y", "fx", "fy", "members"
    )

    def __init__(self, x: float, y: float, fixed: bool) -> None:
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.mass = 0.0
        self.extra_mass = 0.0  # riding load's mass, for the next step only
        self.fixed = fixed
        self.load_x = self.load_y = 0.0
        self.fx = self.fy = 0.0
        self.members: set[int] = set()


class _Member:
    __slots__ = ("a", "b", "rest", "k", "c", "mass", "tension_limit", "compression_limit", "force")

    def __init__(
        self, a: _Node, b: _Node, k: float, mass: float, tension_limit: float, compression: float
    ) -> None:
        self.a, self.b = a, b
        self.rest = math.hypot(b.x - a.x, b.y - a.y)
        self.k = k
        self.c = 2.0 * DAMPING_RATIO * math.sqrt(k * mass / 2.0)
        self.mass = mass
        self.tension_limit = tension_limit
        self.compression_limit = compression
        self.force = 0.0  # elastic axial force, + pull / - push

    def load_fraction(self) -> float:
        if self.force >= 0.0:
            return self.force / self.tension_limit
        return -self.force / self.compression_limit


class Structure:
    def __init__(self, fixed: set[Node], gravity: float = GRAVITY_Y) -> None:
        self.fixed = set(fixed)
        self.gravity = gravity
        self._nodes: dict[Node, _Node] = {}
        self._members: dict[int, _Member] = {}
        self.peak_load = 0.0  # worst load fraction seen since construction or reset_peak()
        self._cut = False  # a beam was removed: some piece may hang from nothing
        self.air_damping = AIR_DAMPING
        self.gravity_scale = 1.0

    # --- building ---------------------------------------------------------

    def add_member(
        self,
        mid: int,
        a: Node,
        b: Node,
        stiffness: float,
        mass: float,
        tension_limit: float = math.inf,
        compression: float | None = None,
    ) -> None:
        na, nb = self._node(a), self._node(b)
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if compression is None:
            compression = compression_limit(tension_limit, length)
        self._members[mid] = _Member(na, nb, stiffness, mass, tension_limit, compression)
        for n in (na, nb):
            n.members.add(mid)
            n.mass += mass / 2.0

    def remove_member(self, mid: int) -> None:
        m = self._members.pop(mid, None)
        if m is None:
            return
        for n in (m.a, m.b):
            n.members.discard(mid)
            n.mass -= m.mass / 2.0
        for key in [k for k, n in self._nodes.items() if not n.members]:
            del self._nodes[key]
        self._cut = True

    def _node(self, key: Node) -> _Node:
        n = self._nodes.get(key)
        if n is None:
            n = self._nodes[key] = _Node(key[0], key[1], key in self.fixed)
        return n

    # --- queries ----------------------------------------------------------

    def has_member(self, mid: int) -> bool:
        return mid in self._members

    def has_node(self, key: Node) -> bool:
        return key in self._nodes

    def member_ids(self) -> list[int]:
        return list(self._members)

    def node_keys(self) -> list[Node]:
        return list(self._nodes)

    def node_degree(self, key: Node) -> int:
        n = self._nodes.get(key)
        return 0 if n is None else len(n.members)

    def node_position(self, key: Node) -> tuple[float, float]:
        n = self._nodes[key]
        return (n.x, n.y)

    def node_velocity(self, key: Node) -> tuple[float, float]:
        n = self._nodes[key]
        return (n.vx, n.vy)

    def node_load(self, key: Node) -> tuple[float, float]:
        n = self._nodes[key]
        return (n.load_x, n.load_y)

    def node_extra_mass(self, key: Node) -> float:
        return self._nodes[key].extra_mass

    def member_ends(self, mid: int) -> tuple[tuple[float, float], tuple[float, float]]:
        m = self._members[mid]
        return (m.a.x, m.a.y), (m.b.x, m.b.y)

    def member_velocities(self, mid: int) -> tuple[tuple[float, float], tuple[float, float]]:
        m = self._members[mid]
        return (m.a.vx, m.a.vy), (m.b.vx, m.b.vy)

    def member_force(self, mid: int) -> float:
        """Axial force in newtons: positive = pull (tension), negative = push (compression)."""
        return self._members[mid].force

    def load_fraction(self, mid: int) -> float:
        """Axial force as a fraction of the limit it is working against (1.0 = breaks)."""
        return self._members[mid].load_fraction()

    # --- loads and time ---------------------------------------------------

    def add_node_load(self, key: Node, fx: float, fy: float) -> None:
        """Add a force to a node for the next step only."""
        n = self._nodes.get(key)
        if n is not None:
            n.load_x += fx
            n.load_y += fy

    def apply_load(
        self, mid: int, x: float, y: float, fx: float, fy: float, mass: float = 0.0
    ) -> None:
        """A point load at (x, y) on beam ``mid`` for the next step, split to its ends by the lever rule.

        ``mass`` is what the load carries with it (a car's supported mass); it is split the same way.
        """
        m = self._members.get(mid)
        if m is None:
            return
        dx, dy = m.b.x - m.a.x, m.b.y - m.a.y
        t = ((x - m.a.x) * dx + (y - m.a.y) * dy) / (dx * dx + dy * dy)
        t = min(1.0, max(0.0, t))
        m.a.load_x += (1.0 - t) * fx
        m.a.load_y += (1.0 - t) * fy
        m.b.load_x += t * fx
        m.b.load_y += t * fy
        m.a.extra_mass += (1.0 - t) * mass
        m.b.extra_mass += t * mass

    def reset_peak(self) -> None:
        self.peak_load = 0.0

    def step(self, dt: float) -> list[int]:
        """Advance ``dt`` seconds. Returns the beams that left the structure (broke or fell away)."""
        h = dt / SUBSTEPS
        keep = 1.0 - self.air_damping * h
        g = self.gravity * self.gravity_scale
        released = self._release_unanchored()
        for _ in range(SUBSTEPS):
            nodes = self._nodes.values()
            for n in nodes:
                n.fx = n.load_x
                n.fy = n.load_y + n.mass * g
            for m in self._members.values():
                a, b = m.a, m.b
                dx, dy = b.x - a.x, b.y - a.y
                length = math.hypot(dx, dy) or 1e-9
                ux, uy = dx / length, dy / length
                m.force = m.k * (length - m.rest)
                pull = m.force + m.c * ((b.vx - a.vx) * ux + (b.vy - a.vy) * uy)
                a.fx += pull * ux
                a.fy += pull * uy
                b.fx -= pull * ux
                b.fy -= pull * uy
            for n in nodes:
                if n.fixed or n.mass <= 0.0:
                    continue
                inertia = n.mass + n.extra_mass
                n.vx = (n.vx + n.fx / inertia * h) * keep
                n.vy = (n.vy + n.fy / inertia * h) * keep
                n.x += n.vx * h
                n.y += n.vy * h
            gone: list[int] = []
            for mid, m in self._members.items():
                load = m.load_fraction()
                if load > self.peak_load:
                    self.peak_load = load
                if load > 1.0 or m.a.y < FALL_Y or m.b.y < FALL_Y:
                    gone.append(mid)
            for mid in gone:
                self.remove_member(mid)
            released += gone
            if gone:
                released += self._release_unanchored()
        for n in self._nodes.values():
            n.load_x = n.load_y = n.extra_mass = 0.0
        return released

    def settle(self, dt: float = 1.0 / 60.0) -> list[int]:
        """Let the bridge take up its own weight slowly, as it would while being built.

        Gravity is ramped up over SETTLE_RAMP_SECONDS with heavy damping, then held until
        every node is at rest (or SETTLE_MAX_SECONDS pass), so the dead load arrives
        without the overshoot of a sudden release. Beams can still break. Returns the
        beams that left the structure.
        """
        released: list[int] = []
        ramp = max(1, int(SETTLE_RAMP_SECONDS / dt))
        self.air_damping = SETTLE_DAMPING
        try:
            for i in range(int(SETTLE_MAX_SECONDS / dt)):
                self.gravity_scale = min(1.0, (i + 1) / ramp)
                released += self.step(dt)
                at_rest = all(math.hypot(n.vx, n.vy) < SETTLE_SPEED for n in self._nodes.values())
                if i >= ramp and at_rest:
                    break
        finally:
            self.air_damping = AIR_DAMPING
            self.gravity_scale = 1.0
        return released

    def _release_unanchored(self) -> list[int]:
        """After a cut, remove every piece that no longer reaches a fixed node; it is debris now."""
        if not self._cut:
            return []
        self._cut = False
        held: set[int] = set()
        frontier = [id(n) for n in self._nodes.values() if n.fixed]
        seen = set(frontier)
        by_id = {id(n): n for n in self._nodes.values()}
        while frontier:
            n = by_id[frontier.pop()]
            for mid in n.members:
                held.add(mid)
                m = self._members[mid]
                for other in (m.a, m.b):
                    if id(other) not in seen:
                        seen.add(id(other))
                        frontier.append(id(other))
        loose = [mid for mid in self._members if mid not in held]
        for mid in loose:
            self.remove_member(mid)
        self._cut = False
        return loose
