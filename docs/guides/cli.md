# Realm CLI reference

Interactive tester: `uv run realm` (or `uv run python src/main.py`). Prompt: `(realm)`.

**For application development**, use the [typed Session API](building-on-realm-fabric.md) instead of assembling CLI strings in code. This reference is for **debugging and GM tooling**.

See [documentation hub](../README.md).

Commands are **case-insensitive**. World-editing commands do **not** consume a turn.

## Session & agents

| Command | Description |
|---------|-------------|
| `list` | Overview of agents and objects |
| `objects` / `agents` / `areas` | List ids (for edit commands) |
| `state` | Active agent context, memory module, last turn steps |
| `vision` | What the active agent perceives |
| `prompt` | Compound prompt for the active agent |
| `switch <name>` | Change active agent (no turn) |
| `run` | LLM compound turn for active agent |
| `<AgentName>` | LLM turn for that agent (sets active) |
| `export-session <path>` | Save full session JSON |
| `import-session <path>` | Load session JSON |
| `fewshots on/off` | Toggle few-shot examples in prompts |
| `quit` | Exit |

## Memory modules

| Command | Description |
|---------|-------------|
| `memory-modules` | List loaded modules (built-ins + customs) |
| `add-memory-module <path>` | Load a custom `.py` module for this process |

Built-in ids: `recent_turns`, `salient_turns`, `rolling_summary`. Create-agent uses only **loaded** modules.

Custom module contract: [examples/custom_memory/README.md](../examples/custom_memory/README.md).

## Lorebooks

| Command | Description |
|---------|-------------|
| `load-lorebook <path>` | Load a SillyTavern `.json` lorebook into the session |
| `lorebooks` | List loaded lorebooks |

Add a `lorebook` prompt block in realm-studio Prompt layout (or custom `prompt_blocks`) to inject matched entries.

## World editing

```
create-object name "Crate" pdesc "A crate." desc "Wooden." at 0,0
create-object name "Table" pdesc "A large table." at 1,1 width 2 height 2 blocks-movement true
create-object name "Trap" pdesc "Hidden." at 2,2 hidden true blocks-movement false
create-object name "Door" pdesc "A door." at 1,1 action enter range 0 handler move_area dest-area hall dest-at 0,0 result "You walk through." passive "{actor} walks through."
edit-object obj_sign_01 desc "New sign text."
edit-object obj_table_01 width 3 height 1
edit-object obj_trap_01 hidden false
edit-object obj_trap_01 add-action trip range 0 kind trigger halt-movement true delete-after-trigger false handler delete_self result "(trigger)" passive "{actor} steps on the trap."
delete-object obj_crate_01

create-area id attic desc "A dusty attic." width 6 height 6
edit-area hall desc "Longer hall." width 8 height 4
delete-area attic
active-area hall

create-agent name "Goblin" personality "Grumpy." move-speed 2 at 0,3
create-agent name "Player" personality "You." player true at 1,1
create-agent name "Archivist" personality "Remembers." memory rolling_summary memory-summary-interval 15 at 1,1
create-agent name "Scribe" personality "Quiet." memory salient_turns memory-budget 2500 at 2,2
edit-agent agent_01 personality "Updated."
delete-agent agent_goblin_01
```

Object actions support template placeholders (`{actor}`, `{object}`, …). Trigger actions use `kind trigger` and fire on path steps (area event from `passive`). Handlers use `handler <id>` (e.g. `handler delete_self`, `handler move_area dest-area hall dest-at 0,0`). List registered handlers with `handlers`. See `examples/reference_handlers/` or realm-studio **Manage actions…** help.

**`private_data`** on agents/objects is snapshot-only (custom apps); not set via CLI.

## Turns

```
step-compound 2,3 look obj_ball_01 speak Hello.
step-compound interact obj_ball_01 kick
emit-event "Thunder rumbles overhead."
```

Pipeline: **move → look → speak → turn action** (`interact` | `emote` | `none`).

## Flags

```powershell
uv run realm --with-fewshots   # include few-shot examples
uv run realm --log             # turn logging
```

## Environment

Set `OPENROUTER_API_KEY` in `.env` (see [`.env.example`](../.env.example)) for `run` and agent-name LLM turns. Optional `OPENROUTER_MODEL`.
