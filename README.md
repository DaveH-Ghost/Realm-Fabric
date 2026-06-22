# Realm Fabric

A grid-based agent simulation framework designed around structured output and narrative roleplay.

**Current Status:** **V0.4.4** (`0.4.4` in `pyproject.toml`) + [**realm-studio**](examples/web/realm-studio) example app. Tag **`v0.4.4`** when ready. Ships: **compact default prompt** (~500 est. input tokens, down from ~966) and **compact JSON keys** (`move`, `look`, `say`, `action`, `verb`) — plus V0.4.3 memory UI, V0.4.2 emote/speak/debug, V0.4.1 prompt layout, and V0.4.0 movement / multi-area.

**Documentation:**

- [V0.4.4 changelog](docs/v0.4.4-changelog.md) — prompt/schema token reduction (**0.4.4a–d**) ✅
- [V0.4.3 changelog](docs/v0.4.3-changelog.md) — memory module UI, edit location, witness broadcast (**0.4.3a–c**) ✅
- [V0.4.2 changelog](docs/v0.4.2-changelog.md) — emote, speak step, action range units, debug panels (**0.4.2a–e**) ✅
- [V0.4.1 changelog](docs/v0.4.1-changelog.md) — truncation, prompt blocks, prompt editor, vision units (**0.4.1a–d**) ✅
- [V0.4.0 changelog](docs/v0.4.0-changelog.md) — movement, multi-area, `move_area`, object actions (**0.4.0a–e**) ✅
- [V0.3.2 changelog](docs/v0.3.2-changelog.md) — **realm-studio** GM events, pannable grid, token images (0.3.2a–e) ✅
- [V0.3.1 changelog](docs/v0.3.1-changelog.md) — **realm-studio** web app (0.3.1a–f) ✅
- [V0.3.0 changelog](docs/v0.3.0-changelog.md) — engine refactor (0.3.0a–e)
- [Roadmap](docs/ROADMAP.md) — version plans (**V0.4.4** ✅; **V0.4.5** save/load planned; V0.4.x ✅)
- [V0.2.5 changelog](docs/v0.2.5-changelog.md) — memory / prompt slices (0.2.5a–g)
- [Long-term goals](LONG_TERM_GOALS.md) — aspirational features
- [V0 implementation checklist](docs/v0-implementation-readiness-checklist.md) — V0 historical design reference
- [Schema design references](docs/schemas/) — `AgentTurn` (pre-V0.2); compound turn schema in `src/llm/schemas.py`

## Engine vs apps

**Realm-Fabric is the engine** — grid sim, perception, compound turns, memory modules, and a stable library API. **Apps and games build on top** with their own prompts, UI, and scenarios.

| Layer | What it is |
|-------|------------|
| **`realm_fabric` package** | Public API: `Session`, `GameProfile`, `load_profile`, `PromptContext`, `AgentCompoundTurn`, snapshots |
| **`realm` CLI** | Reference client (`ManualStepper`) for manual testing — not required for library use |
| **[realm-studio](examples/web/realm-studio)** | Example web UI (V0.4.3) — create-agent memory module + options, edit location panels, emotes/speak step, prompt layout, vision units, last prompt/response debug, multi-area grid, GM **Emit event**, LLM **Run turn** over HTTP |

Quick start for a downstream project:

```python
from realm_fabric import Session, load_profile, AgentCompoundTurn

session = Session.from_profile(load_profile("default_compound"))
prompt = session.build_prompt()
# ... call your LLM, then:
result = session.run_compound_turn(AgentCompoundTurn(...))
state = session.snapshot()
```

**V0.4.2** ships [realm-studio](examples/web/realm-studio) on this API:

```powershell
cd examples\web\realm-studio
uv sync
uv run realm-studio
```

Multi-area pannable grid, token images (SVG/PNG), right-click create/edit/delete, **Manage actions…** on objects, **Prompt layout** (block reorder + section edit + slot ⚙), session **Units** for distance/move speed and action ranges, **Emit event…**, area dropdown, **Run turn** with input-token hover hint, and **Last prompt / Last response** debug panels (needs `OPENROUTER_API_KEY`). See [realm-studio README](examples/web/realm-studio/README.md) and [v0.4.2-changelog](docs/v0.4.2-changelog.md).

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
   uv sync
   uv run realm
  ```
   Or equivalently: `uv run python src/main.py`
   Few-shot examples are disabled by default for token efficiency. Use `--with-fewshots` to include compound turn examples.
   Inside the `(realm)` prompt you can:
  - `list` — overview of all agents and objects (no turn consumed)
  - `objects` — list all objects with ids and action names (for `edit-object` / `delete-object`)
  - `agents` — list all agents with ids and active marker
  - `effects` — list registered object interaction effects (`delete_self`, `random_move_self`, `move_area`, …)
  - `areas` — list areas in a multi-area session (* marks active edit scope)
  - `memory-modules` — list pluggable memory module ids (V0.2.5)
  - `state` — active agent context (memory module, turn count, compound step breakdown, few-shots)
  - `vision` — see what the active agent currently perceives
  - `prompt` — show the compound turn prompt for the active agent
  - `step-compound …` — manual compound turn (move / look / speak / interact)
  - `step-nav` / `step-action` — debug one phase without a full turn record (see `help`)
  - `run` — single compound LLM turn for the **active** agent (requires OPENROUTER_API_KEY)
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
create-object name "Crate" pdesc "A crate." desc "A wooden crate." appearance "tokens/crate.svg" at 0,0
create-object name "Cookie" pdesc "A cookie." desc "Tasty." at 2,2 action eat range 1 effect delete_self result "You ate the cookie." passive "{actor} ate the cookie."
create-object name "Door" pdesc "A door." desc "To the hall." at 1,1 action enter range 0 effect move_area dest-area hall dest-at 0,0 result "You walk through." passive "{actor} walks through to {actor_end_area}."
edit-object obj_sign_01 pdesc "A sign on the wall." desc "Updated sign text."
edit-object obj_ball_01 appearance "tokens/ball.svg" pos 3,3
edit-object obj_cookie_01 add-action smell range 1 result "Nice smell." passive "{actor} smells it."
edit-object obj_cookie_01 remove-action smell
delete-object obj_crate_01
create-agent name "Goblin" pdesc "A short figure." desc "A grumpy goblin." personality "You are a grumpy goblin." appearance "tokens/goblin.svg" move-speed 2 at 0,3
create-agent name "Archivist" personality "You remember everything." memory rolling_summary memory-summary-interval 15 memory-summary-tail 3 at 1,1
create-agent name "Scribe" personality "Quiet." memory salient_turns memory-budget 2500 at 2,2
edit-agent agent_01 desc "Updated detailed description."
edit-agent agent_01 appearance "tokens/explorer.svg"
edit-agent agent_01 personality "Updated LLM personality."
edit-agent agent_01 name "Scout"
delete-agent agent_goblin_01
```

The initial **ceramic ball** includes a built-in **`kick`** action (`range 1`, `random_move_self`). Result templates can use placeholders such as `{object}`, `{object_start}`, `{object_end}`, `{actor}`, `{actor_start_area}`, etc. (see `effects` / realm-studio **?** help). Example manual turn:

```
step-compound 2,3 interact obj_ball_01 kick
```

The old V0 `sign` command is removed. Update the sign with:

```
edit-object obj_sign_01 pdesc "A sign on the wall." desc "This is new text."
```

Objects and agents share **`pdesc`** (glance) and **`desc`** (detailed, hidden behind `[?]` until `look`). Agents also have **`personality`** — private LLM prompt text only, never shown in vision or revealed by `look`. Optional **`appearance`** is a client-only image path (realm-studio token art); the engine ignores it for gameplay. Other agents appear in passive vision; you do not see yourself. Stale examined knowledge shows as `[?] [changed] {pdesc}`.

### GM area events (V0.3.2)

Broadcast narrator/world text to every agent's memory without consuming a turn:

```
emit-event "Thunder rumbles overhead."
```

Events appear in agent **Memory:** on the next turn; realm-studio shows a **Recent events** sidebar and **Emit event…** button. Passive vision stays static (events are memory-only).

### Multi-area sessions (V0.4.0)

One session can hold multiple areas. Agents live in exactly one area; GM **active area** scopes create/edit/delete and **Emit event**. Compound turns (move, look, interact) use the agent's current area only.

```
areas
active-area hall
create-area id attic desc "A dusty attic." width 6 height 6
edit-area hall desc "A longer hall." width 8 height 4
delete-area attic
```

realm-studio: **Area** dropdown, **+ Area** / **Edit area** / **Delete area**; **Agents elsewhere** sidebar.

### Movement (V0.4.0)

- **`move_target`** — coordinate `"x,y"` **or** entity id (`obj_*`, `agent_*`) in the agent's current area
- **`move_speed`** — on agent; `None` (default) = teleport; `N` = up to N Chebyshev steps toward target
- CLI: `move-speed N` on `create-agent` / `edit-agent`; blank → unlimited

```
edit-agent agent_01 move-speed 2
step-compound obj_ball_01
```

### Prompt layout (V0.4.1)

Sessions assemble compound prompts from an ordered **block list** (`slot`, `text`, `section`) instead of a fixed template file. realm-studio **Prompt layout** sidebar: reorder blocks, edit static rules / output format, add/remove blocks, ⚙ toggles on Character / Passive vision / Move instructions.

Session **Units** + **Units per tile** (sidebar) feed relative bearing in passive vision and move-speed wording in move instructions.

Engine API: `Session.get_prompt_blocks()`, `Session.set_prompt_blocks()`, `Session.build_prompt()` uses blocks when set. See [v0.4.1-changelog](docs/v0.4.1-changelog.md).

### Compound turns (V0.4.4)

Pipeline per agent turn: **move → look → speak → turn action** (`interact` | `emote` | `none`).

- **Speak** — optional `say` field (independent of `action`); speak and interact/emote can combine in one turn
- **Emote** — `action: "emote"` with past-tense `verb` and optional `target` (entity id or free text)
- **Compact JSON** — `move`, `look`, `say`, `action`, `verb`, `target`, `reasoning` (legacy 0.4.3 keys still accepted on parse)

**Breaking (0.4.4):** LLM JSON uses compact keys; `move_target` / `look_target` / `content` / `turn_action` / `action_name` are normalized when parsing. See [v0.4.4-changelog](docs/v0.4.4-changelog.md).

### Multi-agent (V0.1 Section 3)

Typical LLM workflow with two agents (each `run` / agent name = **one compound LLM call** per turn):

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
- **`run`** — compound LLM turn for the **active** agent (use after `switch`)
- **`switch <name>`** — change active agent without a turn (`vision`, `state`, `prompt`, manual steps, `run`)
- **Typing an agent's name** — compound LLM turn for that agent; sets them active (even if the LLM call fails)
- Agent display names must be **unique** and **cannot match stepper commands** (e.g. `vision`, `run`, `list`, `create-agent`) — validated automatically via `src/stepper_commands.py`
- Commands are **case-insensitive** (`Run`, `Switch Goblin`, etc.)
- Deleting the active agent reassigns to the first remaining agent and prints `Active agent: …`
- Turn numbers in each agent's memory are **per-agent** (1, 2, 3…); `session_turn` in logs is a global session label only
- Other agents appear in passive vision (`pdesc` + hidden `desc` until `look`); `personality` is LLM-only; agents do not see themselves

### V0.2.5 (current — `0.2.5`)

See [changelog](docs/v0.2.5-changelog.md) for slice-by-slice detail.

**LLM & prompt**

- **One compound LLM call** per turn (`AgentCompoundTurn`) — move, look, and speak/interact planned together; execution order unchanged (move → look → turn action).
- Prompt order: character → **`Passive Vision:`** (position + visible entities) → rules → room → move bounds → look/interact lists → **`Memory:`**.
- Interact failures use in-world prose in turn results (no `ERR:` in memory); validation/off-grid move still use `ERR:*` for logging/retry.

**Memory modules**

- **`memory-modules`** — list registered modules and valid **create-agent** flags; default is **`recent_turns`** (last 10 own turns + witnessed actions).
- **`salient_turns`** — salience-weighted retention + char budget (`memory-budget` on create-agent).
- **`rolling_summary`** — verbatim detail + rolling LLM summary every **N** turns (default 10); keeps last **3** turns in detail after each summary; **background consolidation** gates the next turn until merge succeeds; optional **`memory-summary-interval`**, **`memory-summary-max`**, **`memory-summary-tail`**.
- Module id set **only at `create-agent`**.
- **`state`** shows module-specific config; for `rolling_summary` includes consolidation state and detail turn numbers.
- **Code layout:** `src/memory_modules/` — module implementations, `formatting/` (common / salient / summary render helpers), `consolidation_runner.py` (async merge for `rolling_summary`).

### V0.2 (`v0.2.0`)

| Area | V0.1 (`v0.1.0`) | V0.2 (`v0.2.0`) | V0.2.5 (`0.2.5`) |
|------|-----------------|-----------------|------------------|
| Move | Cardinal one step (`north`, …) | Coordinate move to `"x,y"` on 0–4 grid | Same as V0.2 |
| LLM turn | One call, one action (`AgentTurn`) | Two calls: nav + action | **One compound call** |
| Memory | Fixed 10 turns on agent | Same as V0.1 | Pluggable modules (`recent_turns`, …) |
| Turn shape | Move, look, or speak — one per turn | Optional move → optional one look → speak **or** interact | Same execution; single plan |
| Manual step | `step move\|look\|speak` | `step-compound` (+ optional `step-nav` / `step-action`) | Same as V0.2 |
| Objects | Look only | Declarative **interact** + effects | Same + in-world interact errors |
| Speak limit | 280 characters | 500 characters (5 sentences unchanged) | Same as V0.2 |

**Unchanged from V0.1:** 5×5 grid, manual human control (`switch`, `run`, typing agent names), world editing, multi-agent passive vision. GUI → **V0.3** (after V0.2.5 memory).

See [V0.2 checklist](docs/v0.2-implementation-readiness-checklist.md) for the full spec.

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

# Then run the program (either form works after uv sync)
uv run realm
# or: uv run python src/main.py
```

### Without any .env file

You can still use almost everything:

- All the manual commands (`step-compound`, `vision`, `state`, etc.) work perfectly.
- The only thing that requires an `OPENROUTER_API_KEY` is an LLM turn: type an agent's name (e.g. `Explorer`) or use `run` after selecting the active agent. Each turn makes **one** compound LLM call (plus an extra **memory summary** call on interval boundaries for `rolling_summary` agents).

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

Tests use [pytest](https://docs.pytest.org/) and run **without** an API key or network access. There are **two separate pytest projects**:

| Suite | Where to run | Count | What it covers |
|-------|----------------|-------|----------------|
| **Engine** | Repo root (`uv run pytest`) | **415** | `tests/` — perception, prompt tokens, emote, prompt blocks, Session API, snapshots, etc. |
| **realm-studio** | `examples/web/realm-studio` (`uv run pytest`) | **49** | HTTP smoke — health, multi-area state, prompt blocks, vision units, areas CRUD, object actions, events, turn, debug panels |

Root `pyproject.toml` sets `testpaths = ["tests"]` only. The example app has its own `pyproject.toml` and does **not** get picked up when you run pytest from the repo root.

### Run engine tests

From the project folder:

```powershell
uv run pytest
```

By default this runs quietly (`-q` is set in `pyproject.toml`). You should see a final `passed` summary when everything is green.

### Run realm-studio tests

```powershell
cd examples\web\realm-studio
uv sync
uv run pytest
```

See [realm-studio README](examples/web/realm-studio/README.md#tests) for details. `test_api.py` mocks the LLM — no running server or API key required.

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
| `tests/test_schema.py` | `AgentCompoundTurn` Pydantic validation, sentence truncation |
| `tests/test_text_truncation.py` | Sentence-boundary truncation helper (V0.4.1a) |
| `tests/test_prompt_blocks.py` | Prompt block model, slot settings, render order (V0.4.1b–c+) |
| `tests/test_vision_bearing.py` | Relative compass + distance phrases (V0.4.1c+) |
| `tests/test_packaging.py` | `pyproject.toml` version, `realm_fabric` public imports, wheel layout |
| `tests/test_stepper.py` | ManualStepper intro, help, state, compound turn logging |
| `tests/test_llm_client.py` | LLM parse errors (`ERR:INVALID_JSON`, etc.) |
| `tests/test_coordinate_move.py` | Coordinate move parser, bounds, schema |
| `tests/test_move_target.py` | Entity id as move target (V0.4.0a) |
| `tests/test_move_pathing.py` | `move_speed`, Chebyshev pathing, towards/reached wording (V0.4.0b) |
| `tests/test_compound_turn.py` | Compound orchestration, speak step, `TurnRecord.steps`, step-compound parser |
| `tests/test_emote.py` | Emote turn action, witness phrasing (V0.4.2) |
| `tests/test_observations.py` | Multi-step witness broadcast (V0.4.3) |
| `tests/test_token_estimate.py` | Prompt token estimate helper (V0.4.2) |
| `tests/test_prompt_tokens.py` | Default prompt token budget regression (V0.4.4) |
| `tests/test_object_actions.py` | Effect registry, interact range/vision, `delete_self`, ball `kick` |
| `tests/test_move_area_effect.py` | `move_area` effect, cross-area transfer (V0.4.0d) |
| `tests/test_interact_templates.py` | Result/passive template placeholders |
| `tests/test_session_multi_area.py` | Multi-area `Session`, transfer, snapshot |
| `tests/test_session_area_edit.py` | Area CRUD CLI |
| `tests/test_area.py` | Initial demo area, grid rules, passive vision baseline |
| `tests/test_area_config.py` | Configurable grid bounds and `area_description` |
| `tests/test_session.py` | Session API — turns, commands, active agent, `build_prompt` |
| `tests/test_session_snapshot.py` | `Session.snapshot()` JSON shape, privacy, post-turn state |
| `tests/test_game_profile.py` | `GameProfile`, `PromptTemplate`, default profile parity |
| `tests/test_simulation.py` | Compound turns, memory side effects, prompts |
| `tests/test_perception.py` | V0.1 `[?]` / stale vision for objects and cross-agent invalidation |
| `tests/test_area_edit.py` | Area editing commands (create/edit/delete, listings, object actions, `appearance`) |
| `tests/test_area_events.py` | GM area events (`emit_area_event`, memory ingest, snapshot `recent_events`) |
| `tests/test_multi_agent.py` | Multi-agent stepper (`switch`, `run`, agent vision, `passive_result`, LLM mocks) |
| `tests/test_memory_modules.py` | Pluggable memory modules, registry, witnesses, `get_detail_turns` |
| `tests/test_salient_turns.py` | Salience scoring, char budget, fragment render |
| `tests/test_rolling_summary.py` | Rolling summary, async consolidation, detail tail, gating |

### First-time setup

`uv sync` installs pytest via the `dev` dependency group. If pytest is missing:

```powershell
uv sync
uv run pytest -v
```

