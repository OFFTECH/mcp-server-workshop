import json
from pathlib import Path

from bridge_builder.client import MCP_URL, register_claude


def test_register_claude_writes_project_mcp_json(tmp_path: Path):
    result = register_claude(project_root=tmp_path)
    path = tmp_path / ".mcp.json"
    assert result["ok"] is True
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    server = data["mcpServers"]["bridge-engineer"]
    assert server["url"] == MCP_URL
    assert server.get("type") == "http"


def test_find_project_root_walks_up_to_pyproject(tmp_path: Path):
    from bridge_builder.client import find_project_root

    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    notebooks = tmp_path / "notebooks"
    notebooks.mkdir()
    assert find_project_root(notebooks) == tmp_path
    assert find_project_root(tmp_path) == tmp_path


def test_find_project_root_falls_back_to_the_start_folder(tmp_path: Path):
    from bridge_builder.client import find_project_root

    assert find_project_root(tmp_path) == tmp_path


def test_register_claude_from_the_notebooks_folder_writes_the_root_config(tmp_path: Path, monkeypatch):
    import bridge_builder.client as client

    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    notebooks = tmp_path / "notebooks"
    notebooks.mkdir()
    monkeypatch.chdir(notebooks)
    monkeypatch.setattr(client.shutil, "which", lambda name: None)  # no real `claude mcp add`
    result = client.register_claude(include_desktop=False)
    assert (tmp_path / ".mcp.json").exists()
    assert not (notebooks / ".mcp.json").exists()
    assert result["wrote"] == [str(tmp_path / ".mcp.json")]
