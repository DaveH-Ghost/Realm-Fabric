# Long Term Goals

**Purpose:**  
This document exists to capture big, exciting, "someday" dreams for this project without letting them pollute or over-scope the current version we're working on.

These are **aspirational goals**. They are not targets for Version 0, Version 0.1, or even Version 1 unless we explicitly decide to pull one in. They are recorded here so they aren't lost and so we can feel the satisfaction of moving them into the "Achieved" section when the time comes.

Treat this file like a trophy case. Checking something off here should feel like a real milestone.

---

## Planned Goals

Concrete improvements we expect to build — not current-version scope, but not distant dreams either.

- [ ] **Multiplayer / shared sessions** — Server-authoritative `Session`, rooms, auth, and multiple clients on one world (WebSocket or equivalent). Studio is the GM host (single-session today); player clients attaching to Studio are the intended model. See [docs/UML/01-system-overview.md](docs/UML/01-system-overview.md).

---

## Dream Goals

These are still distant or unspecified. They are not committed roadmap items.

*(Most former dream goals have moved to **Achieved** or **Out of scope** below.)*

---

## Out of scope (for CampAIgn-RPG-Engine / campaign-rpg-studio)

CampAIgn-RPG-Engine is a **simulation engine** and **library API**. [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) is the **GM host** for authoring and running sessions — world authority for a campaign. It is not a full multiplayer VTT yet; **player clients attaching to Studio** are a planned goal (see Planned Goals). The following experiences are intentionally **not** built into the core engine. **Apps** (including future clients) can implement them using pluggable memory modules, interaction handlers (V0.6.1+), lorebooks, and their own UI.

- **Multi-agent social simulation** — agents that observe each other, start targeted conversations, form relationships, and influence one another over time.  
  V0.1 shipped shared-grid multi-agent with passive vision, `look` at other agents, and observable speech/movement via `passive_result`. That is engine support only. Rich social dynamics belong in **downstream apps** with custom memory modules and app-specific prompts/rules.

- **Roll20-style VTT UI** — grid with tokens, chat bubbles, full tabletop UX.  
  campaign-rpg-studio provides a minimal authoring grid and turn runner, not a player-facing VTT. Product UIs are **app scope**.

- **Roll20 plugin / live game bridge** — Mod/API Scripts, chat bridge, token control in real Roll20 games.  
  Same as above: integrate via a **separate app** that talks to Roll20 and uses `Session` (or snapshots) on the side.

- **Agent-initiated world edits** — agents that create or modify objects in the world (with validation/rules).  
  V0.6.1 **interaction handlers** give apps a hook to run world changes from interacts and triggers; the engine does not ship agent-driven authoring or a built-in validation policy. Apps decide what agents may change.

- **Rich agent cognition** — beliefs, relationships, long-term goals, emotional state, pursuing objectives over many turns instead of only reacting to the current situation.  
  V0.2.5 shipped **pluggable memory modules** (`recent_turns`, `salient_turns`, `rolling_summary`, custom modules). Beliefs, goals, and personality depth are **app-owned**: implement in custom modules and prompts, not in the core engine or campaign-rpg-studio.

---

## Achieved Goals

This section is for goals that have actually been completed. When something moves here, it should feel like a genuine accomplishment.

- [x] **General "object knowledge is stale" notification (V0.1)**  
  When an object's or agent's detailed description changes after an agent has examined it, passive vision shows a neutral stale state (e.g. `[?] [changed] A simple wooden sign on the wall.`) so the agent knows to `look` again. Works via `ever_looked` + `World.invalidate_entity_knowledge()`, not sign-specific. See [v0.1-implementation-readiness-checklist.md](docs/changelog/v0.1-implementation-readiness-checklist.md).

- [x] **Runtime world editing via stepper commands (V0.1)**  
  Create, edit, and delete objects and agents at runtime (`create-object`, `edit-object`, `delete-object`, `create-agent`, `edit-agent`, `delete-agent`) with listing commands (`list`, `objects`, `agents`). Objects support passive (`pdesc`) and detailed (`desc`) descriptions. Replaces the V0 `sign` command.

- [x] **Multi-agent shared world with passive observation (V0.1)**  
  Multiple agents share one grid with independent memory and per-agent turn numbers. `switch` / `run` / typing a name control turns. Other agents appear in passive vision (`pdesc` / `desc` / `[?]`); `personality` is LLM-only. Observable actions (`passive_result`) let agents see each other's recent speech, movement, and looks. Agent names cannot collide with stepper commands. See [v0.1-implementation-readiness-checklist.md](docs/changelog/v0.1-implementation-readiness-checklist.md).

- [x] **Declarative object interact — first milestone (V0.2 Section 3, v0.2.0)**  
  Objects expose named `ObjectAction`s with Chebyshev range, `{actor}`/`{object}` templates, and a central effect registry (`delete_self`, `random_move_self`). Interact runs in the compound action phase; listed in the post-move action prompt when in range. Initial ball includes **`kick`**. See [v0.2-implementation-readiness-checklist.md](docs/changelog/v0.2-implementation-readiness-checklist.md).

- [x] **Pluggable memory modules (V0.2.5, `0.2.5`)**  
  Per-agent memory modules (`recent_turns`, `salient_turns`, `rolling_summary`) with witnessed-action ingest, condensed render, salience retention, and async rolling LLM consolidation. Single compound LLM call per turn. See [v0.2.5-changelog.md](docs/changelog/v0.2.5-changelog.md).

- [x] **Compound D&D-shaped agent turns (V0.2, v0.2.0)**  
  Two-phase LLM per turn (navigation then action): optional coordinate move, optional look, optional speak or object interact. `step-compound` manual parity; structured `TurnRecord.steps` for future memory ingestion. See [v0.2-implementation-readiness-checklist.md](docs/changelog/v0.2-implementation-readiness-checklist.md).

- [x] **Session save/load (V0.4.5, `0.4.5`)**  
  Full snapshot round-trip: multi-area world, objects, agents, look knowledge, all memory modules (`export_state` / `restore_state`), prompt block overrides, vision settings. CLI `export-session` / `import-session`; campaign-rpg-studio save/load buttons and API. See [v0.4.5-changelog.md](docs/changelog/v0.4.5-changelog.md).

- [x] **Lorebook / world-info injection (V0.5.0, `0.5.0`)**  
  SillyTavern JSON import, session-level lorebooks, keyword/constant matching, optional per-book `lorebook` prompt slot, campaign-rpg-studio Lorebooks tab. See [v0.5.0-changelog.md](docs/changelog/v0.5.0-changelog.md).

- [x] **Tactical grid simulation (V0.6.0, `0.6.0`)**  
  Movement blocking, BFS pathfinding, interact pathing, merged passive-vision prompts, multi-tile footprints, hidden objects, path-step triggers, `snapshot_version: 3`. See [v0.6.0-changelog.md](docs/changelog/v0.6.0-changelog.md).

- [x] **Rectangular / multi-tile objects (V0.6.0d, `0.6.0`)**  
  Axis-aligned footprints (`width` / `height`), blocking on all footprint tiles, Chebyshev range to nearest footprint tile. See [v0.6.0-changelog.md](docs/changelog/v0.6.0-changelog.md).

- [x] **Object behaviors and actions (V0.2 + V0.6.0 + V0.6.1)**  
  Declarative `interact` actions and effect registry (V0.2); engine-fired **triggers** for zones and cutscenes (V0.6.0); **pluggable interaction handlers** so apps register world-change behavior at runtime — food that can be eaten, puzzle boxes, lockable doors, etc. are implemented by **apps** via handlers, not hardcoded in the engine. See [v0.2.0](docs/changelog/v0.2-implementation-readiness-checklist.md), [v0.6.0-changelog.md](docs/changelog/v0.6.0-changelog.md), [ROADMAP.md](docs/ROADMAP.md) V0.6.1.

- [x] **Coordinate and entity-target move (V0.4.0 + V0.4.4 JSON)**  
  Compound turns accept coordinate `"x,y"` or entity id (`obj_*` / `agent_*`) as move targets; optional `move_speed` pathing. V0.4.4 compact JSON field `move`. See [v0.4.0-changelog.md](docs/changelog/v0.4.0-changelog.md).

---

## How to Use This Document

- Add new dream goals whenever they come up during development or daydreaming.
- Do **not** use these goals to justify adding scope to the current version.
- When we decide a dream is worth actively working toward, we should first create a proper design document for it (not just check it off).
- Moving something from "Dream Goals" to "Achieved" should be celebrated.
- If a goal is better solved by **downstream apps** than the engine, record it under **Out of scope** instead of Dream Goals.

---

*This file is meant to stay fun and inspiring. It is not a roadmap.*
