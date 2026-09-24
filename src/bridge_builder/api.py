"""Thread-safe command queue. Box2D is only touched on the owner thread via drain()."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any

from bridge_builder.game import Game


@dataclass
class Command:
    op: str
    payload: dict[str, Any]
    result: Future = field(default_factory=Future)


class GameAPI:
    def __init__(self, game: Game) -> None:
        self.game = game
        self._queue: Queue[Command] = Queue()

    def submit(self, op: str, payload: dict[str, Any] | None = None, timeout: float = 2.0) -> dict[str, Any]:
        cmd = Command(op=op, payload=payload or {})
        self._queue.put(cmd)
        try:
            return cmd.result.result(timeout=timeout)
        except TimeoutError:
            # Withdraw the command so it cannot run after we have reported failure.
            if cmd.result.cancel():
                return {"ok": False, "error": "timeout: the game loop did not respond"}
            # drain() already started it; the result is moments away.
            return cmd.result.result()

    def drain(self) -> None:
        while True:
            try:
                cmd = self._queue.get_nowait()
            except Empty:
                return
            if not cmd.result.set_running_or_notify_cancel():
                continue  # the caller timed out and withdrew it
            try:
                payload = cmd.payload
                if cmd.op == "place_girder":
                    out = self.game.place_girder(
                        float(payload["x1"]),
                        float(payload["y1"]),
                        float(payload["x2"]),
                        float(payload["y2"]),
                        material=payload.get("material"),
                    )
                elif cmd.op == "place_girders":
                    out = self.game.place_girders(
                        list(payload["beams"]), reset=bool(payload.get("reset", False))
                    )
                elif cmd.op == "add_joint":
                    out = self.game.add_joint(float(payload["x"]), float(payload["y"]))
                elif cmd.op == "destroy_at":
                    out = self.game.destroy_at(
                        float(payload["x"]), float(payload["y"]), snap=bool(payload.get("snap", True))
                    )
                elif cmd.op == "start_train":
                    out = self.game.start_train(force=bool(payload.get("force", False)))
                elif cmd.op == "pause":
                    out = self.game.pause()
                elif cmd.op == "reset":
                    out = self.game.reset()
                elif cmd.op == "status":
                    out = self.game.status()
                elif cmd.op == "level":
                    out = self.game.level()
                else:
                    out = {"ok": False, "error": "unknown op"}
            except Exception as exc:
                out = {"ok": False, "error": str(exc)}
            cmd.result.set_result(out)
