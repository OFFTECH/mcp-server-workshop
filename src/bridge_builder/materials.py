"""Beam materials: cost, strength, and weight trade-offs.

Steel is the cheap default. Wood (engineered timber) costs a little more per beam
and is weaker: you choose it for sustainability, not to save money. Titanium is
strong, light, and expensive.

``strength`` multiplies the level's base break force (``game.BREAK_FORCE``):
a wood beam breaks at 0.6x the pull a steel beam survives.
``stiffness`` multiplies steel's axial stiffness: how little a beam stretches
or shortens under load (wood gives most; light titanium a little more than steel).
``density`` sets the beam's weight, the dead load the bridge must carry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Material:
    name: str
    cost: int
    strength: float
    stiffness: float
    density: float
    color: tuple[int, int, int]

    def describe(self, break_force: float) -> dict:
        d = asdict(self)
        d["color"] = list(self.color)
        d["break_force"] = break_force * self.strength
        return d


MATERIALS: dict[str, Material] = {
    "wood": Material("wood", cost=120, strength=0.6, stiffness=0.5, density=0.5, color=(170, 120, 60)),
    "steel": Material("steel", cost=100, strength=1.0, stiffness=1.0, density=1.0, color=(50, 50, 55)),
    "titanium": Material(
        "titanium", cost=400, strength=2.0, stiffness=0.8, density=0.8, color=(90, 130, 200)
    ),
}
MATERIAL_ORDER: list[str] = ["wood", "steel", "titanium"]
DEFAULT_MATERIAL = "steel"


def get_material(name: str | None) -> Material | None:
    """Look up a material by name (case-insensitive); ``None`` when unknown."""
    if name is None:
        return MATERIALS[DEFAULT_MATERIAL]
    return MATERIALS.get(str(name).strip().lower())
