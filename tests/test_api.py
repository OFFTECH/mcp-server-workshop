import threading
import time

from bridge_builder.api import GameAPI
from bridge_builder.game import Game


def test_api_queue_status():
    g = Game()
    api = GameAPI(g)
    box: dict = {}

    def worker():
        box["s"] = api.submit("status", {})

    t = threading.Thread(target=worker)
    t.start()
    for _ in range(50):
        api.drain()
        if "s" in box:
            break
        time.sleep(0.01)
    t.join(1)
    assert box["s"]["ok"] is True
    assert box["s"]["girders"] == 0
    assert box["s"]["banks"]["gap"] == [-6.0, 6.0]


def test_api_timeout():
    g = Game()
    api = GameAPI(g)
    r = api.submit("status", {}, timeout=0.05)
    assert r["ok"] is False
    assert r["error"].startswith("timeout")


def test_api_place_girder_from_worker():
    g = Game()
    api = GameAPI(g)
    box: dict = {}

    def worker():
        box["r"] = api.submit("place_girder", {"x1": -6.0, "y1": 3.0, "x2": -4.0, "y2": 3.0})

    t = threading.Thread(target=worker)
    t.start()
    deadline = time.time() + 1.0
    while time.time() < deadline:
        api.drain()
        if "r" in box:
            break
        time.sleep(0.01)
    t.join(1)
    assert box["r"]["ok"] is True
    assert g.status()["girders"] == 1


def test_api_place_girder_with_material():
    from bridge_builder.materials import MATERIALS

    g = Game()
    api = GameAPI(g)
    box: dict = {}

    def worker():
        box["r"] = api.submit(
            "place_girder", {"x1": -6.0, "y1": 3.0, "x2": -4.0, "y2": 3.0, "material": "wood"}
        )

    t = threading.Thread(target=worker)
    t.start()
    deadline = time.time() + 1.0
    while time.time() < deadline:
        api.drain()
        if "r" in box:
            break
        time.sleep(0.01)
    t.join(1)
    assert box["r"]["ok"] is True
    assert box["r"]["material"] == "wood"
    assert g.status()["cost"] == MATERIALS["wood"].cost


def test_timed_out_command_never_runs():
    g = Game()
    api = GameAPI(g)
    out = api.submit("place_girder", {"x1": -6, "y1": 3, "x2": -4, "y2": 3}, timeout=0.05)
    assert out["ok"] is False
    assert "timeout" in out["error"]
    api.drain()
    assert g.status()["girders"] == 0


def test_place_girders_runs_as_one_command_on_the_game_thread():
    import threading
    import time

    from bridge_builder.api import GameAPI
    from bridge_builder.game import Game

    game = Game()
    api = GameAPI(game)
    box = {}
    beams = [{"x1": -6, "y1": 3, "x2": -4, "y2": 3}, {"x1": -4, "y1": 3, "x2": -2, "y2": 3}]
    t = threading.Thread(target=lambda: box.setdefault("r", api.submit("place_girders", {"beams": beams, "reset": True})))
    t.start()
    deadline = time.time() + 2
    while "r" not in box and time.time() < deadline:
        api.drain()
        time.sleep(0.01)
    t.join(1)
    assert box["r"]["ok"] is True
    assert box["r"]["placed"] == 2
    assert game.status()["girders"] == 2
