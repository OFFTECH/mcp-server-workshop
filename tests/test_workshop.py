"""The stage 1 helpers: the checker grades tools through MCP, restore resets the exercise."""

import subprocess
import sys
from pathlib import Path

from bridge_builder import workshop

PACKAGE = Path(workshop.__file__).parent


def _check(flag: str, stage: int = 1) -> subprocess.CompletedProcess:
    # Each check loads an exercise module into the one server, so it needs its own interpreter.
    return subprocess.run(
        [sys.executable, "-m", "bridge_builder.workshop", "check", flag, "--stage", str(stage)],
        capture_output=True, text=True,
    )


def test_the_reference_tools_pass_every_check():
    out = _check("--solution")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "4 of 4 tools done, 3 of 3 stretch." in out.stdout
    assert " x " not in out.stdout
    assert "Tips" not in out.stdout  # the reference is also the model answer for the tips


def test_the_blank_exercise_has_nothing_done_and_nothing_broken():
    out = _check("--blank")
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.count("not a tool yet") == len(workshop.CHECKS)
    assert "0 of 4 tools done" in out.stdout


def test_restore_puts_back_the_blank_and_keeps_yours(tmp_path):
    blank = (PACKAGE / "solution" / "my_tools_blank.py").read_text(encoding="utf-8")
    (tmp_path / "solution").mkdir()
    (tmp_path / "solution" / "my_tools_blank.py").write_text(blank, encoding="utf-8")
    mine = tmp_path / "my_tools.py"
    mine.write_text("@mcp.tool()\ndef half_done(", encoding="utf-8")

    backup = workshop.restore(tmp_path)

    assert backup is not None and backup.read_text(encoding="utf-8") == "@mcp.tool()\ndef half_done("
    assert mine.read_text(encoding="utf-8") == blank.split("\n", 1)[1]
    assert mine.read_text(encoding="utf-8").startswith('"""Stage 1: YOUR tools.')
    assert workshop.restore(tmp_path) is None  # already blank: nothing to keep


def test_the_solution_is_the_exercise_plus_decorators():
    # Someone who is stuck compares the two files: only the decorators may differ.
    def code(text: str) -> list[str]:
        body = text[text.index('"""\n', 3) + 4:]  # after the module docstring
        return [line for line in body.splitlines() if not line.startswith("@mcp.tool(")]

    blank = (PACKAGE / "solution" / "my_tools_blank.py").read_text(encoding="utf-8").split("\n", 1)[1]
    solution = (PACKAGE / "solution" / "mcp_tools.py").read_text(encoding="utf-8")
    assert code(solution) == code(blank)
    assert sum(line.startswith("@mcp.tool(") for line in solution.splitlines()) == len(workshop.CHECKS)


# --- stage 2: resources ------------------------------------------------------


def test_the_reference_resources_pass_every_check():
    out = _check("--solution", stage=2)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "4 of 4 resources done." in out.stdout
    assert " x " not in out.stdout
    assert "Tips" not in out.stdout


def test_the_blank_resources_have_nothing_done():
    out = _check("--blank", stage=2)
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.count("not a resource yet") == len(workshop.RESOURCE_CHECKS)


def test_restore_stage_2_puts_back_the_blank_resources(tmp_path):
    blank = (PACKAGE / "solution" / "my_resources_blank.py").read_text(encoding="utf-8")
    (tmp_path / "solution").mkdir()
    (tmp_path / "solution" / "my_resources_blank.py").write_text(blank, encoding="utf-8")
    (tmp_path / "my_resources.py").write_text("half done", encoding="utf-8")

    backup = workshop.restore(tmp_path, stage=2)

    assert backup is not None and backup.name.startswith("my_resources.")
    assert (tmp_path / "my_resources.py").read_text(encoding="utf-8") == blank.split("\n", 1)[1]


def test_the_resource_solution_is_the_exercise_plus_decorators():
    # As in stage 1: someone who is stuck compares the two files, and only the decorators differ.
    def code(text: str) -> list[str]:
        body = text[text.index('"""\n', 3) + 4:]  # after the module docstring
        return [line for line in body.splitlines() if not line.startswith("@mcp.resource(")]

    blank = (PACKAGE / "solution" / "my_resources_blank.py").read_text(encoding="utf-8").split("\n", 1)[1]
    solution = (PACKAGE / "solution" / "mcp_resources.py").read_text(encoding="utf-8")
    assert code(solution) == code(blank)
    assert sum(line.startswith("@mcp.resource(") for line in solution.splitlines()) == len(workshop.RESOURCE_CHECKS)


# --- stage 3: prompts -------------------------------------------------------------


def test_the_reference_prompts_pass_every_check():
    out = _check("--solution", stage=3)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "2 of 2 prompts done." in out.stdout
    assert "Tips" not in out.stdout


def test_the_blank_prompts_have_nothing_done():
    out = _check("--blank", stage=3)
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.count("not a prompt yet") == len(workshop.PROMPT_CHECKS)


def test_the_prompt_solution_is_the_exercise_plus_decorators():
    def code(text: str) -> list[str]:
        body = text[text.index('"""' + chr(10), 3) + 4:]  # after the module docstring
        return [line for line in body.splitlines() if not line.startswith("@mcp.prompt(")]

    blank = (PACKAGE / "solution" / "my_prompts_blank.py").read_text(encoding="utf-8").split(chr(10), 1)[1]
    solution = (PACKAGE / "solution" / "mcp_prompts.py").read_text(encoding="utf-8")
    assert code(solution) == code(blank)
    assert sum(line.startswith("@mcp.prompt(") for line in solution.splitlines()) == len(workshop.PROMPT_CHECKS)


def test_restore_stage_3_puts_back_the_blank_prompts(tmp_path):
    blank = (PACKAGE / "solution" / "my_prompts_blank.py").read_text(encoding="utf-8")
    (tmp_path / "solution").mkdir()
    (tmp_path / "solution" / "my_prompts_blank.py").write_text(blank, encoding="utf-8")
    (tmp_path / "my_prompts.py").write_text("half done", encoding="utf-8")

    backup = workshop.restore(tmp_path, stage=3)

    assert backup is not None and backup.name.startswith("my_prompts.")
    assert (tmp_path / "my_prompts.py").read_text(encoding="utf-8") == blank.split(chr(10), 1)[1]
