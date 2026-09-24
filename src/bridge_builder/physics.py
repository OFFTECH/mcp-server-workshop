"""The level: Box2D for the banks, the train and what the player sees; ``Structure`` for the bridge.

The bridge's strength comes from ``structure.Structure``, a pin-jointed truss.
Each beam also has a Box2D body so the train can roll on it and the view can
draw it. While the beam is intact that body is kinematic and follows its two
nodes; the train's contact forces on it go back into the truss as loads. A beam
that breaks becomes an ordinary falling body (debris). No pygame.
"""

from __future__ import annotations

import math
from typing import Any

from Box2D import (
    b2_dynamicBody,
    b2AABB,
    b2CircleShape,
    b2ContactFilter,
    b2DistanceJointDef,
    b2Filter,
    b2PolygonShape,
    b2QueryCallback,
    b2RevoluteJointDef,
    b2Vec2,
    b2World,
)

from bridge_builder.grid import point_from_index, snap_member, snap_point
from bridge_builder.materials import DEFAULT_MATERIAL, MATERIALS
from bridge_builder.structure import Structure, compression_limit

DT = 1.0 / 60.0
GIRDER_THICKNESS = 0.30
GIRDER_OVERLAP = 0.12
# Axial stiffness EA of a steel beam, in newtons: a 2 m steel beam is a 1e5 N/m spring.
AXIAL_STIFFNESS = 2.0e5
# Time constant (s) of the low-pass on the train's contact loads: its suspension.
WHEEL_SUSPENSION = 0.05
# Grab tool: a capped spring pulls the grabbed bridge node toward the mouse.
DRAG_STIFFNESS = 2000.0
DRAG_MAX_FORCE = 3000.0
CAT_GROUND = 0x0001
CAT_DECK = 0x0002
CAT_BRACE = 0x0004
CAT_TRAIN = 0x0008
BANK_TOP_Y = 3.0  # node line of the anchors and the deck
# Road surface: the bank top is flush with the top face of a deck beam, whose box is
# centred on the node line, so wheels roll from bank to deck without hitting a step.
ROAD_Y = BANK_TOP_Y + GIRDER_THICKNESS / 2.0
GAP = (-6.0, 6.0)
GRAVITY = (0.0, -9.8)
VEL_ITERS = 8
POS_ITERS = 3

WHEEL_RADIUS = 0.35
CHASSIS_SIZE = (2.0, 0.8)
CHASSIS_DENSITY = 4.0
WHEEL_MOTOR_SPEED = -12.0
WHEEL_MOTOR_TORQUE = 80.0
LEAD_CAR_X = -8.2
CAR_SPACING = 2.2
WHEEL_Y = ROAD_Y + WHEEL_RADIUS
CHASSIS_Y = WHEEL_Y + 0.45

Node = tuple[float, float]


class _PointQuery(b2QueryCallback):
    def __init__(self, point: b2Vec2, require_point: bool) -> None:
        super().__init__()
        self.point = point
        self.require_point = require_point
        self.fixtures: list[Any] = []

    def ReportFixture(self, fixture: Any) -> bool:
        if not self.require_point or fixture.TestPoint(self.point):
            self.fixtures.append(fixture)
        return True


class _SharedJointFilter(b2ContactFilter):
    """Beams that share an end node overlap there by design; they must not push each other apart."""

    def __init__(self, girder_ends: dict[int, tuple[Node, Node]]) -> None:
        super().__init__()
        self.girder_ends = girder_ends

    def ShouldCollide(self, fixture_a: Any, fixture_b: Any) -> bool:
        if not super().ShouldCollide(fixture_a, fixture_b):
            return False
        a = fixture_a.body.userData or {}
        b = fixture_b.body.userData or {}
        if a.get("kind") == b.get("kind") == "girder":
            ends_a = self.girder_ends.get(a["id"], ())
            ends_b = self.girder_ends.get(b["id"], ())
            if any(node in ends_b for node in ends_a):
                return False
        return True


class World:
    DT = DT

    def __init__(self, break_force: float = math.inf) -> None:
        # pull that breaks a beam of strength 1.0 (steel); math.inf = unbreakable
        self.break_force = break_force
        self._next_id = 1
        self._girders: dict[int, Any] = {}
        self._girder_lengths: dict[int, float] = {}
        self._girder_ends: dict[int, tuple[Node, Node]] = {}
        self._girder_materials: dict[int, str] = {}
        self._contact_filter = _SharedJointFilter(self._girder_ends)
        self.world = self._new_world()
        self._train_parts: list[Any] = []
        self.first_train: Any | None = None
        self.anchors: set[Node] = set()
        self._nodes: set[Node] = set()
        self._drag: tuple[Node, tuple[float, float]] | None = None
        # smoothed contact load per beam: (x, y, fx, fy)
        self._wheel_loads: dict[int, tuple[float, float, float, float]] = {}
        self._build_banks()
        self._build_anchors()
        self.structure = Structure(fixed=self.anchors)

    def _new_world(self) -> Any:
        world = b2World(gravity=GRAVITY, doSleep=True)
        world.contactFilter = self._contact_filter
        return world

    def _build_banks(self) -> None:
        left = self.world.CreateStaticBody(
            position=(-10.0, ROAD_Y / 2.0),
            shapes=b2PolygonShape(box=(4.0, ROAD_Y / 2.0)),
        )
        left.userData = {"kind": "bank", "name": "left"}
        self._set_filter(left, CAT_GROUND, CAT_GROUND | CAT_DECK | CAT_BRACE | CAT_TRAIN)
        right = self.world.CreateStaticBody(
            position=(10.0, ROAD_Y / 2.0),
            shapes=b2PolygonShape(box=(4.0, ROAD_Y / 2.0)),
        )
        right.userData = {"kind": "bank", "name": "right"}
        self._set_filter(right, CAT_GROUND, CAT_GROUND | CAT_DECK | CAT_BRACE | CAT_TRAIN)
        self.left_bank = left
        self.right_bank = right

    def _build_anchors(self) -> None:
        self.anchors = set()
        for ix in range(-7, -2):
            self.anchors.add(point_from_index(ix, 0))
        for ix in range(3, 8):
            self.anchors.add(point_from_index(ix, 0))
        self._nodes = set(self.anchors)

    def has_node(self, x: float, y: float) -> bool:
        return snap_point(x, y) in self._nodes

    def iter_nodes(self) -> list[tuple[Node, tuple[float, float]]]:
        """Every node a beam may start from, as (grid node, where it is now): bridge nodes move as the truss flexes."""
        out = []
        for node in self._nodes:
            now = self.structure.node_position(node) if self.structure.has_node(node) else node
            out.append((node, now))
        return out

    def reset(self) -> None:
        self.world = self._new_world()
        self._next_id = 1
        self._girders.clear()
        self._girder_lengths.clear()
        self._girder_ends.clear()
        self._girder_materials.clear()
        self._train_parts.clear()
        self.first_train = None
        self._drag = None
        self._wheel_loads.clear()
        self._build_banks()
        self._build_anchors()
        self.structure = Structure(fixed=self.anchors)

    def _alloc_id(self) -> int:
        n = self._next_id
        self._next_id += 1
        return n

    def _set_filter(self, body: Any, category: int, mask: int) -> None:
        filt = b2Filter(categoryBits=category, maskBits=mask)
        for fixture in body.fixtures:
            fixture.filterData = filt

    # --- building -------------------------------------------------------------

    def place_girder(
        self, x1: float, y1: float, x2: float, y2: float, material: str = DEFAULT_MATERIAL
    ) -> int | None:
        grade = MATERIALS[material]
        snapped = snap_member(x1, y1, x2, y2)
        if snapped is None:
            return None
        x1, y1, x2, y2 = snapped
        a = (x1, y1)
        b = (x2, y2)
        if a not in self._nodes and b not in self._nodes:
            return None
        length = math.hypot(x2 - x1, y2 - y1)
        angle = math.atan2(y2 - y1, x2 - x1)
        body = self.world.CreateKinematicBody(position=((x1 + x2) / 2.0, (y1 + y2) / 2.0), angle=angle)
        body.CreatePolygonFixture(
            box=(length / 2.0 + GIRDER_OVERLAP / 2.0, GIRDER_THICKNESS / 2.0),
            density=grade.density,
            friction=0.5,
            restitution=0.05,
        )
        if abs(math.sin(angle)) < 0.35:
            self._set_filter(body, CAT_DECK, CAT_GROUND | CAT_DECK | CAT_BRACE | CAT_TRAIN)
        else:
            self._set_filter(body, CAT_BRACE, CAT_GROUND | CAT_DECK | CAT_BRACE)
        gid = self._alloc_id()
        body.userData = {"kind": "girder", "id": gid, "material": grade.name}
        self._girders[gid] = body
        self._girder_lengths[gid] = length
        self._girder_ends[gid] = (a, b)
        self._girder_materials[gid] = grade.name
        self._nodes.add(a)
        self._nodes.add(b)
        tension = self.break_force * grade.strength
        self.structure.add_member(
            gid,
            a,
            b,
            stiffness=AXIAL_STIFFNESS * grade.stiffness / length,
            mass=grade.density * (length + GIRDER_OVERLAP) * GIRDER_THICKNESS,
            tension_limit=tension,
            compression=compression_limit(tension, length),
        )
        return gid

    def girder_count(self) -> int:
        return len(self._girders)

    def girder_length(self, girder_id: int) -> float:
        return self._girder_lengths[girder_id]

    def girder_material(self, girder_id: int) -> str:
        return self._girder_materials[girder_id]

    def girder_position(self, girder_id: int) -> tuple[float, float]:
        p = self._girders[girder_id].position
        return (float(p.x), float(p.y))

    def is_intact(self, girder_id: int) -> bool:
        """True while the beam is part of the bridge; False once it has broken off."""
        return self.structure.has_member(girder_id)

    def iter_beams(self) -> list[int]:
        """Ids of the intact beams."""
        return self.structure.member_ids()

    def beam_load(self, girder_id: int) -> float:
        """Axial force in an intact beam as a fraction of its limit (1.0 = it breaks)."""
        return self.structure.load_fraction(girder_id)

    def beam_force(self, girder_id: int) -> float:
        """Axial force in an intact beam, newtons: + pull, - push."""
        return self.structure.member_force(girder_id)

    def _is_joint(self, node: Node) -> bool:
        degree = self.structure.node_degree(node)
        return degree >= 2 or (degree >= 1 and node in self.anchors)

    def add_joint(self, x: float, y: float) -> int | None:
        """Beams that end on the same node are always pinned there; this only reports the joint.

        Returns an id for the joint at (x, y) (an anchor holding a beam, or two or more
        beams meeting), or None when there is none.
        """
        node = snap_point(x, y)
        if not self._is_joint(node):
            return None
        return sorted(self.structure.node_keys()).index(node) + 1

    def joint_count(self) -> int:
        return sum(1 for node in self.structure.node_keys() if self._is_joint(node))

    def bodies_at(
        self, x: float, y: float, radius: float = 0.15, require_point: bool = True
    ) -> list[Any]:
        point = b2Vec2(x, y)
        cb = _PointQuery(point, require_point)
        pad = max(radius, 0.05)
        aabb = b2AABB(lowerBound=point - (pad, pad), upperBound=point + (pad, pad))
        self.world.QueryAABB(cb, aabb)
        seen: list[Any] = []
        ids: set[int] = set()
        for fixture in cb.fixtures:
            body = fixture.body
            bid = id(body)
            if bid not in ids:
                ids.add(bid)
                seen.append(body)
        return seen

    def girder_at(self, x: float, y: float) -> Any | None:
        """The girder body whose shape contains the exact point (x, y), or None."""
        for body in self.bodies_at(x, y):
            if (body.userData or {}).get("kind") == "girder":
                return body
        return None

    def destroy_at(self, x: float, y: float, snap: bool = True) -> dict[str, Any]:
        if snap:
            x, y = snap_point(x, y)
        target = None
        for body in self.bodies_at(x, y):
            if (body.userData or {}).get("kind") in ("girder", "chassis", "wheel"):
                target = body
                break
        if target is None:
            return {"destroyed": False, "girder_refund": 0, "girder_id": None}
        data = target.userData or {}
        girder_refund = 0
        girder_id: int | None = None
        if data.get("kind") == "girder":
            gid = data.get("id")
            girder_id = gid
            self.structure.remove_member(gid)
            self._girders.pop(gid, None)
            self._girder_lengths.pop(gid, None)
            self._girder_ends.pop(gid, None)
            self._girder_materials.pop(gid, None)
            girder_refund = 1
            self._nodes = set(self.anchors)
            for ends in self._girder_ends.values():
                self._nodes.add(ends[0])
                self._nodes.add(ends[1])
        if target in self._train_parts:
            self._train_parts.remove(target)
        if target is self.first_train:
            self.first_train = None
        self.world.DestroyBody(target)
        return {"destroyed": True, "girder_refund": girder_refund, "girder_id": girder_id}

    # --- simulation -----------------------------------------------------------

    @property
    def peak_load(self) -> float:
        """Worst beam load since the last reset_peak, as a fraction of that beam's limit (1.0+ = it broke)."""
        return self.structure.peak_load

    def reset_peak(self) -> None:
        self.structure.reset_peak()

    def settle(self) -> list[int]:
        """Let the bridge take up its own weight before a run (see Structure.settle)."""
        released = self.structure.settle(DT)
        for gid in released:
            self._release(gid)
        self._snap_to_nodes()
        return released

    def step(self, dt: float = DT) -> list[int]:
        """Advance the truss, then Box2D. Returns the beams that broke off this step."""
        self._apply_drag()
        released = self.structure.step(dt)
        for gid in released:
            self._release(gid)
        self._follow_nodes(dt)
        self.world.Step(dt, VEL_ITERS, POS_ITERS)
        self.world.ClearForces()
        self._snap_to_nodes()
        self._collect_contact_loads(dt)
        return released

    def _beam_pose(self, gid: int) -> tuple[float, float, float]:
        (ax, ay), (bx, by) = self.structure.member_ends(gid)
        return (ax + bx) / 2.0, (ay + by) / 2.0, math.atan2(by - ay, bx - ax)

    def _follow_nodes(self, dt: float) -> None:
        """Give each intact beam body the velocity that carries it to its nodes' new pose over ``dt``."""
        for gid in self.structure.member_ids():
            body = self._girders[gid]
            cx, cy, angle = self._beam_pose(gid)
            turn = (angle - body.angle + math.pi) % (2.0 * math.pi) - math.pi
            body.linearVelocity = ((cx - body.position.x) / dt, (cy - body.position.y) / dt)
            body.angularVelocity = turn / dt

    def _snap_to_nodes(self) -> None:
        for gid in self.structure.member_ids():
            cx, cy, angle = self._beam_pose(gid)
            self._girders[gid].transform = ((cx, cy), angle)

    def _release(self, gid: int) -> None:
        """A beam left the truss: its body becomes falling debris, moving as it was."""
        body = self._girders.get(gid)
        if body is None:
            return
        v = b2Vec2(body.linearVelocity)
        w = body.angularVelocity
        body.type = b2_dynamicBody
        body.linearVelocity = v
        body.angularVelocity = w
        body.awake = True

    def _collect_contact_loads(self, dt: float) -> None:
        """Contact forces on intact beams (wheels, debris) become point loads on the truss next step.

        A car is ten times heavier than a beam's share of a node, so the raw contact force
        chatters (the light deck is knocked away and slams back each frame). The loads are
        low-passed over WHEEL_SUSPENSION seconds, as a train's springs would, before the
        truss sees them; this keeps beam forces at what statics predicts.
        """
        raw: dict[int, list[float]] = {}  # gid -> [sum fx, sum fy, sum |f| x, sum |f| y, sum |f|]

        def add(gid: int, px: float, py: float, fx: float, fy: float) -> None:
            acc = raw.setdefault(gid, [0.0, 0.0, 0.0, 0.0, 0.0])
            weight = math.hypot(fx, fy)
            acc[0] += fx
            acc[1] += fy
            acc[2] += weight * px
            acc[3] += weight * py
            acc[4] += weight

        for contact in self.world.contacts:
            if not contact.touching:
                continue
            gid_a = self._intact_id(contact.fixtureA.body)
            gid_b = self._intact_id(contact.fixtureB.body)
            if gid_a is None and gid_b is None:
                continue
            manifold = contact.manifold
            world_manifold = contact.worldManifold
            nx, ny = world_manifold.normal
            tx, ty = ny, -nx  # Box2D's tangent: cross(normal, 1)
            for i in range(manifold.pointCount):
                point = manifold.points[i]
                px, py = world_manifold.points[i]
                # the contact solver pushes body B by +P and body A by -P
                fx = (nx * point.normalImpulse + tx * point.tangentImpulse) / dt
                fy = (ny * point.normalImpulse + ty * point.tangentImpulse) / dt
                if gid_a is not None:
                    add(gid_a, px, py, -fx, -fy)
                if gid_b is not None:
                    add(gid_b, px, py, fx, fy)
        blend = dt / (WHEEL_SUSPENSION + dt)
        for gid in set(raw) | set(self._wheel_loads):
            old = self._wheel_loads.get(gid)
            new = raw.get(gid)
            ofx, ofy = (old[2], old[3]) if old else (0.0, 0.0)
            nfx, nfy = (new[0], new[1]) if new else (0.0, 0.0)
            fx, fy = ofx + blend * (nfx - ofx), ofy + blend * (nfy - ofy)
            if new and new[4] > 0.0:
                px, py = new[2] / new[4], new[3] / new[4]
            elif old:
                px, py = old[0], old[1]
            else:
                continue
            if not self.structure.has_member(gid) or math.hypot(fx, fy) < 0.5:
                self._wheel_loads.pop(gid, None)
                continue
            self._wheel_loads[gid] = (px, py, fx, fy)
            # the weight a wheel puts on the beam is mass riding on it: fy = -m g
            riding = max(0.0, fy / GRAVITY[1])
            self.structure.apply_load(gid, px, py, fx, fy, mass=riding)

    def _intact_id(self, body: Any) -> int | None:
        data = body.userData or {}
        if data.get("kind") != "girder":
            return None
        gid = data.get("id")
        return gid if self.structure.has_member(gid) else None

    # --- grab tool ------------------------------------------------------------

    def grab_node(self, x: float, y: float, radius: float = 0.6) -> Node | None:
        """The free bridge node nearest (x, y) within ``radius``, to pull with ``drag_node``."""
        best, best_d = None, radius
        for node in self.structure.node_keys():
            if node in self.anchors:
                continue
            nx, ny = self.structure.node_position(node)
            d = math.hypot(nx - x, ny - y)
            if d < best_d:
                best, best_d = node, d
        return best

    def drag_node(self, node: Node | None, target: tuple[float, float] | None = None) -> None:
        """Pull ``node`` toward ``target`` with a capped spring every step; None lets go."""
        self._drag = None if node is None or target is None else (node, target)

    def _apply_drag(self) -> None:
        if self._drag is None:
            return
        node, (tx, ty) = self._drag
        if not self.structure.has_node(node):
            self._drag = None
            return
        x, y = self.structure.node_position(node)
        fx, fy = DRAG_STIFFNESS * (tx - x), DRAG_STIFFNESS * (ty - y)
        scale = min(1.0, DRAG_MAX_FORCE / max(math.hypot(fx, fy), 1e-9))
        self.structure.add_node_load(node, fx * scale, fy * scale)

    # --- train ----------------------------------------------------------------

    def spawn_train(self, force: bool = False) -> bool:
        if self.first_train is not None and not force:
            return False
        if force:
            self._destroy_train()
        self._train_parts = []
        chassis_list: list[Any] = []
        for i in range(3):
            cx = LEAD_CAR_X - i * CAR_SPACING
            chassis = self.world.CreateDynamicBody(position=(cx, CHASSIS_Y))
            chassis.CreatePolygonFixture(
                box=(CHASSIS_SIZE[0] / 2.0, CHASSIS_SIZE[1] / 2.0),
                density=CHASSIS_DENSITY,
                friction=0.3,
                restitution=0.05,
            )
            chassis.userData = {"kind": "chassis", "index": i}
            self._set_filter(chassis, CAT_TRAIN, CAT_GROUND | CAT_DECK | CAT_TRAIN)
            self._train_parts.append(chassis)
            chassis_list.append(chassis)
            for side in (-0.7, 0.7):
                wx, wy = cx + side, WHEEL_Y
                wheel = self.world.CreateDynamicBody(position=(wx, wy))
                wheel.bullet = True
                wheel.CreateCircleFixture(
                    shape=b2CircleShape(radius=WHEEL_RADIUS),
                    density=CHASSIS_DENSITY,
                    friction=1.2,
                    restitution=0.1,
                )
                wheel.userData = {"kind": "wheel"}
                self._set_filter(wheel, CAT_TRAIN, CAT_GROUND | CAT_DECK | CAT_TRAIN)
                self._train_parts.append(wheel)
                jdef = b2RevoluteJointDef()
                jdef.Initialize(chassis, wheel, b2Vec2(wx, wy))
                jdef.enableMotor = True
                jdef.motorSpeed = WHEEL_MOTOR_SPEED
                jdef.maxMotorTorque = WHEEL_MOTOR_TORQUE
                motor = self.world.CreateJoint(jdef)
                motor.userData = {"kind": "motor"}
        self.first_train = chassis_list[0]
        for i in range(len(chassis_list) - 1):
            back = chassis_list[i + 1]
            front = chassis_list[i]
            ddef = b2DistanceJointDef()
            ddef.Initialize(
                back,
                front,
                back.GetWorldPoint((-0.95, 0.0)),
                front.GetWorldPoint((0.95, 0.0)),
            )
            ddef.collideConnected = False
            coupler = self.world.CreateJoint(ddef)
            coupler.userData = {"kind": "coupler"}
        return True

    def _destroy_train(self) -> None:
        for body in list(self._train_parts):
            try:
                self.world.DestroyBody(body)
            except Exception:
                pass
        self._train_parts.clear()
        self.first_train = None

    def first_train_position(self) -> tuple[float, float] | None:
        if self.first_train is None:
            return None
        p = self.first_train.position
        return (float(p.x), float(p.y))

    def iter_bodies(self) -> list[Any]:
        return list(self.world.bodies)
