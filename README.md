# Realm Fabric

A grid-based agent simulation framework designed around structured output and narrative roleplay.

**Current Status:** **V0.1 shipped** (`v0.1.0`). **V0.2 is in progress on `main`:** Sections **1–3 implemented** (coordinate move, compound two-phase turns, declarative object interact + effect registry). **Section 4 ship** (`v0.2.0` tag, `pyproject.toml` bump) is still pending — runtime and docs below describe the current stepper unless noted.

**Documentation:**

- [V0.2 implementation checklist](docs/v0.2-implementation-readiness-checklist.md) — **authoritative V0.2 spec** (Sections 0–4 agreed; 1–3 implemented)
- [V0.1 implementation checklist](docs/v0.1-implementation-readiness-checklist.md) — design reference for shipped V0.1 behavior (partially superseded by V0.2)
- [Roadmap](docs/ROADMAP.md) — version plans (V0.1 ✅, V0.2 🚧, V0.2.5, V0.3)
- [Long-term goals](LONG_TERM_GOALS.md) — aspirational features
- [V0 implementation checklist](docs/v0-implementation-readiness-checklist.md) — V0 historical design reference
- [Schema design references](docs/schemas/) — `AgentTurn` (pre-V0.2); **`AgentNavigationTurn` / `AgentActionTurn`** (V0.2 — implemented in `src/llm/schemas.py`)

## Running / Testing (without LLM)

1. Install [uv](https://docs.astral.sh/uv/) if you don't have it (Windows PowerShell):
  ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
2. In the project folder:
  ```powershell
   cd path\to\Realm-Fabric
   uv sync
  ```
3. Run the interactive manual tester:
  ```powershell
   uv run python src/main.py
  ```
   Few-shot examples are disabled by default for token efficiency. Use `--with-fewshots` to include navigation and action phase examples.
   Inside the `(realm)` prompt you can:
  - `list` — overview of all agents and objects (no turn consumed)
  - `objects` — list all objects with ids and action names (for `edit-object` / `delete-object`)
  - `agents` — list all agents with ids and active marker
  - `effects` — list registered object interaction effects (`delete_self`, `random_move_self`, …)
  - `state` — active agent context (memory, turn count, compound step breakdown, few-shots)
  - `vision` — see what the active agent currently perceives
  - `prompt` — show navigation and action prompts (`prompt nav` / `prompt action` for one phase)
  - `step-compound …` — manual compound turn (move / look / speak / interact)
  - `step-nav` / `step-action` — debug one phase without a full turn record (see `help`)
  - `run` — two-phase LLM turn for the **active** agent (requires OPENROUTER_API_KEY)
  - `Explorer` — (type an agent's name) to run an LLM turn for that agent
  - `switch Goblin` — change active agent for `vision` / `state` / `prompt` / manual steps / `run` without a turn or LLM call
  - `fewshots on/off` — toggle few-shot examples (OFF by default)
  - `quit`

### World editing (V0.1 + V0.2 object actions)

Listing and editing commands do **not** consume a turn. Use `list`, `objects`, `agents`, or `effects` to look up ids and effect names before editing.

```
list
objects
agents
effects
create-object name "Crate" pdesc "A crate." desc "A wooden crate." at 0,0
create-object name "Cookie" pdesc "A cookie." desc "Tasty." at 2,2 action eat range 1 effect delete_self result "You ate the cookie." passive "{actor} ate the cookie."
edit-object obj_sign_01 pdesc "A sign on the wall." desc "Updated sign text."
edit-object obj_ball_01 pos 3,3
edit-object obj_cookie_01 add-action smell range 1 result "Nice smell." passive "{actor} smells it."
edit-object obj_cookie_01 remove-action smell
delete-object obj_crate_01
create-agent name "Goblin" pdesc "A short figure." desc "A grumpy goblin." personality "You are a grumpy goblin." at 0,3
edit-agent agent_01 desc "Updated appearance."
edit-agent agent_01 personality "Updated LLM personality."
edit-agent agent_01 name "Scout"
delete-agent agent_goblin_01
```

The initial **ceramic ball** includes a built-in **`kick`** action (`range 1`, `random_move_self`). Example manual turn:

```
step-compound 2,3 interact obj_ball_01 kick
```

The old V0 `sign` command is removed. Update the sign with:

```
edit-object obj_sign_01 pdesc "A sign on the wall." desc "This is new text."
```

Objects and agents share **`pdesc`** (glance) and **`desc`** (detailed, hidden behind `[?]` until `look`). Agents also have **`personality`** — private LLM prompt text only, never shown in vision or revealed by `look`. Other agents appear in passive vision; you do not see yourself. Stale examined knowledge shows as `[?] [changed] {pdesc}`.

### Multi-agent (V0.1 Section 3)

Typical LLM workflow with two agents (each `run` / agent name = **two LLM calls**: navigation, then action):

```
switch Goblin    # inspect Goblin's vision/state without a turn
run              # compound LLM turn for the active agent (Goblin)
switch Explorer
Explorer         # typing a name also runs a compound LLM turn for that agent
```

Manual compound turn without the API:

```
step-compound 2,3 look obj_ball_01 speak Hello.
step-compound - interact obj_ball_01 kick
```

- Create agents with `create-agent`; list with `agents` or `list`
- **`run`** — two-phase LLM turn for the **active** agent (navigation then action; use after `switch`)
- **`switch <name>`** — change active agent without a turn (`vision`, `state`, `prompt`, manual steps, `run`)
- **Typing an agent's name** — two-phase LLM turn for that agent; sets them active (even if the LLM call fails)
- Agent display names must be **unique** and **cannot match stepper commands** (e.g. `vision`, `run`, `list`, `create-agent`) — validated automatically via `src/stepper_commands.py`
- Commands are **case-insensitive** (`Run`, `Switch Goblin`, etc.)
- Deleting the active agent reassigns to the first remaining agent and prints `Active agent: …`
- Turn numbers in each agent's memory are **per-agent** (1, 2, 3…); `session_turn` in logs is a global session label only
- Other agents appear in passive vision (`pdesc` + hidden `desc` until `look`); `personality` is LLM-only; agents do not see themselves

### V0.2 (implemented on main — `v0.2.0` tag pending)

| Area | V0.1 (`v0.1.0`) | V0.2 (current runtime) |
|------|-----------------|------------------------|
| Move | Cardinal one step (`north`, …) | Coordinate move to `"x,y"` on 0–4 grid |
| LLM turn | One call, one action (`AgentTurn`) | Two calls: navigation then action (`AgentNavigationTurn` + `AgentActionTurn`) |
| Turn shape | Move, look, or speak — one per turn | Optional move → optional one look → speak **or** object interact |
| Manual step | `step move\|look\|speak` | `step-compound` (+ optional `step-nav` / `step-action`) |
| Objects | Look only | Declarative **interact** + effect registry (`delete_self`, `random_move_self`; ball `kick`) |
| Speak limit | 280 characters | 500 characters (5 sentences unchanged) |

**Unchanged:** 5×5 grid, manual human control (`switch`, `run`, typing agent names), world editing, multi-agent passive vision, V0.1-style memory (10 turns, single `passive_result`). Full memory subsystem → **V0.2.5**; GUI → **V0.3**.

See [V0.2 checklist](docs/v0.2-implementation-readiness-checklist.md) for the full spec and Section 4 ship checklist.

## Environment Variables & .env Files (Beginner Guide)

This project uses **environment variables** for things like API keys. We manage them with a library called `python-dotenv`.

### What are .env files?

A `.env` file is just a plain text file that looks like this:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=deepseek/deepseek-v4-flash
```

Each line is `KEY=VALUE`. These become available to your program as if you had set them in the operating system environment.

### Why use .env files?

- You don't want to hard-code secrets (API keys, passwords) into your source code.
- Different people/machines can have different values.
- You can have different settings for development vs production.

### How to set one up in this project

1. Copy the template that is safe to commit:
  ```powershell
   copy .env.example .env
  ```
2. Open the new `.env` file in a text editor and fill in the values.
3. Save it. The program will automatically pick it up.

**Important**: The file `.env` is listed in `.gitignore`, so Git will never commit your real keys.

### How this program loads .env files

When you trigger anything that needs the LLM (e.g. typing the agent's name in the stepper), the code in `src/llm/client.py` automatically runs:

```python
load_dotenv()                    # loads .env
load_dotenv(".env.local", override=True)   # then loads .env.local (if it exists)
```

This means:

- Values in `.env.local` will override values in `.env`
- You only need a `.env` file for basic use

### Can I have multiple .env files?

**Yes.** This is very common. Here are typical patterns:


| File               | Purpose                          | Commit to Git?                | Example use                                                  |
| ------------------ | -------------------------------- | ----------------------------- | ------------------------------------------------------------ |
| `.env`             | Base settings for the project    | No (use .env.example instead) | Shared team defaults                                         |
| `.env.local`       | Your personal overrides          | **Never**                     | Your own API keys, local database URL                        |
| `.env.development` | Development-specific settings    | Sometimes                     | Debug flags, local services                                  |
| `.env.production`  | Production settings              | Sometimes                     | Real production keys (usually managed by the server instead) |
| `.env.example`     | Template with placeholder values | **Yes**                       | Shows teammates what keys are needed                         |


You can load any of them explicitly like this (advanced):

```python
from dotenv import load_dotenv
load_dotenv(".env.development", override=True)
```

### Quick commands

```powershell
# Create your local file from the template
copy .env.example .env

# Edit it (add your real OPENROUTER_API_KEY)

# Then run the program - it will automatically read the .env file
uv run python src/main.py
```

### Without any .env file

You can still use almost everything:

- All the manual commands (`step-compound`, `vision`, `state`, etc.) work perfectly.
- The only thing that requires an `OPENROUTER_API_KEY` is an LLM turn: type an agent's name (e.g. `Explorer`) or use `run` after selecting the active agent. Each turn makes **two** LLM calls (navigation, then action).

This design is intentional so you can explore and test the system without needing any paid services.

### Where the code actually reads the variables

Look at `src/llm/client.py`:

```python
from dotenv import load_dotenv
import os

load_dotenv()                    # loads .env + .env.local
api_key = os.getenv("OPENROUTER_API_KEY")
model   = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
```

`os.getenv("SOME_KEY")` looks for an environment variable. `load_dotenv()` populates those variables from the .env file(s) before the rest of the program runs.

That's the whole magic.

## Running tests

Tests use [pytest](https://docs.pytest.org/) and run **without** an API key or network access. They cover V0.1 perception/editing/multi-agent behavior plus V0.2 coordinate move, compound turns, and object interact (**152 tests**).

### Run all tests

From the project folder:

```powershell
uv run pytest
```

By default this runs quietly (`-q` is set in `pyproject.toml`). You should see a final `passed` summary when everything is green.

### Useful variants

```powershell
# Verbose — shows each test name as it runs
uv run pytest -v

# Single file
uv run pytest tests/test_perception.py -v

# Single test by name
uv run pytest tests/test_perception.py::test_ball_vision_states_never_stale_current -v

# Stop on first failure (helpful while debugging)
uv run pytest -x
```

### What each test file covers

| File | Focus |
|------|--------|
| `tests/test_schema.py` | `AgentNavigationTurn` / `AgentActionTurn` Pydantic validation |
| `tests/test_coordinate_move.py` | Coordinate move parser, bounds, schema |
| `tests/test_compound_turn.py` | Compound orchestration, `TurnRecord.steps`, step-compound parser |
| `tests/test_object_actions.py` | Effect registry, interact range/vision, `delete_self`, ball `kick` |
| `tests/test_world.py` | Initial world state, grid rules, passive vision baseline |
| `tests/test_simulation.py` | Compound turns, memory side effects, prompts |
| `tests/test_perception.py` | V0.1 `[?]` / stale vision for objects and cross-agent invalidation |
| `tests/test_world_edit.py` | World editing commands (create/edit/delete, listings, object actions) |
| `tests/test_multi_agent.py` | Multi-agent stepper (`switch`, `run`, agent vision, `passive_result`, LLM mocks) |

### First-time setup

`uv sync` installs pytest via the `dev` dependency group. If pytest is missing:

```powershell
uv sync
uv run pytest -v
```

