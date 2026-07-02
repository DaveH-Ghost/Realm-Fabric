# Realm-Fabric Roadmap

This document outlines concrete plans for versions after V0.

See also [LONG_TERM_GOALS.md](../LONG_TERM_GOALS.md) for larger aspirational / dream goals that are not yet tied to specific versions.

These plans are subject to change as we learn and discuss.

## V0.1

**Status:** ✅ **Implemented** — tag `v0.1.0`; see [v0.1-implementation-readiness-checklist.md](changelog/v0.1-implementation-readiness-checklist.md).

**Focus:** Make the world dynamic with general editing tools and improved perception for changes, then add multi-agent support. Everything remains fully manual (human decides which agent acts when by typing its name, using `run` for the active agent, or using `switch` to inspect another agent without a turn). The initial world still starts with a single "Explorer" agent, ball, and sign.

**Implementation order:** (1) generalized stale perception → (2) editing commands + perception extension → (3) multi-agent support.

### 1. Generalize the "has changed" notification — ✅ Implemented

- Removed all sign-specific special cases in `perception.py`.
- Added `ever_looked` tracking on `Memory` to distinguish never examined from stale examined knowledge.
- Stale vision: `**[?] [changed] {passive}`** (or `[?] [changed]` if no passive line). Never-examined with hidden detail: `[?]` or `[?] {passive}`.
- Any change to an entity's **detailed** description (`desc` on objects or agents) calls `World.invalidate_entity_knowledge(id)` on all agents with current knowledge.
- Name, position, or **passive** (`pdesc`) edits do **not** invalidate look knowledge.
- Few-shot examples and system rules updated in `prompt.py`.
- The `sign` command removed; use `edit-object obj_sign_01 desc "..."` (and optional `pdesc`).

### 2. General editing commands (objects + agents) — ✅ Implemented

- Keyword-style stepper commands (`create-object`, `edit-object`, `delete-object`, `create-agent`, `edit-agent`, `delete-agent`), parsed with `shlex.split`.
- Objects support `**pdesc`** (passive glance) and `**desc**` (detailed, hidden behind `[?]` until examined).
- **Listing commands** (read-only, no turn consumed): `list` (everything), `objects` (all objects), `agents` (all agents with ids and active marker). Primary way to look up ids for edit/delete without running a turn or viewing a prompt.
- **ID rules:** auto-generated per category (`obj_{slug}_01`, `agent_{slug}_01`); immutable after creation. Object display names may duplicate; agent display names must be unique among agents (case-insensitive) and cannot match stepper commands (validated via `src/stepper_commands.py`). Objects and agents may share a display name with each other.
- **Edit/delete** commands take entity **id**, not display name.
- Editing an object's or agent's `**desc`** triggers generalized "has changed" invalidation (per item 1). `**personality**` edits do not invalidate look knowledge.
- Agents support `**pdesc**`, `**desc**` (observable; same `[?]` rules as objects), and `**personality**` (private LLM prompt only).
- Agent edits affect name, `pdesc`, `desc`, `personality`, or position — per-agent memory and turn history are untouched.
- `create-agent` does not change the active agent.
- The default initial world keeps the same layout (Explorer + ball + sign) but Explorer uses the three-layer agent text model (`pdesc` / `desc` / `personality`); all runtime changes happen via stepper commands.
- Keep the experience fully manual (no automatic sequencing of agent turns).

### 3. Multi-agent support — ✅ Implemented

- Each agent has its own independent `Memory` (own turn history, own `looked_at` / `ever_looked`, own position).
- Typing an agent's name (e.g. `Explorer` or `Goblin`) gives *that agent* an **LLM turn** — build prompt, execute action, update only that agent, set as active (active is set at start of the LLM path so `vision`/`state` match even if the call fails).
- `**run*`* runs an LLM turn for the **active** agent (typical workflow: `switch Goblin` then `run`).
- `**switch <name>`** changes the active agent without a turn or LLM call (for `vision`, `state`, `prompt`, manual `step`, `run`).
- Stepper commands are case-insensitive (`Run` = `run`). Deleting the active agent falls back to `world.agents[0]` and prints the new active agent.
- `vision`, `state`, `prompt`, manual `step`, etc. operate on the active agent.
- **Per-agent turn numbers** in `TurnRecord` (no gaps when agents alternate); `session_turn` is a console/log label only and increments after successful `step_turn`.
- Add `World.get_agents()`, `get_agent_by_id()`, `get_agent_by_name()`; keep `get_agent()` as first agent for backward compatibility.
- Agents share the same world grid and objects. **Other agents appear in passive vision** (`pdesc` + hidden `desc` until `look`; `personality` is LLM-only). You do not see yourself.
- `**look`** works on other agents (`agent_*` ids) as well as objects. `**passive_result**` shows each agent's most recent observable action to others (speech, movement, examination, emotes).
- No speak **targeting** (agents broadcast speech to the room), no relationships, no automatic turn sequencing, and no agent-initiated world edits.
- Additional agents are introduced via editing commands from item 2.

These changes improve experimentation while keeping the core "one structured action per LLM call per agent" model that was validated in V0.

## V0.2

**Status:** ✅ **Implemented** — tag `**v0.2.0`**; see [v0.2-implementation-readiness-checklist.md](changelog/v0.2-implementation-readiness-checklist.md).

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
- **Schemas:** `AgentNavigationTurn` (`move_target`) + `AgentActionTurn` (`look_target`, `turn_action`, interact fields). `**AgentTurn` removed** from the LLM path.
- **TurnRecord:** `steps[]`, `nav_reasoning`, `action_reasoning`, composite `result` (legacy flat fields removed).
- `**passive_result`:** one line; priority **turn action > look > move**; mood suffix from action phase only. Other agents see end-of-turn snapshot only.
- **Manual:** `step-compound` replaces `step move|look|speak`; optional `step-nav` / `step-action` for debug.
- **Speak limit:** 500 characters (5 sentences unchanged).
- V0.1 memory unchanged (10 turns, `looked_at`, single `passive_result`); compound `TurnRecord.steps` are hooks for V0.2.5.

### 3. Custom object actions (declarative interact) — ✅ Implemented

- `Object.actions: dict[str, ObjectAction]` — name, Chebyshev **range**, `result` / `passive_result` templates (`{actor}`, `{object}`), ordered **effects** list.
- **Effect registry** (e.g. `src/object_effects.py`); V0.2 ships `**delete_self`** and `**random_move_self**`; `**effects: []**` allowed for result-only interacts. Initial ball has `**kick**` → `random_move_self`.
- Listed in the **action-phase** prompt when object is in passive vision and in range (post-move position).
- World edit: `action` / `range` / `effect` / `result` / `passive` on `create-object`; `add-action` / `remove-action` on `edit-object`.
- Read-only `**effects`** command lists registered effect names (like `objects` / `agents`).
- On object removal (`delete_self`, `delete-object`): purge id from all agents' `looked_at` / `ever_looked`.

### 4. Cross-cutting (integration) — ✅ Implemented

- `**ERR:*` codes** including `INVALID_COORDINATES`, `INVALID_JSON`, interact codes; no hard prompt truncation in V0.2.
- Logging: `Turn N [nav]` and `Turn N [action]` with prompt char counts in file logs; `state` shows step breakdown.
- Tests: `test_coordinate_move.py`, `test_compound_turn.py`, `test_object_actions.py`, `test_stepper.py`, `test_llm_client.py`, `test_packaging.py` + updates to existing suite.
- Release `**v0.2.0`** — `pyproject.toml` version bump, docs synced.

**Explicitly out of V0.2:** memory manager, beliefs/goals database, pluggable memory modules, heard-dialogue buffers, persistence — delivered in **V0.2.5**. Pathing, blockers, speak targeting, relationships, automatic turn sequencing, GUI (V0.3).

## V0.2.5

**Status:** ✅ **Release-ready** — all slices **0.2.5a–g** implemented (`pyproject.toml` → `0.2.5`); tag `**v0.2.5`** pending — see [v0.2.5-changelog.md](changelog/v0.2.5-changelog.md) (includes ship checklist).

**Focus:** Memory as a first-class subsystem — required before V0.3. **Pluggable memory modules** per agent (`recent_turns`, `salient_turns`, … via `create-agent memory`) replace a separate “tiered policy” layer — e.g. a minion can use `salient_turns` with a low budget, a PC can use `recent_turns` or a richer module later.

### 0.2.5a — Single LLM compound turn — ✅ Implemented

- One LLM call per agent turn via `AgentCompoundTurn` (replaces two-phase nav + action schemas).
- Single `build_compound_prompt()` / `get_compound_turn()`; logging phase `[compound]`.
- Turn execution unchanged (move → look → turn action); `TurnRecord.reasoning` replaces split nav/action reasoning.
- Pre-move vision in prompt; model plans post-move look/action (5×5 tradeoff documented in changelog).
- `pyproject.toml` → `0.2.5`; tests updated.

### 0.2.5b — Pluggable memory modules — ✅ Implemented

- `memory_modules/` package with `MemoryModule` protocol and `**recent_turns`** default module.
- `Memory` facade: look knowledge + `record_turn` / `record_observation` / `render_prompt_block`.
- `**Memory:**` prompt section; witnessed other-agent `passive_result` ingested on turn commit.
- `**create-agent memory MODULE_ID**` selects module at creation; `**edit-agent` does not support memory** (fixed for agent lifetime).
- `**memory-modules`** command; agent listings show `memory=<id>`.

### 0.2.5c — Salient turns memory module — ✅ Implemented

- `**salient_turns**` module: same ingest as `recent_turns`; salience-weighted storage (50-turn cap); char-budget render (default 2500).
- `**create-agent memory salient_turns memory-budget N**` (200–8000); budget-only implies salient; `**recent_turns` remains default**.
- Shared `memory_modules/formatting/` for module render output; `tests/test_salient_turns.py`.
- **Render/scoring refined in 0.2.5d** — step-level salience and condensed turn format (see changelog).

### 0.2.5d — Condensed memory & prompt look fixes — ✅ Implemented

- **Both modules:** turn render is `Turn N` + optional `Reasoning:` (newest 3 only) + `Result:` — no per-step duplicate lines.
- `**recent_turns`:** always full composite `Result:`.
- `**salient_turns`:** step-fragment `Result:` (speak 10 / interact 7 / look 3 / move 1); older turns drop move/look; witness blocks at speak tier in budget selection.
- **Prompt:** look rule points at provided list; `**You can look at:`** lists `**[?]**` entities only.
- **Interact templates:** `{object_start}` / `{object_end}` for object position before/after effects; `{actor_start}` / `{actor_end}` and area ids for cross-area transfers (ball kick, doors).

### 0.2.5e — Rolling summary memory module — ✅ Implemented

- `**rolling_summary`:** verbatim detail (tail + turns since last consolidation) + `**Summary:`** block from periodic LLM merge.
- Defaults: **interval 10**, **max 8000** chars, **detail tail 3** (tail kept in prompt, excluded from next merge).
- `**create-agent memory rolling_summary`** + optional `**memory-summary-interval**` / `**memory-summary-max**` / `**memory-summary-tail**`.
- **Background consolidation** with turn gating (`TurnGatedMemoryModule` + `ConsolidationRunner` in **0.2.5f**); sync retry on failure; `**MemoryConsolidationError`** if retry fails.
- Extra LLM call per agent on each interval (`src/llm/memory_summary.py`, plain text); logged as `**[memory_summary]**`.
- Facade: `**get_detail_turns()**`; `**stored_turns**` is detail buffer only for this module (summary is separate).

### 0.2.5f — Memory module refactor — ✅ Implemented

- `**formatting/` package** — split `common` / `salient` / `summary` helpers; no behavior change.
- `**ConsolidationRunner`** (`consolidation_runner.py`) — threading, state machine, snapshot wait/retry extracted from `RollingSummaryModule`; `MemoryConsolidationError` lives there (re-exported from `rolling_summary`).

### 0.2.5g — Release polish — ✅ Implemented

- `**Passive Vision:**` section first in compound prompt (after character); duplicate position line removed from move block.
- In-world interact failure messages in turn results (no `ERR:` in memory).
- Adjacency interact rule in prompt; few-shot examples updated.
- [LONG_TERM_GOALS.md](../LONG_TERM_GOALS.md) **Planned Goals**: coordinate move + target move for future pathing.

### Planned themes (high level, after 0.2.5g)

- **Persistent memory store** (database): memories with IDs, priorities, and types; serializable for save/load later.
- **Goals and tasks** linked to memory IDs (feeds LONG_TERM_GOALS “beliefs, relationships, goals, pursuit”).
- **Richer consolidation** into the store (beyond the single rolling summary string in `rolling_summary`).
- **Prompt assembler** reads from the store under token budget.
- **New memory modules** as needed (same `MemoryModule` protocol; per-agent module choice replaces archetype-tier policies).

V0.2 compound turns and object interact should log in a shape that V0.2.5 can ingest without rework.

## V0.3

**Focus:** **V0.3.0** — engine refactor (Session API, snapshots, GameProfile, CLI on Session). **V0.3.1** — example web project built on the engine. **V0.3.2** — realm-studio polish (GM events, appearance). **Depends on V0.2.5** (`v0.2.5`).

See [v0.3.0-changelog.md](changelog/v0.3.0-changelog.md) for slice plan (0.3.0a–e). See [v0.3.1-changelog.md](changelog/v0.3.1-changelog.md) for realm-studio (0.3.1a–f). See [v0.3.2-changelog.md](changelog/v0.3.2-changelog.md) for 0.3.2 slices. See [v0.4.0-changelog.md](changelog/v0.4.0-changelog.md) for 0.4.0 slices. See [v0.4.1-changelog.md](changelog/v0.4.1-changelog.md) for 0.4.1 slices. See [v0.4.2-changelog.md](changelog/v0.4.2-changelog.md) for 0.4.2 slices. See [v0.4.3-changelog.md](changelog/v0.4.3-changelog.md) for 0.4.3 slices.

### V0.3.0 — Engine — ✅ Implemented (`0.3.0`; superseded by **`0.4.0`**)

- **`Session`** — single entry point for turns, area-edit commands, active agent, prompts (one **`Area`** per session)
- **JSON snapshot** — web-ready area state
- **`GameProfile`** — prompt templates + default area factory; swappable schemas → **V0.4**
- **CLI refactor** — `ManualStepper` delegates to `Session`
- **`realm_fabric` package** — public imports for downstream projects
- **`Area`** — configurable `GridBounds` + `area_description`
- **Tests** — session, snapshot, profile, packaging, CLI parity (274 tests)

### V0.3.1 — Example web project — ✅ Implemented (tag **`v0.3.1`**)

See [v0.3.1-changelog.md](changelog/v0.3.1-changelog.md). App path: **`examples/web/realm-studio`**.

- FastAPI wraps `Session`; depends on `realm-fabric>=0.4.3` (path dep in dev)
- Local web UI: **grid** with agents/objects; **right-click** create/edit/delete; passive vision + turn log; **Run turn**
- **19** FastAPI `TestClient` smoke/integration tests (V0.3.2); engine coverage stays in root pytest

### V0.3.2 — realm-studio polish (events + appearance) — ✅ Implemented (tag **`v0.3.2`**)

See [v0.3.2-changelog.md](changelog/v0.3.2-changelog.md).

- **Area-wide GM events** — `Session.emit_area_event`; memory for all agents; realm-studio **Emit event…** + **Recent events** sidebar
- **Pannable grid viewport** — white map on black canvas (0.3.2c1)
- **`appearance`** — client-only image path on `Agent` / `Object`; token images on grid (0.3.2c2–d)
- **Tests** — root **348** pytest; realm-studio **36** API tests
- **Not in 0.3.2:** multiplayer (moved to [LONG_TERM_GOALS.md](../LONG_TERM_GOALS.md))

Larger items (Roll20 integration, full strategy turn models, lorebooks, etc.) remain in [LONG_TERM_GOALS.md](../LONG_TERM_GOALS.md).

## V0.4

**Focus:** **Tactical movement** + **multi-area sessions** + **area-transfer object effects**. Builds on V0.3.2 engine + realm-studio.

**Status:** ✅ **Complete** — see [v0.4.0-changelog.md](changelog/v0.4.0-changelog.md) for slices **0.4.0a–e**. Tag **`v0.4.0`** when ready.

### V0.4.0 — movement, multi-area, portals — ✅ Complete

| Slice | Theme | Status |
|-------|--------|--------|
| **0.4.0a** | `move_target` accepts entity id | ✅ |
| **0.4.0b** | `move_speed` + Chebyshev pathing | ✅ |
| **0.4.0c1** | Multi-area `Session` + snapshot | ✅ |
| **0.4.0c2** | realm-studio area dropdown | ✅ |
| **0.4.0d** | `move_area` effect + object actions UI + interact templates | ✅ |
| **0.4.0e** | Release polish, tag **`v0.4.0`** | ✅ |

- **Movement** — id or coordinate targets; `move_speed=None` preserves teleport parity
- **Multi-area** — `Session.areas`, agent `area_id`, full snapshot v1; GM **active area** in realm-studio
- **Connectors** — `move_area` on object actions (doors, ladders) via parameterized effects; **Manage actions…** in realm-studio
- **Interact templates** — `{object_start}`, `{actor_end_area}`, etc.; **?** help in action editor
- **Tests** — root **348** pytest; realm-studio **36** API tests
- **Deferred:** swappable turn schemas → **V0.5+**; multiplayer → [LONG_TERM_GOALS.md](../LONG_TERM_GOALS.md)

<details>
<summary>Original ROADMAP draft (multi-area + swappable schemas)</summary>

### Multi-area session

- **`Session`** holds a map of areas (e.g. by `area_id`) plus each agent’s **current area**
- **Area transfer API** — move an agent from one area to another (and optionally to a coordinate in the destination area)
- **Prompt / perception** scoped to the agent’s **current area** only (passive vision, interact list, bounds)
- **Cross-area** — no shared passive vision by default; portals/exits modeled as objects or explicit transfer commands
- **Snapshot** includes all areas + agent locations for save/load

### Swappable turn schemas (`GameProfile`)

- Profile selects **Pydantic model + turn executor**, not just prompt prose — deferred to **V0.5+**

</details>

---

## V0.4.1

**Focus:** **LLM turn reliability** + **GM prompt layout** in realm-studio. Builds on V0.4.0.

**Status:** ✅ **Complete** — see [v0.4.1-changelog.md](changelog/v0.4.1-changelog.md) for slices **0.4.1a–d** (+ **0.4.1c+**). Tag **`v0.4.1`** when ready.

### V0.4.1 — truncation + prompt blocks — ✅ Complete

| Slice | Theme | Status |
|-------|--------|--------|
| **0.4.1a** | Sentence-aware truncation (`reasoning` 400, speak 500); drop 5-sentence cap | ✅ |
| **0.4.1b** | Prompt block model + session override + API | ✅ |
| **0.4.1c** | realm-studio block-list prompt editor | ✅ |
| **0.4.1c+** | Slot ⚙ settings, vision units, bearing, move-instruction polish | ✅ |
| **0.4.1d** | Release polish, tag **`v0.4.1`** | ✅ |

- **Truncation** — trim at sentence boundaries on parse; no mid-sentence cuts; turns do not fail on length alone
- **Prompt blocks** — reorder `slot` / `text` / `section` blocks; edit static rules and output format in-session
- **Slot settings** — Character / passive vision / move-instructions ⚙ toggles; session **Units** for distance and move speed
- **Deferred:** profile file export, per-agent prompts, swappable schemas → **V0.5+**

---

## V0.4.2

**Focus:** **Clearer spatial prompts** and **richer compound turns**. Builds on V0.4.1.

**Status:** ✅ **Complete** — see [v0.4.2-changelog.md](changelog/v0.4.2-changelog.md) for slices **0.4.2a–e**. Tag **`v0.4.2`** when ready.

### V0.4.2 — emote + speak step + debug — ✅ Complete

| Slice | Theme | Status |
|-------|--------|--------|
| **0.4.2a** | Action range labels in session units | ✅ |
| **0.4.2b** | Speak separate from `turn_action` | ✅ |
| **0.4.2c** | Prompt input token estimate on Run turn hover | ✅ |
| **0.4.2d** | Emote turn action; remove confidence/emotion | ✅ |
| **0.4.2e** | Last response debug; release polish, tag **`v0.4.2`** | ✅ |

- **Compound pipeline** — move → look → speak → turn action (`interact` | `emote` | `none`)
- **Emote** — past-tense gestures at entities or free-text targets; per-observer witness phrasing
- **realm-studio** — input-token hover hint; **Last prompt** + **Last response** debug panels
- **Breaking:** `"turn_action": "speak"` and `confidence` / `emotion` fields removed from compound JSON

---

## V0.4.3

**Focus:** **realm-studio create-agent** + edit location UX + witness broadcast fixes. Builds on V0.4.2.

**Status:** ✅ **Complete** — see [v0.4.3-changelog.md](changelog/v0.4.3-changelog.md) for slices **0.4.3a–c**. Tag **`v0.4.3`** when ready.

| Slice | Theme | Status |
|-------|--------|--------|
| **0.4.3a** | Memory module + options on create-agent in realm-studio | ✅ |
| **0.4.3b** | Edit object/agent Location panel (area + position) | ✅ |
| **0.4.3c** | Multi-step witness broadcast (speak + emote, etc.) | ✅ |

- **`GET /api/memory-modules`** — catalog for UI; **`memory-window`** on `create-agent`
- **Create agent** modal — module dropdown + conditional options; Advanced collapse
- **Edit object/agent** — Location ▾ (area + X/Y); cross-area engine support
- **Witness broadcast** — move/speak/emote/interact each recorded; look only when idle

---

## V0.4.4

**Focus:** **Prompt and schema token reduction** — shrink default compound-turn input (~966 est. tokens pre-release) before future lorebook and richer memory. Builds on V0.4.3.

**Status:** ✅ **Complete** — see [v0.4.4-changelog.md](changelog/v0.4.4-changelog.md) for slices **0.4.4a–d**. Tag **`v0.4.4`** when ready.

| Slice | Theme | Status |
|-------|--------|--------|
| **0.4.4a** | Baseline + token budget regression test | ✅ |
| **0.4.4b** | Compact rules, look/interact, output_format, dedupe glue | ✅ |
| **0.4.4c** | Compact JSON keys (`move`, `look`, `say`, `action`, `verb`) | ✅ |
| **0.4.4d** | Release polish, tag **`v0.4.4`** | ✅ |

- **Prompt** — terse default `compound_rules`; dynamic slots unchanged; verbose rules still editable in realm-studio Prompt layout
- **Schema** — shorter LLM JSON keys; legacy 0.4.3 keys accepted via normalization shim
- **Deferred:** lorebook, richer memory beyond current modules → post–V0.4.4; swappable schemas → **V0.5+**

---

## V0.4.5

**Focus:** **Session save/load** — full snapshot round-trip (world + memory + prompt blocks) + realm-studio export/import.

**Status:** ✅ **Done** — tag **`v0.4.5`** when ready.

- `Session.from_snapshot()` / `Session.to_save_dict()` / `build_save_snapshot` with `snapshot_version: 1`
- Memory modules: `export_state` / `restore_state` on all built-in modules
- CLI: `export-session`, `import-session`
- realm-studio: `GET /api/session/export`, `POST /api/session/import`, header save/load icon buttons

See [v0.4.5-changelog.md](changelog/v0.4.5-changelog.md).

---

## V0.4.6

**Focus:** **Custom memory modules** — runtime registration, save/load validation, realm-studio settings gear.

**Status:** ✅ **Done** — tag **`v0.4.6`** when ready.

- Split built-in / custom registries; `loader.py`; CLI `add-memory-module`
- Example `rolling_summary_custom`; contract in `examples/custom_memory/`
- `validate_snapshot_modules` — import fails if save references unloaded `module_id`
- realm-studio: settings modal (LLM key/model in-memory, module upload); loaded-only create-agent catalog
- Per-request `OPENROUTER_MODEL`; fresh root README + [cli.md](cli.md)

See [v0.4.6-changelog.md](changelog/v0.4.6-changelog.md).

---

## V0.5.0

**Focus:** **Lorebooks** — SillyTavern JSON import, optional `lorebook` prompt slot, realm-studio Lorebooks tab.

**Status:** ✅ **Shipped** — tag **`v0.5.0`**.

- `src/lorebook/` — ST import, keyword matcher, char budget
- Session lorebook CRUD; `lorebook` slot (one book per block; not in default layout)
- `snapshot_version: 2` with `lorebooks` array (v1 import supported)
- realm-studio: Main | Lorebooks tabs; load/edit entries; prompt layout book picker
- CLI: `load-lorebook`, `lorebooks`

See [v0.5.0-changelog.md](changelog/v0.5.0-changelog.md).

---

## V0.6.0

**Focus:** **Grid simulation depth** — multi-tile objects, movement blocking, interact pathing, merged passive-vision prompt, hidden objects and triggers. Builds on V0.5.0.

**Status:** ✅ **Shipped** — tag **`v0.6.0`**.

| Slice | Theme | Status |
|-------|--------|--------|
| **0.6.0a** | Movement blocking + pathfinder | ✅ Done |
| **0.6.0b** | Interact pathing (overwrites move) | ✅ Done |
| **0.6.0c** | Merge look + interact into passive vision | ✅ Done |
| **0.6.0d** | Multi-tile object footprints | ✅ Done |
| **0.6.0e** | Hidden objects + step-aware triggers | ✅ Done |
| **0.6.0f** | Release prep (`private_data`, studio modals) | ✅ Done |

**Shipped highlights:**

- BFS pathfinding + per-entity blocking / `movement_exceptions`
- Interact pathing overwrites compound `move`; passive vision includes interaction hints
- Multi-tile footprints; hidden objects; `trigger` actions on path steps
- **`snapshot_version: 3`** (v1–v2 import supported)
- **`private_data`** on agents/objects for custom apps (not CLI / LLM)
- realm-studio: footprint overlay, hidden-trigger wizard, grouped modals, player agents

See [v0.6.0-changelog.md](changelog/v0.6.0-changelog.md).

### Historical slice notes (0.6.0a–e)

<details>
<summary>Original implementation notes (archived)</summary>

### 0.6.0a — Movement blocking + pathfinder

- **Pathfinder** — BFS/A* on grid with same 5e step rules as today (diagonal + orthogonal cost 1); replace greedy `walk_towards` for blocked routes
- **Blocking** — per-entity `blocks_movement` (objects blocking by default; agents **non-blocking** by default so units can share tiles, D&D-friendly)
- **Selective pass-through** — `movement_exceptions: list[str]` on blocking entities (entity ids that may pass through *this* entity’s occupied tiles)
- Footprint v1 can stay 1×1; pathfinder API should accept tile occupancy from day one

### 0.6.0b — Interact pathing (overwrites move)

- Choosing **`interact`** in a compound turn **replaces** explicit movement for that turn (document in schema + few-shots; reject or ignore `move` when interact is set)
- Out of range: path toward **nearest valid interact tile** (within `action.range`) using full `move_speed` budget, then execute interact if in range
- Already in range: no movement
- Failure message in-world if still out of range after pathing (“too far to …”)

### 0.6.0c — Merged passive vision + interactions

- **Single prompt slot** — fold `look_and_interact` into passive vision (keep alias/migration for one release)
- Global rule: objects with **`[?]`** can be looked at for detailed description
- Empty look state: *“There are currently no objects you have not looked at and cannot gain any new information from looking.”*
- **Interactions indented under each object** in passive vision (not a separate block)
- List interactions reachable **after** full move budget toward the object (consistent with interact-overwrites-move)
- Agents still show `[?]` for examination; no fake interaction lines on agents

### 0.6.0d — Multi-tile objects ✅

- Axis-aligned **footprint** (`width`, `height`, anchor at `position`) — not arbitrary shapes in v1
- Passive vision: one line per object (document center vs footprint in range rules)
- **Range** — Chebyshev to **nearest tile** of footprint
- **Blocking** — all footprint tiles when `blocks_movement` is true
- Interact adjacency uses nearest valid tile within range

### 0.6.0e — Hidden objects + triggers

- **`hidden`** on objects — excluded from passive vision and look lists; still in world state, snapshots, GM tooling
- **`reveal` / `hide`** — `edit-object` (and realm-studio) toggles; optional handler-driven reveal on look/interact (hooks align with 0.6.1)
- New action kind **`trigger`** — engine-fired (not LLM `interact`); fires when an agent **enters or passes through** trigger range (Chebyshev to **nearest footprint tile**, same as interact range)
- **Multi-tile zones** — hidden objects with `width` / `height` (tripwires, doorway cutscene triggers); does not block movement when `blocks_movement` is false
- Evaluate triggers on **each step** along resolved paths (move, interact-path), not only endpoint; define dedupe (e.g. once per turn per trigger)
- Story outcomes via **`Session.emit_area_event`** from `passive_result` (handler/effect hooks deferred to **0.6.1**)
- realm-studio: GM visibility for hidden objects (ghost/list) so designers can place traps and zones

### Cross-cutting (0.6.0)

- **`snapshot_version: 3`** — footprint, blocking, hidden, trigger action kinds, `private_data`
- **Tests** — pathfinder, interact-path, triggers, multi-tile range, `private_data`
- **Deferred within 0.6.x** — line-of-sight vision, hearing range, tag-based movement exceptions

</details>

---

## V0.6.1

**Focus:** **Pluggable interaction handlers** — remove hardcoded effect registry from the engine; apps register world-change behavior at runtime (same sustainability goal as custom memory modules).

**Status:** ✅ **Shipped** — tag **`v0.6.1`**. See [v0.6.1-changelog.md](changelog/v0.6.1-changelog.md).

### Engine

- Remove built-in **`object_effects` registry** (`delete_self`, `random_move_self`, `move_area` as core code paths)
- **`ObjectAction`** — `result` / `passive` templates + **`handler_id`** + opaque **`params`** (handler optional = flavor-only interact)
- **`InteractionHandler` protocol** — `(session, agent, obj, action) -> str | None` (error message or success)
- **`register_interaction_handler(id, handler)`** — process-wide registry (parallel to memory modules)
- **Triggers and interacts share one handler surface** — same `handler_id` + `params` on `ObjectAction`
- **Trigger effects** — world-change behavior on trigger fire (today: area event text + optional `delete_after_trigger` only; full handler parity in 0.6.1, not the legacy `effect` CLI)
- Snapshots store handler id + params; validate on import that handlers are registered

### realm-studio (reference, not a library)

- Register **reference handlers** at startup: `delete_self`, `random_move_self`, `move_area` (demo ball kick, doors)
- **Manage actions…** UI maps to handler id + params — for **interact** and **trigger** kinds (not engine-specific effect names)
- **Trigger actions** — handler picker + params (replacing interact-only effect UI); cutscenes, teleports, item spawns via registered handlers
- Other apps copy this pattern; they do **not** import behavior from realm-studio

### Migration

- CLI `effect` on `create-object` → `handler` + params (or JSON/studio-only)
- Default profile / demo world registers reference handlers
- `move_area` becomes a **reference handler**, not special-cased engine code

See [v0.6.1-changelog.md](changelog/v0.6.1-changelog.md).

---

## V0.7.0

**Focus:** **Platform / app SDK** — stable `realm_fabric` API, typed programmatic world editing, thin HTTP reference (`minimal-server`), and app-developer documentation. Builds on **V0.6.1** handler contracts.

**Status:** ✅ **Implemented** — `pyproject.toml` **`0.7.0`**; tag **`v0.7.0`** pending. See [v0.7.0-changelog.md](changelog/v0.7.0-changelog.md).

**Ships the runway for apps.** Integration gaps found while building the external demo ship in **0.7.1+** on this repo; the demo itself versions independently (**0.1.0**+).

| Slice | Theme | Status |
|-------|--------|--------|
| **0.7.0a** | Expand `realm_fabric` exports + `test_public_api_surface.py` | ✅ Done |
| **0.7.0b** | Typed `Session` world API (`create_object`, `create_agent`, areas, …) | ✅ Done |
| **0.7.0c** | `run_command` delegates to typed API; CLI/debug contract | ✅ Done |
| **0.7.0d** | `guides/building-on-realm-fabric.md` + session hosting patterns | ✅ Done |
| **0.7.0e** | `examples/minimal-server/` — JSON HTTP, no grid UI | ✅ Done |
| **0.7.0f** | Semver policy, install story, release prep | ✅ Done |

### Public API (`realm_fabric`)

- Expanded exports: lorebooks, prompt blocks, `LorebookScanConfig`, `ObjectAction`, `WorldMutationResult`, interaction handlers, `register_memory_module_from_path`, `MemoryModule`
- **`tests/test_public_api_surface.py`** — CI fails if documented exports drift
- Semver policy documented in [building-on-realm-fabric.md](guides/building-on-realm-fabric.md)

### Typed world editing

- **`Session.create_object`**, **`create_agent`**, **`edit_object`**, **`delete_object`**, **`delete_agent`**, **`add_object_action`**, **`remove_object_action`**, **`create_area`**
- Same validation as CLI; apps use structured arguments, not `run_command` strings
- **`tests/test_session_world_api.py`**
- `edit_agent` / `edit_area` typed methods — CLI only for now (optional follow-up)

### Documentation

- **[building-on-realm-fabric.md](guides/building-on-realm-fabric.md)** — install, session lifecycle, typed API, anti-patterns, hosting, semver
- **0.6.x** pathing, interact-path, and interaction handlers covered for app authors

### Examples

- **`examples/minimal-server/`** — thin FastAPI on port 8770: health, state, turn, manual turn, export/import, optional debug `/api/command`
- Bootstrap uses **typed API only** (no CLI strings)
- [realm-studio](../examples/web/realm-studio) remains the **full GM reference app**, not the template every project clones

### Session hosting

- Documented in `guides/building-on-realm-fabric.md`: per-match sessions, handler/module process scope, persistence patterns
- realm-studio = singleton in-memory session (reference only)

### Distribution

- Install via path/git dep today; **PyPI publish** optional follow-up (packaging ready in `pyproject.toml`)
- Changelog: **App developer impact** per release in version changelogs

### Deferred / optional

- realm-studio migration off `run_command` — not required for apps; optional follow-up
- realm-studio as separate repo — see discussion in project planning; still under `examples/web/realm-studio` today

See [v0.7.0-changelog.md](changelog/v0.7.0-changelog.md).

---

## V0.7.1

**Focus:** **Engine/SDK follow-up** while building the product-shaped demo in a **separate repository**. Tag **`v0.7.1`** on **this repo** for `realm_fabric` / `Session` fixes and small API additions discovered during demo integration — **not** for shipping the demo itself.

**Status:** 📋 **Planned** — after **0.7.0** tag. See [v0.7.1-changelog.md](changelog/v0.7.1-changelog.md).

### Versioning model

| Artifact | Repo | Tags |
|----------|------|------|
| Realm-Fabric engine | This monorepo | `v0.7.0`, **`v0.7.1`**, … |
| Product-shaped demo | Separate repo (TBD) | **`v0.1.0`**, `v0.2.0`, … |

The demo depends on `realm-fabric>=0.7.0` and bumps its requirement when engine releases ship.

### In scope for V0.7.1 (this repo)

- Missing typed APIs, exports, or docs exposed by demo development
- Bug fixes and `minimal-server` clarifications that help app authors
- No requirement to complete the demo before tagging **`v0.7.1`** — tag when engine slices are ready

### Sample demo (external — not V0.7.1)

- **Separate repository** — name TBD (e.g. `realm-fabric-sample`); link in README when it exists
- **`realm-fabric>=0.7.0`** via its own `pyproject.toml` (path/git/PyPI during co-development)
- Typed `Session` API only; own handlers and small UI/CLI
- First demo release: **`v0.1.0`** on the **demo repo**, not on Realm-Fabric

Details: [v0.7.1-changelog.md](changelog/v0.7.1-changelog.md).

### Out of scope

- Shipping the full demo from this monorepo (`examples/` keeps `minimal-server` only)
- realm-studio migration off `run_command` (optional)
- Multiplayer netcode

---

**Notes**

- Prefer adding sections to the [V0.2.5 changelog](changelog/v0.2.5-changelog.md) or [V0.3.0 changelog](changelog/v0.3.0-changelog.md) over a readiness checklist for new versions.
- When a version is **implemented**, move relevant items to "Achieved" in LONG_TERM_GOALS.md and update this roadmap.
- This document is meant to be living — edit it as plans evolve.

