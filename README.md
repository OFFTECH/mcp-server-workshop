# MCP Workshop

Repository for a hands-on workshop on the Model Context Protocol (MCP).

- A python code stems (Python, pygame + Box2D) illustrating how to implement MCP server.
- A Jupyter notebook in `notebooks/` with the workshop guide.
- Python 3.12, managed with [uv](https://docs.astral.sh/uv/). A dev container config is included for GitHub Codespaces.

## Quick start

```bash
uv sync --python 3.12 --extra dev
uv run pytest
uv run python -m bridge_builder
```

## Workshop stages

```bash
uv run python -m bridge_builder --stage 1              # the bare server + your tools
uv run python -m bridge_builder --stage 1 --solution   # the reference tools instead
uv run python -m bridge_builder --stage 2              # + your resources: level facts and designs
uv run python -m bridge_builder --stage 3              # + your prompts: design and brief, client briefs
```

| File | What it is |
|---|---|
| `src/bridge_builder/mcp_server.py` | the bare server: name, instructions, the line to the game |
| `src/bridge_builder/my_tools.py` | **stage 1 exercise**: the functions are written; you add `@mcp.tool()` |
| `src/bridge_builder/solution/mcp_tools.py` | the reference tools |
| `src/bridge_builder/my_resources.py` | **stage 2 exercise**: the functions are written; you add `@mcp.resource(...)` |
| `src/bridge_builder/solution/mcp_resources.py` | the reference resources |
| `src/bridge_builder/my_prompts.py` | **stage 3 exercise**: the prompts are written; you add `@mcp.prompt(...)` |
| `src/bridge_builder/solution/mcp_prompts.py` | the reference prompts |
| `src/bridge_builder/mcp_designs.py`, `mcp_clients.py` | the rest of stages 2 and 3 (instructions, `build_design`, client briefs) |

Each stage serves your file for that stage's exercise and the reference answers
for the stages before it, so everyone starts a stage from the same working server.
`--solution` serves the reference everywhere, `--mine` your files everywhere.

```bash
uv run workshop check               # stage 1: call your tools the way the model does
uv run workshop check --stage 2     # stage 2: read your resources the way the client does
uv run workshop check --stage 3     # stage 3: get your prompts the way the client does
uv run workshop restore [--stage N] # put back the untouched exercise file (yours is kept as .bak)
```

After changing an exercise file, restart the game and run `/mcp` in Claude Code to
reconnect: the server does not reload by itself.
