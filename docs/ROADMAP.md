# Realm-Fabric Roadmap

This document outlines concrete plans for versions after V0.

See also [LONG_TERM_GOALS.md](../LONG_TERM_GOALS.md) for larger aspirational / dream goals that are not yet tied to specific versions.

These plans are subject to change as we learn and discuss.

## V0.1

**Status:** ✅ **Implemented** — tag `v0.1.0`; see [v0.1-implementation-readiness-checklist.md](v0.1-implementation-readiness-checklist.md).

**Focus:** Make the world dynamic with general editing tools and improved perception for changes, then add multi-agent support. Everything remains fully manual (human decides which agent acts when by typing its name, using `run` for the active agent, or using `switch` to inspect another agent without a turn). The initial world still starts with a single "Explorer" agent, ball, and sign.

**Implementation order:** (1) generalized stale perception → (2) editing commands + perception extension → (3) multi-agent support.

### 1. Generalize the "has changed" notification — ✅ Implemented
- Removed all sign-specific special cases in `perception.py`.
- Added `ever_looked` tracking on `Memory` to distinguish never examined from stale examined knowledge.
- Stale vision: **`[?] [changed] {passive}`** (or `[?] [changed]` if no passive line). Never-examined with hidden detail: `[?]` or `[?] {passive}`.
- Any change to an entity's **detailed** description (`desc` on objects or agents) calls `World.invalidate_entity_knowledge(id)` on all agents with current knowledge.
- Name, position, or **passive** (`pdesc`) edits do **not** invalidate look knowledge.
- Few-shot examples and system rules updated in `prompt.py`.
- The `sign` command removed; use `edit-object obj_sign_01 desc "..."` (and optional `pdesc`).

### 2. General editing commands (objects + agents) — ✅ Implemented
- Keyword-style stepper commands (`create-object`, `edit-object`, `delete-object`, `create-agent`, `edit-agent`, `delete-agent`), parsed with `shlex.split`.
- Objects support **`pdesc`** (passive glance) and **`desc`** (detailed, hidden behind `[?]` until examined).
- **Listing commands** (read-only, no turn consumed): `list` (everything), `objects` (all objects), `agents` (all agents with ids and active marker). Primary way to look up ids for edit/delete without running a turn or viewing a prompt.
- **ID rules:** auto-generated per category (`obj_{slug}_01`, `agent_{slug}_01`); immutable after creation. Object display names may duplicate; agent display names must be unique among agents (case-insensitive) and cannot match stepper commands (validated via `src/stepper_commands.py`). Objects and agents may share a display name with each other.
- **Edit/delete** commands take entity **id**, not display name.
- Editing an object's or agent's **`desc`** triggers generalized "has changed" invalidation (per item 1). **`personality`** edits do not invalidate look knowledge.
- Agents support **`pdesc`**, **`desc`** (observable; same `[?]` rules as objects), and **`personality`** (private LLM prompt only).
- Agent edits affect name, `pdesc`, `desc`, `personality`, or position — per-agent memory and turn history are untouched.
- `create-agent` does not change the active agent.
- The default initial world keeps the same layout (Explorer + ball + sign) but Explorer uses the three-layer agent text model (`pdesc` / `desc` / `personality`); all runtime changes happen via stepper commands.
- Keep the experience fully manual (no automatic sequencing of agent turns).

### 3. Multi-agent support — ✅ Implemented
- Each agent has its own independent `Memory` (own turn history, own `looked_at` / `ever_looked`, own position).
- Typing an agent's name (e.g. `Explorer` or `Goblin`) gives *that agent* an **LLM turn** — build prompt, execute action, update only that agent, set as active (active is set at start of the LLM path so `vision`/`state` match even if the call fails).
- **`run`** runs an LLM turn for the **active** agent (typical workflow: `switch Goblin` then `run`).
- **`switch <name>`** changes the active agent without a turn or LLM call (for `vision`, `state`, `prompt`, manual `step`, `run`).
- Stepper commands are case-insensitive (`Run` = `run`). Deleting the active agent falls back to `world.agents[0]` and prints the new active agent.
- `vision`, `state`, `prompt`, manual `step`, etc. operate on the active agent.
- **Per-agent turn numbers** in `TurnRecord` (no gaps when agents alternate); `session_turn` is a console/log label only and increments after successful `step_turn`.
- Add `World.get_agents()`, `get_agent_by_id()`, `get_agent_by_name()`; keep `get_agent()` as first agent for backward compatibility.
- Agents share the same world grid and objects. **Other agents appear in passive vision** (`pdesc` + hidden `desc` until `look`; `personality` is LLM-only). You do not see yourself.
- **`look`** works on other agents (`agent_*` ids) as well as objects. **`passive_result`** shows each agent's most recent observable action to others (speech, movement, examination), with optional confidence/emotion appended.
- No speak **targeting** (agents broadcast speech to the room), no relationships, no automatic turn sequencing, and no agent-initiated world edits.
- Additional agents are introduced via editing commands from item 2.

These changes improve experimentation while keeping the core "one structured action per LLM call per agent" model that was validated in V0.

## V0.2

**Status:** ✅ **Implemented** — tag **`v0.2.0`**; see [v0.2-implementation-readiness-checklist.md](v0.2-implementation-readiness-checklist.md).

**Focus:** D&D-shaped compound turns (move anywhere, then look and take one action in the same round) and the first **declarative object interact** behaviors — without the full memory subsystem (deferred to V0.2.5). Builds on V0.1 multi-agent observation and manual control.

**Implementation order (complete):** (1) coordinate-based move → (2) compound turns (two-phase LLM) → (3) custom object actions → (4) cross-cutting integration and release.

### 1. Coordinate-based move — ✅ Implemented
- **Replace** cardinal one-step move with **coordinate targeting** — canonical `"x,y"` (e.g. `2,3`); parser silently accepts `"(x,y)"` variants.
- Move to in-bounds tile on the 5×5 grid; same-tile move succeeds with no `passive_result` update.
- **Remove** `north` / `east` / `south` / `west` entirely (breaking change).
- Single `move()` entry point in `src/actions/move.py` for simulation, stepper, and future pathing.
- Updated prompts, few-shots, `passive_result` strings, and manual step parity.

### 2. Compound agent turns — ✅ Implemented
- One agent turn: **navigation LLM** → optional move → **action LLM** → optional one look → optional one turn action (`speak` or `interact`).
- **Always two LLM calls** per `run` / typing an agent name; nav parse failure aborts the whole turn (no `session_turn` increment).
- **Schemas:** `AgentNavigationTurn` (`move_target`) + `AgentActionTurn` (`look_target`, `turn_action`, interact fields). **`AgentTurn` removed** from the LLM path.
- **TurnRecord:** `steps[]`, `nav_reasoning`, `action_reasoning`, composite `result` (legacy flat fields removed).
- **`passive_result`:** one line; priority **turn action > look > move**; mood suffix from action phase only. Other agents see end-of-turn snapshot only.
- **Manual:** `step-compound` replaces `step move|look|speak`; optional `step-nav` / `step-action` for debug.
- **Speak limit:** 500 characters (5 sentences unchanged).
- V0.1 memory unchanged (10 turns, `looked_at`, single `passive_result`); compound `TurnRecord.steps` are hooks for V0.2.5.

### 3. Custom object actions (declarative interact) — ✅ Implemented
- `Object.actions: dict[str, ObjectAction]` — name, Chebyshev **range**, `result` / `passive_result` templates (`{actor}`, `{object}`), ordered **effects** list.
- **Effect registry** (e.g. `src/object_effects.py`); V0.2 ships **`delete_self`** and **`random_move_self`**; **`effects: []`** allowed for result-only interacts. Initial ball has **`kick`** → `random_move_self`.
- Listed in the **action-phase** prompt when object is in passive vision and in range (post-move position).
- World edit: `action` / `range` / `effect` / `result` / `passive` on `create-object`; `add-action` / `remove-action` on `edit-object`.
- Read-only **`effects`** command lists registered effect names (like `objects` / `agents`).
- On object removal (`delete_self`, `delete-object`): purge id from all agents' `looked_at` / `ever_looked`.

### 4. Cross-cutting (integration) — ✅ Implemented
- **`ERR:*` codes** including `INVALID_COORDINATES`, `INVALID_JSON`, interact codes; no hard prompt truncation in V0.2.
- Logging: `Turn N [nav]` and `Turn N [action]` with prompt char counts in file logs; `state` shows step breakdown.
- Tests: `test_coordinate_move.py`, `test_compound_turn.py`, `test_object_actions.py`, `test_v0_2_ship.py` + updates to existing suite.
- Release **`v0.2.0`** — `pyproject.toml` version bump, docs synced.

**Explicitly out of V0.2:** memory manager, beliefs/goals database, pluggable memory modules, heard-dialogue buffers, persistence — delivered in **V0.2.5**. Pathing, blockers, speak targeting, relationships, automatic turn sequencing, GUI (V0.3).

## V0.2.5

**Status:** **0.2.5e** implemented in code (`0.2.5`); **0.2.5f** refactor planned — see [v0.2.5-changelog.md](v0.2.5-changelog.md).

**Focus:** Memory as a first-class subsystem — required before V0.3. **Pluggable memory modules** per agent (`recent_turns`, `salient_turns`, … via `create-agent memory`) replace a separate “tiered policy” layer — e.g. a minion can use `salient_turns` with a low budget, a PC can use `recent_turns` or a richer module later.

### 0.2.5a — Single LLM compound turn — ✅ Implemented
- One LLM call per agent turn via `AgentCompoundTurn` (replaces two-phase nav + action schemas).
- Single `build_compound_prompt()` / `get_compound_turn()`; logging phase `[compound]`.
- Turn execution unchanged (move → look → turn action); `TurnRecord.reasoning` replaces split nav/action reasoning.
- Pre-move vision in prompt; model plans post-move look/action (5×5 tradeoff documented in changelog).
- `pyproject.toml` → `0.2.5`; tests updated.

### 0.2.5b — Pluggable memory modules — ✅ Implemented
- `memory_modules/` package with `MemoryModule` protocol and **`recent_turns`** default module.
- `Memory` facade: look knowledge + `record_turn` / `record_observation` / `render_prompt_block`.
- **`Memory:`** prompt section; witnessed other-agent `passive_result` ingested on turn commit.
- **`create-agent memory MODULE_ID`** selects module at creation; **`edit-agent` does not support memory** (fixed for agent lifetime).
- **`memory-modules`** command; agent listings show `memory=<id>`.

### 0.2.5c — Salient turns memory module — ✅ Implemented
- **`salient_turns`** module: same ingest as `recent_turns`; salience-weighted storage (50-turn cap); char-budget render (default 2500).
- **`create-agent memory salient_turns memory-budget N`** (200–8000); budget-only implies salient; **`recent_turns` remains default**.
- Shared `formatting.py` for module render output; `tests/test_salient_turns.py`.
- **Render/scoring refined in 0.2.5d** — step-level salience and condensed turn format (see changelog).

### 0.2.5d — Condensed memory & prompt look fixes — ✅ Implemented
- **Both modules:** turn render is `Turn N` + optional `Reasoning:` (newest 3 only) + `Result:` — no per-step duplicate lines.
- **`recent_turns`:** always full composite `Result:`.
- **`salient_turns`:** step-fragment `Result:` (speak 10 / interact 7 / look 3 / move 1); older turns drop move/look; witness blocks at speak tier in budget selection.
- **Prompt:** look rule points at provided list; **`You can look at:`** lists **`[?]`** entities only.
- **Interact templates:** `{start}` / `{end}` for object position before/after effects (ball kick).

### 0.2.5e — Rolling summary memory module — ✅ Implemented
- **`rolling_summary`:** verbatim detail (tail + turns since last consolidation) + **`Summary:`** block from periodic LLM merge.
- Defaults: **interval 10**, **max 8000** chars, **detail tail 3** (tail kept in prompt, excluded from next merge).
- **`create-agent memory rolling_summary`** + optional **`memory-summary-interval`** / **`memory-summary-max`** / **`memory-summary-tail`**.
- **Background consolidation** with turn gating (`TurnGatedMemoryModule`); sync retry on failure; **`MemoryConsolidationError`** if retry fails.
- Extra LLM call per agent on each interval (`src/llm/memory_summary.py`, plain text); logged as **`[memory_summary]`**.
- Facade: **`get_detail_turns()`**; **`stored_turns`** is detail buffer only for this module (summary is separate).

### 0.2.5f — Memory module refactor — Planned
- Extract **`ConsolidationRunner`** from `RollingSummaryModule` (threading/state machine).
- Split **`formatting.py`** into common / salient / summary helpers.

### Planned themes (high level, after 0.2.5f)
- **Persistent memory store** (database): memories with IDs, priorities, and types; serializable for save/load later.
- **Goals and tasks** linked to memory IDs (feeds LONG_TERM_GOALS “beliefs, relationships, goals, pursuit”).
- **Richer consolidation** into the store (beyond the single rolling summary string in `rolling_summary`).
- **Prompt assembler** reads from the store under token budget.
- **New memory modules** as needed (same `MemoryModule` protocol; per-agent module choice replaces archetype-tier policies).

V0.2 compound turns and object interact should log in a shape that V0.2.5 can ingest without rework.

## V0.3

**Focus:** Basic graphical user interface for visualization and direct interaction. Prepares the data model for visual rendering. **Depends on V0.2.5 memory** being in place first.

- **GUI**:
  - A clickable grid view of the world.
  - Clicking on a tile opens a context menu.
  - The menu allows running commands on that tile/location (e.g. create object/agent here, edit nearby entities, inspect, delete, move things, etc.).
  - The GUI will coexist with (or augment) the existing ManualStepper for LLM/agent turns and logging.

- **Image / rendering support**:
  - `Object` and `Agent` dataclasses will gain a new field (e.g. `image: Optional[str] = None` or similar) to specify an image, sprite path, or asset identifier.
  - This field will be used by the GUI to draw the entity on its tile.
  - Core logic (perception, actions, memory, prompts) will ignore the image field for now (it is purely for visualization).
  - Initial world and editing commands will support setting the image field.

Larger items (richer agent interactions, object behaviors, full D&D-style systems, Roll20 integration, lorebooks, etc.) remain in LONG_TERM_GOALS.md and can be pulled into specific versions when we decide they are ready.

---

**Notes**
- Prefer adding sections to the [V0.2.5 changelog](v0.2.5-changelog.md) over a readiness checklist for V0.2.5+.
- When a version is **implemented**, move relevant items to "Achieved" in LONG_TERM_GOALS.md and update this roadmap.
- This document is meant to be living — edit it as plans evolve.
