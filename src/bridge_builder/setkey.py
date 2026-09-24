"""Save an Anthropic API key where Claude Code picks it up for this project only.

Run ``uv run set-api-key`` and paste the key. It is checked against the API and
written to ``.claude/settings.local.json`` as an ``apiKeyHelper``. That file is
gitignored, so the key never reaches the repository.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from bridge_builder.client import find_project_root

KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")
MODELS_URL = "https://api.anthropic.com/v1/models"
SETTINGS = Path(".claude") / "settings.local.json"


def clean_key(raw: str) -> str:
    """The pasted key without spaces or quotes; ValueError if it is not an Anthropic key."""
    key = raw.strip().strip("'\"").strip()
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError("that does not look like an Anthropic API key (it starts with sk-ant-)")
    return key


def check_key(key: str, timeout: float = 10) -> bool | None:
    """True if the API accepts the key, False if it refuses it, None if it cannot be reached."""
    request = urllib.request.Request(
        MODELS_URL, headers={"x-api-key": key, "anthropic-version": "2023-06-01"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except urllib.error.HTTPError as error:
        return False if error.code in (401, 403) else None
    except (urllib.error.URLError, OSError):
        return None


def is_git_ignored(path: Path, root: Path) -> bool | None:
    """Whether git ignores ``path``; None when git or the repository is missing."""
    if shutil.which("git") is None:
        return None
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=root, capture_output=True
    )
    return {0: True, 1: False}.get(result.returncode)


def save_key(key: str, root: Path) -> Path:
    """Write the key into ``root/.claude/settings.local.json``, keeping its other settings."""
    path = root / SETTINGS
    settings = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    settings["apiKeyHelper"] = f"echo {key}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return path


def read_key() -> str:
    """Ask for the key; hidden when typing in a terminal."""
    prompt = "Paste your Anthropic API key and press Enter (it stays hidden): "
    return getpass.getpass(prompt) if sys.stdin.isatty() else input(prompt)


def main() -> int:
    root = find_project_root()
    path = root / SETTINGS
    try:
        key = clean_key(read_key())
    except ValueError as error:
        print(f"Not saved: {error}.")
        return 1

    if is_git_ignored(path, root) is False:
        print(f"Not saved: git would track {SETTINGS}, and the key could end up on GitHub.")
        return 1

    print("Checking the key with Anthropic...")
    valid = check_key(key)
    if valid is False:
        print("Not saved: Anthropic rejected this key. Copy it again from the console and retry.")
        return 1
    if valid is None:
        print("Could not reach Anthropic to check the key (offline or blocked?). Saving it anyway.")

    save_key(key, root)
    print(f"Saved to {path}")
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("Note: ANTHROPIC_API_KEY is also set in your environment; Claude Code uses that one first.")
    print("\nNext: run `claude` in this folder and choose 'Yes, I trust this folder'")
    print("(press the down arrow, then Enter: the default answer is No).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
