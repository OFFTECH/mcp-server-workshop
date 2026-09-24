import json
import shutil
import subprocess
import urllib.error
from pathlib import Path

import pytest

from bridge_builder import setkey

KEY = "sk-ant-api03-" + "a1B2_c3D4-" * 8


def test_clean_key_strips_whitespace_and_quotes():
    assert setkey.clean_key(f'  "{KEY}"\n') == KEY


@pytest.mark.parametrize("raw", ["", "   ", "hello", "sk-ant-short", "sk-proj-" + "x" * 40])
def test_clean_key_rejects_what_is_not_an_anthropic_key(raw):
    with pytest.raises(ValueError):
        setkey.clean_key(raw)


def test_save_key_writes_an_api_key_helper(tmp_path: Path):
    path = setkey.save_key(KEY, tmp_path)
    assert path == tmp_path / ".claude" / "settings.local.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {"apiKeyHelper": f"echo {KEY}"}


def test_save_key_keeps_the_other_local_settings(tmp_path: Path):
    path = tmp_path / ".claude" / "settings.local.json"
    path.parent.mkdir()
    path.write_text('{"enabledMcpjsonServers": ["bridge-engineer"], "apiKeyHelper": "echo old"}', encoding="utf-8")
    setkey.save_key(KEY, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"enabledMcpjsonServers": ["bridge-engineer"], "apiKeyHelper": f"echo {KEY}"}


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_is_git_ignored_follows_gitignore(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(".claude/settings.local.json\n", encoding="utf-8")
    assert setkey.is_git_ignored(tmp_path / ".claude" / "settings.local.json", tmp_path) is True
    assert setkey.is_git_ignored(tmp_path / ".claude" / "settings.json", tmp_path) is False


def test_is_git_ignored_outside_a_repository_is_unknown(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(setkey.shutil, "which", lambda name: None)
    assert setkey.is_git_ignored(tmp_path / "x", tmp_path) is None


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_check_key_accepts_a_working_key(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["key"] = request.get_header("X-api-key")
        return _Response()

    monkeypatch.setattr(setkey.urllib.request, "urlopen", fake_urlopen)
    assert setkey.check_key(KEY) is True
    assert seen["key"] == KEY


def test_check_key_rejects_a_key_the_api_refuses(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(setkey.urllib.request, "urlopen", fake_urlopen)
    assert setkey.check_key(KEY) is False


def test_check_key_without_network_is_unknown(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(setkey.urllib.request, "urlopen", fake_urlopen)
    assert setkey.check_key(KEY) is None


@pytest.fixture
def project(tmp_path: Path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(setkey, "read_key", lambda: KEY)
    monkeypatch.setattr(setkey, "is_git_ignored", lambda path, root: True)
    return tmp_path


def test_main_saves_a_working_key(project: Path, monkeypatch):
    monkeypatch.setattr(setkey, "check_key", lambda key: True)
    assert setkey.main() == 0
    assert (project / ".claude" / "settings.local.json").is_file()


def test_main_refuses_a_key_the_api_rejects(project: Path, monkeypatch):
    monkeypatch.setattr(setkey, "check_key", lambda key: False)
    assert setkey.main() == 1
    assert not (project / ".claude" / "settings.local.json").exists()


def test_main_saves_when_the_key_cannot_be_checked(project: Path, monkeypatch):
    monkeypatch.setattr(setkey, "check_key", lambda key: None)
    assert setkey.main() == 0
    assert (project / ".claude" / "settings.local.json").is_file()


def test_main_refuses_when_git_would_track_the_file(project: Path, monkeypatch):
    monkeypatch.setattr(setkey, "check_key", lambda key: True)
    monkeypatch.setattr(setkey, "is_git_ignored", lambda path, root: False)
    assert setkey.main() == 1
    assert not (project / ".claude" / "settings.local.json").exists()
