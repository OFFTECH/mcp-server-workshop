# MCP Workshop

Repository for a hands-on workshop on the Model Context Protocol (MCP).

- A python code stems (Python, pygame + Box2D) illustrating how to implement MCP server.
- A Jupyter notebook in `notebooks/` with the workshop guide.
- Python 3.12, managed with [uv](https://docs.astral.sh/uv/). A dev container config is included for GitHub Codespaces.

## Before the workshop: set up your environment

This covers setting up an environment that can run the workshop. The case study,
the notebook and setting up Claude are done together on the day.

There are two ways to get an environment:

- **Option A — GitHub Codespaces (recommended).** Nothing to install, works from a browser on any OS.
- **Option B — Native install.** Windows, macOS or Linux; needs permission to install software and about 15 minutes.

### Option A — GitHub Codespaces

#### 1. Use a personal GitHub account

Create one at [github.com/signup](https://github.com/signup) if needed.

Do not use an enterprise account: organisations can disable Codespaces by policy, and
you cannot override that yourself. A free personal account includes enough Codespaces
hours for this workshop several times over.

#### 2. Create the Codespace

Open [codespaces.new/OFFTECH/mcp-server-workshop](https://codespaces.new/OFFTECH/mcp-server-workshop):

- **Machine type:** 4-core.
- **ANTHROPIC_API_KEY:** paste the API key you were given.

The first start builds the container and takes a few minutes. It only happens once;
after that the Codespace resumes in seconds. When it finishes you get VS Code in your
browser. Wait until the extensions and the environment have finished installing.

The game window lives on the Codespace's virtual desktop. If noVNC did not open by
itself: in the **Ports** tab, right-click **Game desktop (noVNC)** on port 6080 and
choose **Open in Browser**.

#### 3. Check it works

In the VS Code terminal:

```bash
uv sync --python 3.12 --extra dev
uv run pytest
uv run python -m bridge_builder
```

The game window with the bridge level now appears in the noVNC tab. Setting noVNC's
scaling mode to **Local scaling** (in its settings panel) makes it fit the tab.

Open a new terminal and run `claude`. When it asks whether to use the API key, choose
**Yes**; answer **Yes** to the questions that follow, then choose **Trust this workspace**.

Done, you are ready to go!

### Option B — Native install

**Before you start, check you have:** Windows 10/11, macOS or Linux, on x86_64 or
Apple Silicon; permission to install software; about 3 GB of free disk.

Windows on ARM (e.g. Snapdragon laptops) and Linux on ARM are **not supported**: the
physics engine has no prebuilt package for them. Use Codespaces instead.

#### 1. Install Git, VS Code and Node.js

**Windows**, in PowerShell:

```powershell
winget install --id Git.Git -e
winget install --id Microsoft.VisualStudioCode -e
winget install --id OpenJS.NodeJS.LTS -e
```

**macOS**, with [Homebrew](https://brew.sh):

```bash
brew install git node
brew install --cask visual-studio-code
```

**Linux (Debian/Ubuntu):**

```bash
sudo apt-get update && sudo apt-get install -y git curl
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Install VS Code from [code.visualstudio.com](https://code.visualstudio.com/download) (the `.deb` package).

Do not install Node.js with plain `apt-get install nodejs`: Ubuntu's own package is too
old. Claude Code and the MCP Inspector need Node.js **22 or newer**.

**Close and reopen your terminal** so the new commands are found, then check:

```bash
git --version
node --version
```

`node --version` must print `v22` or higher.

#### 2. Install uv

uv manages Python for the project; you do not need to install Python yourself.

**Windows**, in PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen your terminal again, then check with `uv --version`.

#### 3. Install Claude Code and the MCP Inspector

```bash
npm install -g @anthropic-ai/claude-code @modelcontextprotocol/inspector
claude --version
```

On Linux, prefix the install with `sudo`.

#### 4. Install the VS Code extensions

```bash
code --install-extension ms-python.python \
     --install-extension ms-python.vscode-pylance \
     --install-extension ms-python.debugpy \
     --install-extension ms-toolsai.jupyter \
     --install-extension ms-toolsai.jupyter-renderers \
     --install-extension charliermarsh.ruff \
     --install-extension anthropic.claude-code \
     --install-extension tamasfe.even-better-toml
```

In PowerShell, put it all on one line, or replace each trailing `\` with a backtick `` ` ``.

If `code` is not found on macOS: open VS Code, press `Cmd+Shift+P`, and run
**Shell Command: Install 'code' command in PATH**.

#### 5. Get the workshop code

Go to the folder where you keep projects, then:

```bash
git clone https://github.com/OFFTECH/mcp-server-workshop.git
cd mcp-server-workshop
```

#### 6. Install the project and run the tests

```bash
uv sync --python 3.12 --extra dev
uv run pytest
```

The first run downloads Python 3.12 and the packages, which takes a few minutes.

#### 7. Set your Claude API key

Have your Anthropic API key ready (it starts with `sk-ant-`), then run:

```bash
uv run set-api-key
```

Paste the key when asked and press Enter. It stays hidden while you paste; that is
intentional. The script checks the key with Anthropic and, if it works, saves it in
`.claude/settings.local.json` inside the project. Claude Code picks it up from there
whenever you start it in this folder. That file is gitignored, so the key never
reaches the repository.

If it says the key was rejected, copy it again and rerun the command.

#### 8. Launch the game

```bash
uv run python -m bridge_builder
```

A window with the bridge level opens, and the terminal prints
`Uvicorn running on http://127.0.0.1:8765`: that is the MCP server Claude will talk
to. **Leave the game running** for the next step.

#### 9. Check that Claude sees the game

Open a **second terminal**, go to the `mcp-server-workshop` folder, and start Claude Code:

```bash
claude
```

The first time, it asks whether you trust this folder. The pre-selected answer is
**No, exit**: press the **down arrow** to choose **Yes, I trust this folder**, then Enter.

In Claude, type:

```
/mcp
```

The list must show **bridge-engineer** as connected: Claude has found the game's MCP
server. Press **Esc** to close the list, then type `/exit` to leave Claude.

If bridge-engineer is missing, failed or waiting for approval: check the game is still
running, then exit Claude and start it again **from the `mcp-server-workshop` folder**.
Claude only finds the server when started there, and only after you trusted the folder.

Close the game window (or press **Esc** in it). Finally, open the project in VS Code,
where you will work on the day:

```bash
code .
```

Done, you are ready to go!

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
