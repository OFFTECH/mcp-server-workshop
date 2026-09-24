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
