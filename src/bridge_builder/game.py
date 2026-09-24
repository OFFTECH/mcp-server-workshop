"""Rules: cost, pause, peak beam load, win/lose. Owns a physics.World."""

from __future__ import annotations

from typing import Any

from bridge_builder.materials import DEFAULT_MATERIAL, MATERIAL_ORDER, MATERIALS, get_material
from bridge_builder.grid import GRID
from bridge_builder.physics import BANK_TOP_Y, DT, GAP, World

GIRDER_COST = MATERIALS[DEFAULT_MATERIAL].cost
BUDGET = 30000
# Pull (N) that breaks a steel beam; other grades scale it by their strength.
BREAK_FORCE = 950.0
WIN_X = 6.0
WIN_Y = 2.0
LOSE_Y = 0.0


class Game:
    def __init__(self, break_force: float = BREAK_FORCE, budget: int = BUDGET) -> None:
        self.break_force = break_force
        self.budget = budget
        self.world = World(break_force=break_force)
        self.paused = True
        self.cost = 0
        self._girder_costs: dict[int, int] = {}
        # the design, in placement order: what a rerun rebuilds (original game: every test starts undamaged)
        self._design: dict[int, tuple[float, float, float, float, str]] = {}
        # worst beam load this run, as a fraction of that beam's limit (1.0 = it broke)
        self.peak_load = 0.0
        self._outcome: str = "absent"
        self.error: str | None = None

    def remaining(self) -> int:
        return self.budget - self.cost

    def score(self) -> int | None:
        if self._outcome == "win":
            return self.remaining()
        if self._outcome == "lose":
            return 0
        return None

    def place_girder(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        material: str | None = None,
    ) -> dict[str, Any]:
        grade = get_material(material)
        if grade is None:
            return {
                "ok": False,
                "error": f"unknown material {material!r}; choose one of {MATERIAL_ORDER}",
            }
        if self.cost + grade.cost > self.budget:
            return {
                "ok": False,
                "error": (
                    f"over budget: {grade.name} beam costs {grade.cost}, "
                    f"{self.remaining()} remaining of {self.budget}"
                ),
            }
        gid = self.world.place_girder(x1, y1, x2, y2, material=grade.name)
        if gid is None:
            return {
                "ok": False,
                "error": (
                    "beams join neighbouring 2 m nodes and must start from an "
                    "existing node (red anchors on the banks, or a joint you already built)"
                ),
            }
        self.cost += grade.cost
        self._girder_costs[gid] = grade.cost
        self._design[gid] = (x1, y1, x2, y2, grade.name)
        return {
            "ok": True,
            "id": gid,
            "material": grade.name,
            "cost": self.cost,
            "length": self.world.girder_length(gid),
        }

    def place_girders(self, beams: list[dict[str, Any]], reset: bool = False) -> dict[str, Any]:
        """Place ``beams`` in order, each as ``place_girder`` would; ``reset`` clears the level first.

        A beam may start at a node an earlier beam in the list created. Stops at the
        first beam that fails and reports it; the beams before it stay built.
        """
        if reset:
            self.reset()
        placed = 0
        for index, beam in enumerate(beams):
            out = self.place_girder(
                float(beam["x1"]),
                float(beam["y1"]),
                float(beam["x2"]),
                float(beam["y2"]),
                material=beam.get("material"),
            )
            if not out["ok"]:
                return {
                    "ok": False,
                    "error": f"beam {index} failed: {out['error']}",
                    "placed": placed,
                    "failed": {"index": index, "beam": beam},
                    "cost": self.cost,
                }
            placed += 1
        return {"ok": True, "placed": placed, "cost": self.cost, "girders": self.world.girder_count()}

    def add_joint(self, x: float, y: float) -> dict[str, Any]:
        jid = self.world.add_joint(x, y)
        if jid is None:
            return {"ok": False, "error": f"no joint at ({x}, {y})"}
        return {"ok": True, "id": jid, "cost": self.cost}

    def destroy_at(self, x: float, y: float, snap: bool = True) -> dict[str, Any]:
        """Remove the beam at (x, y). ``snap=False`` hit-tests the exact point (mouse on a beam)."""
        result = self.world.destroy_at(x, y, snap=snap)
        if not result["destroyed"]:
            return {"ok": False, "error": "nothing to destroy"}
        if result["girder_refund"]:
            self.cost -= self._girder_costs.pop(result["girder_id"], GIRDER_COST)
            self._design.pop(result["girder_id"], None)
        if self.cost < 0:
            self.cost = 0
        return {"ok": True, **result, "cost": self.cost}

    def rebuild(self) -> None:
        """Restore the undamaged design: fresh world, every beam replaced in order, no train."""
        design = list(self._design.values())
        self.world.reset()
        self._design.clear()
        self._girder_costs.clear()
        self.cost = 0
        self.peak_load = 0.0
        self.error = None
        for x1, y1, x2, y2, material in design:
            self.place_girder(x1, y1, x2, y2, material=material)
        self._outcome = "absent"

    def start_train(self, force: bool = False) -> dict[str, Any]:
        """Run the test. After a win or lose this rebuilds the bridge first, like the original game."""
        if self._outcome in ("win", "lose"):
            self.rebuild()
            force = True
        if force or self.world.first_train is None:
            # a new run: the bridge takes up its own weight before the train arrives;
            # resuming a paused run keeps its peak
            self.world.reset_peak()
            self.world.settle()
            self.peak_load = self.world.peak_load
        spawned = self.world.spawn_train(force=force)
        self.paused = False
        if self._outcome == "absent" and self.world.first_train is not None:
            self._outcome = "on_track"
        return {"ok": True, "spawned": spawned, "paused": self.paused}

    def pause(self) -> dict[str, Any]:
        self.paused = True
        return {"ok": True, "paused": True}

    def toggle_pause(self) -> dict[str, Any]:
        if self.world.first_train is None or self._outcome in ("win", "lose"):
            return self.start_train()
        self.paused = not self.paused
        return {"ok": True, "paused": self.paused}

    def reset(self) -> dict[str, Any]:
        self.world.reset()
        self.paused = True
        self.cost = 0
        self._girder_costs.clear()
        self._design.clear()
        self.peak_load = 0.0
        self._outcome = "absent"
        self.error = None
        return {"ok": True, "paused": True, "cost": 0, "budget": self.budget}

    def step(self) -> None:
        if self.paused:
            return
        try:
            self.world.step(DT)
            self.peak_load = max(self.peak_load, self.world.peak_load)
            self._update_outcome()
        except Exception as exc:
            self.paused = True
            self.error = str(exc)

    def _update_outcome(self) -> None:
        if self._outcome in ("win", "lose"):
            return
        pos = self.world.first_train_position()
        if pos is None:
            self._outcome = "absent"
            return
        x, y = pos
        if y < LOSE_Y:
            self._outcome = "lose"
        elif x >= WIN_X and y >= WIN_Y:
            self._outcome = "win"
        else:
            self._outcome = "on_track"

    def level(self) -> dict[str, Any]:
        """Facts about the level that never change during play."""
        return {
            "ok": True,
            "units": "metres, y-up",
            "budget": self.budget,
            "score": "budget minus cost after a win, 0 after a loss",
            "grid": {
                "spacing": GRID,
                "members": "neighbouring nodes only: 2 m orthogonal or 2.83 m diagonal",
                "nodes": (
                    "y=3,5,7,... everywhere; below the deck only inside the gap: "
                    "x=-4..4 at y=1 and y=-1"
                ),
                "growth": "a new beam must start from an anchor or a node already built",
            },
            "anchors": sorted(self.world.anchors),
            "gap": [GAP[0], GAP[1]],
            "win": f"lead car reaches x >= {WIN_X:g} while still at y >= {WIN_Y:g}",
            "lose": f"lead car falls below y = {LOSE_Y:g}",
            "joints": "beams that end on the same node are pinned there; a joint turns freely",
            "beams": (
                f"a beam breaks when its pull exceeds {self.break_force:g} N x its material "
                "strength, or its push exceeds that x (2 m / length)^2 (long beams buckle)"
            ),
            "materials": {
                name: {
                    "cost": MATERIALS[name].cost,
                    "strength": MATERIALS[name].strength,
                    "density": MATERIALS[name].density,
                    "break_force": self.break_force * MATERIALS[name].strength,
                }
                for name in MATERIAL_ORDER
            },
        }

    def status(self) -> dict[str, Any]:
        pos = self.world.first_train_position()
        payload: dict[str, Any] = {
            "ok": True,
            "paused": self.paused,
            "cost": self.cost,
            "budget": self.budget,
            "remaining": self.remaining(),
            "score": self.score(),
            "beam_cost": GIRDER_COST,
            "material": DEFAULT_MATERIAL,
            "materials": {
                name: MATERIALS[name].describe(self.break_force) for name in MATERIAL_ORDER
            },
            "peak_load": round(self.peak_load, 2),
            "train": self._outcome if pos is not None or self._outcome in ("win", "lose") else "absent",
            "train_x": None if pos is None else pos[0],
            "train_y": None if pos is None else pos[1],
            "girders": self.world.girder_count(),
            "joints": self.world.joint_count(),
            "anchors": sorted(self.world.anchors),
            "banks": {
                "left": [-10.0, BANK_TOP_Y],
                "right": [10.0, BANK_TOP_Y],
                "gap": [GAP[0], GAP[1]],
            },
        }
        if self.error:
            payload["error"] = self.error
        return payload
