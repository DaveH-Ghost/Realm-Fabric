# Long Term Goals

**Purpose:**  
This document exists to capture big, exciting, "someday" dreams for this project without letting them pollute or over-scope the current version we're working on.

These are **aspirational goals**. They are not targets for Version 0, Version 0.1, or even Version 1 unless we explicitly decide to pull one in. They are recorded here so they aren't lost and so we can feel the satisfaction of moving them into the "Achieved" section when the time comes.

Treat this file like a trophy case. Checking something off here should feel like a real milestone.

---

## Dream Goals

These are currently out of scope. They represent the kind of experiences we eventually want to create.

### More Complex Goals

- [ ] Multiple agents that can observe each other, start conversations, form relationships, and influence one another over time  
  *(V0.1 added shared-grid multi-agent with passive vision, `look` at other agents, and observable speech/movement via `passive_result` — but no relationships, beliefs, speak targeting, or agent-driven world edits. That is a stepping stone, not this goal.)*
- [ ] Objects that have their own behaviors and actions (examples: food that can be eaten and gives a taste description, a puzzle box with interactive mechanisms, a door that can be locked/unlocked, etc.)  
  *(**V0.2** — first step **shipped on `main`**: declarative `interact` actions, effect registry (`delete_self`, `random_move_self`), ball `kick`. Puzzle doors, taste text, and richer effect types remain future work; see [v0.2-implementation-readiness-checklist.md](docs/v0.2-implementation-readiness-checklist.md).)*
- [ ] Rectangular / multi-tile objects (e.g. long walls, large furniture, 2x2 trees with 6x6 shadows) where objects occupy multiple grid tiles using size + bounding box definitions instead of single-tile objects
- [ ] A visual interface similar to Roll20 — a grid with tokens representing agents and objects, plus chat bubbles when agents speak
- [ ] **Roll20 plugin support**  
  Integrate the agent with real Roll20 games (via Mod/API Scripts + chat bridge). Enable the agent to perceive live map state and control tokens representing D&D characters, NPCs, and enemies. The external agent handles reasoning/LLM calls; a companion Roll20 script executes token movement, sheet updates, etc. (Roll20 Pro required for the scripting side; communication constrained by the sandbox model.)
- [ ] Agents that can create or modify objects in the world (with some form of validation or rules)
- [ ] Richer memory systems (beliefs, relationships, long-term goals, emotional state)  
  *(Planned for **V0.2.5** — persistent memory store, tiered policies, memory manager LLM; see [ROADMAP.md](docs/ROADMAP.md). V0.2 leaves compound `TurnRecord.steps` as ingestion hooks.)*
- [ ] The ability for agents to develop and pursue their own goals over many turns instead of only reacting to the current situation  
  *(Tied to **V0.2.5** goals/tasks linked to memory IDs.)*

---

## Achieved Goals

This section is for goals that have actually been completed. When something moves here, it should feel like a genuine accomplishment.

- [x] **General "object knowledge is stale" notification (V0.1)**  
  When an object's or agent's detailed description changes after an agent has examined it, passive vision shows a neutral stale state (e.g. `[?] [changed] A simple wooden sign on the wall.`) so the agent knows to `look` again. Works via `ever_looked` + `World.invalidate_entity_knowledge()`, not sign-specific. See [v0.1-implementation-readiness-checklist.md](docs/v0.1-implementation-readiness-checklist.md).

- [x] **Runtime world editing via stepper commands (V0.1)**  
  Create, edit, and delete objects and agents at runtime (`create-object`, `edit-object`, `delete-object`, `create-agent`, `edit-agent`, `delete-agent`) with listing commands (`list`, `objects`, `agents`). Objects support passive (`pdesc`) and detailed (`desc`) descriptions. Replaces the V0 `sign` command.

- [x] **Multi-agent shared world with passive observation (V0.1)**  
  Multiple agents share one grid with independent memory and per-agent turn numbers. `switch` / `run` / typing a name control turns. Other agents appear in passive vision (`pdesc` / `desc` / `[?]`); `personality` is LLM-only. Observable actions (`passive_result`) let agents see each other's recent speech, movement, and looks. Agent names cannot collide with stepper commands. See [v0.1-implementation-readiness-checklist.md](docs/v0.1-implementation-readiness-checklist.md).

- [x] **Declarative object interact — first milestone (V0.2 Section 3, pre-`v0.2.0` tag)**  
  Objects expose named `ObjectAction`s with Chebyshev range, `{actor}`/`{object}` templates, and a central effect registry (`delete_self`, `random_move_self`). Interact runs in the compound action phase; listed in the post-move action prompt when in range. Initial ball includes **`kick`**. Full puzzle/behavior richness remains in Dream Goals above. See [v0.2-implementation-readiness-checklist.md](docs/v0.2-implementation-readiness-checklist.md).

---

## How to Use This Document

- Add new dream goals whenever they come up during development or daydreaming.
- Do **not** use these goals to justify adding scope to the current version.
- When we decide a dream is worth actively working toward, we should first create a proper design document for it (not just check it off).
- Moving something from "Dream Goals" to "Achieved" should be celebrated.

---

*This file is meant to stay fun and inspiring. It is not a roadmap.*