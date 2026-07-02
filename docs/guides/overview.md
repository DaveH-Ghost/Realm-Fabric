# Overview

How Realm-Fabric models a playable grid world and LLM-driven agents.

---

## Core objects

| Concept | Role |
|---------|------|
| **`Session`** | Owns all simulation state — areas, agents, turn counter, lorebooks, prompt layout |
| **`Area`** | One grid room: bounds, objects, agents, recent GM events |
| **`Agent`** | Character on the grid — position, personality, memory, `is_player` flag |
| **`Object`** | World prop — footprint, descriptions, interaction actions |
| **`GameProfile`** | Default area factory + compound-turn schema (`default_compound`) |

A session can hold **multiple areas**. Each agent has an **`area_id`** mapping. **`active_area_id`** scopes GM-style edits; **`active_agent_id`** is who runs next by default.

---

## One compound turn

Each turn is a single structured **`AgentCompoundTurn`** (move → look → speak → action):

```
1. Move     optional — coordinate "x,y" or entity id; pathing when move_speed set
2. Look     optional — examine one entity id after moving
3. Say      optional — dialogue heard by witnesses
4. Action   interact | emote | none — turn-ending action
```

The engine runs these phases in order, updates memory, and records **`TurnRecord`** steps.

- **NPC agents:** your server calls the LLM with `session.build_prompt()`, parses JSON into `AgentCompoundTurn`, then `session.run_compound_turn(...)`.
- **Player agents:** set `is_player=True`; your client sends `AgentCompoundTurn` JSON directly (no LLM).

See [Compound turns](turns.md).

---

## Perception

Agents see the world through **passive vision** (injected into the LLM prompt):

- Nearby objects and agents show `pdesc` or `[?]` if never examined
- After `look`, detailed `desc` is remembered until it changes
- In-range **object actions** appear as interaction options

Your UI can read `session.snapshot()` — it includes `passive_vision` for the active agent when requested.

---

## World changes

Apps bootstrap and mutate worlds with the **typed Session API** (`create_object`, `create_agent`, …). Object **interacts** and path **triggers** call **registered interaction handlers** — game logic lives in your app, not the engine core.

See [Building on Realm-Fabric](building-on-realm-fabric.md) and [Interaction handlers](handlers.md).

---

## What to use where

| You are building… | Start with |
|-------------------|------------|
| HTTP / web game | [minimal-server](../../examples/minimal-server/) + [Building on Realm-Fabric](building-on-realm-fabric.md) |
| GM authoring tool | [realm-studio](../../examples/web/realm-studio/) (reference; fork or replace) |
| CLI debugging | [CLI reference](cli.md) |
| Headless / tests | `Session` + manual `AgentCompoundTurn` |

---

## Next

- [Building on Realm-Fabric](building-on-realm-fabric.md) — install and integration patterns
- [API reference](api-reference.md) — exports and Session methods
