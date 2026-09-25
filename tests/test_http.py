import threading
import time

import pytest

from bridge_builder.api import GameAPI
from bridge_builder.client import call_tool
from bridge_builder.game import Game
from bridge_builder.mcp_server import bind_api, load_stage, mcp
from bridge_builder.server import HOST, PORT, port_free

load_stage(3, "solution", "solution", "solution")


def test_status_over_http():
    if not port_free(HOST, PORT):
        pytest.skip("port 8765 busy; stop the other bridge-engineer first")
    game = Game()
    api = GameAPI(game)
    bind_api(api)
    http = threading.Thread(
        target=lambda: mcp.run(transport="streamable-http", host=HOST, port=PORT),
        daemon=True,
    )
    http.start()
    owner_stop = threading.Event()

    def owner():
        while not owner_stop.is_set():
            api.drain()
            time.sleep(0.01)

    loop = threading.Thread(target=owner, daemon=True)
    loop.start()
    deadline = time.time() + 8.0
    last = None
    while time.time() < deadline:
        try:
            last = call_tool("status")
            if last.get("ok"):
                break
        except Exception as exc:
            last = {"ok": False, "error": str(exc)}
        time.sleep(0.2)
    owner_stop.set()
    assert last is not None
    assert last.get("ok") is True, last
    assert last["girders"] == 0
    assert last["peak_load"] == 0.0


def test_stage_flag_defaults_to_everything():
    from bridge_builder.server import parse_args

    assert parse_args([]).stage == 3
    assert parse_args(["--stage", "1"]).stage == 1
    assert parse_args(["--stdio", "--stage", "2"]).stdio is True


def test_tools_flag_picks_mine_or_the_solution():
    from bridge_builder.server import parse_args

    assert parse_args(["--stage", "1"]).choice is None  # the stage decides: see default_choice
    assert parse_args(["--stage", "1", "--solution"]).choice == "solution"
    assert parse_args(["--stage", "3", "--mine"]).choice == "mine"
    with pytest.raises(SystemExit):
        parse_args(["--solution", "--mine"])


def test_stage_flag_rejects_unknown_stages():
    import pytest

    from bridge_builder.server import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--stage", "4"])
