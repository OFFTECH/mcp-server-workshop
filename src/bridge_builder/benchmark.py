"""Replay a beam list in a headless game and measure how the bridge performs.

The knowledge files record these numbers; tests replay every design to keep
them honest. ``python -m bridge_builder.benchmark`` prints fresh numbers for all
designs, e.g. after adding a design or tuning the physics.
"""

from __future__ import annotations

from collections.abc import Iterable

from bridge_builder.game import Game
from bridge_builder.physics import DT

Beam = tuple[float, float, float, float, str]


def run_benchmark(beams: Iterable[Beam], seconds: float = 15.0) -> dict:
    """Build ``beams`` in order, send the train, and report cost, result, and peak beam load."""
    game = Game()
    for x1, y1, x2, y2, material in beams:
        out = game.place_girder(x1, y1, x2, y2, material=material)
        if not out["ok"]:
            raise ValueError(f"cannot place ({x1}, {y1})->({x2}, {y2}) {material}: {out['error']}")
    game.start_train()
    for _ in range(int(seconds / DT)):
        game.step()
        if game.status()["train"] in ("win", "lose"):
            break
    st = game.status()
    return {"cost": st["cost"], "result": st["train"], "peak_load": st["peak_load"]}


def main() -> None:
    from bridge_builder.designs import load_designs

    for design in load_designs().values():
        print(f"{design.name:16s} recorded {design.benchmark}  measured {run_benchmark(design.beams)}")


if __name__ == "__main__":
    main()
