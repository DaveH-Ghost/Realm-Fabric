# Building on CampAIgn-RPG-Engine

Guide for application authors integrating **CampAIgn-RPG-Engine 1.0** as a library. Import only from **`campaign_rpg_engine`** in product code — the package is a single tree at `campaign_rpg_engine/` (no `src.*` layout).

**Read first:** [Overview](overview.md). **Upgrading from 0.7?** [Migration 0.7 → 1.0](../MIGRATION-0.7-to-1.0.md).

---

## Documentation map

| Topic | Guide |
|-------|-------|
| Architecture | [Overview](overview.md) |
| Compound turns & LLM | [Turns](turns.md) |
| Object behavior | [Handlers](handlers.md) |
| Saves & HTTP state | [Persistence](persistence.md) |
| Memory & lore | [Memory & lorebooks](memory-and-lorebooks.md) |
| Full export list | [API reference](api-reference.md) |

Runnable template: [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) (`backend/` shows HTTP + typed `Session` usage).

---

## Install

```powershell
uv add campaign-rpg-engine

# Co-development with a local checkout
uv add --editable path/to/CampAIgn-RPG-Engine
```

Python **3.11+** required.

---

## Project layout

```
my-realm-game/
  pyproject.toml          # depends on campaign-rpg-engine>=1.0.0
  my_game/
    handlers/             # your interaction handlers
    server.py             # FastAPI / your HTTP layer
    bootstrap.py          # typed world setup
```

Keep **scenario content** (handlers, lorebooks, UI) in your repo. Use **CampAIgn-RPG-Studio** as the HTTP + GM reference; fork it only if you need a full editor.

---

## Session lifecycle

```python
from campaign_rpg_engine import Session, load_profile, AgentCompoundTurn

session = Session.from_profile(load_profile("default_compound"))

session.create_agent(name="Player", position=(0, 0), is_player=True, personality="...")
session.create_object(name="Chest", position=(2, 1), passive_description="...")

# NPC: build_prompt → LLM → run_compound_turn (see turns.md)
# Player: run_compound_turn(AgentCompoundTurn(...), agent_id=player.id)

save_doc = session.to_save_dict()
restored = Session.from_snapshot(save_doc)
```

### Use the typed API

Bootstrap and mutate worlds with **`Session` methods** — not string commands.

| Layer | Use |
|-------|-----|
| App bootstrap / gameplay | `session.create_object(...)`, `session.create_agent(...)`, `session.edit_agent(...)`, … |
| GM authoring UI | Typed HTTP handlers (see CampAIgn-RPG-Studio `area_api.py`) or your own forms |
| Legacy stepper strings | App-owned dispatch only (CampAIgn-RPG-Studio `command_dispatch.py` imports `campaign_rpg_engine.area_edit` helpers) |

---

## Typed world-editing API

Methods return **`WorldMutationResult`** or **`AreaMutationResult`** (`ok`, `message`, optional entity refs):

| Method | Purpose |
|--------|---------|
| `create_object(name, position, *, area_id=None, ...)` | Add object |
| `create_agent(name, position, *, personality, is_player, memory_module, ...)` | Add agent |
| `edit_object(object_id, *, description, position, target_area_id, ...)` | Update / move object |
| `edit_agent(agent_id, *, name, personality, position, area_id, ...)` | Update / move agent |
| `delete_object(object_id)` | Remove object (session-wide) |
| `delete_agent(agent_id)` | Remove agent |
| `add_object_action(object_id, action: ObjectAction)` | Attach handler-backed action |
| `remove_object_action(object_id, action_name)` | Remove action |
| `create_area(area_id, *, description, width, height)` | New area |
| `edit_area(area_id, *, description, width, height, ...)` | Resize / update area |
| `delete_area(area_id)` | Remove empty area |

Full signatures: [API reference](api-reference.md).

---

## Register handlers and memory at startup

Process-wide — register before `Session.from_snapshot()` if the save references them:

```python
from campaign_rpg_engine import register_interaction_handler, register_memory_module_from_path

register_interaction_handler("my_effect", my_handler_fn, label="My effect")
register_memory_module_from_path("path/to/my_memory_module.py")
```

Details: [Handlers](handlers.md), [Memory & lorebooks](memory-and-lorebooks.md).

---

## Session hosting

- **One `Session` per match / lobby / campaign**
- **Singleton** (like CampAIgn-RPG-Studio) is fine for local demos
- **Handlers / memory modules**: process start; shared across sessions in that process
- **Persistence**: [Persistence guide](persistence.md)

---

## Testing without an LLM

Use manual `AgentCompoundTurn` payloads or mock the LLM layer. Engine tests auto-register reference handlers via `tests/conftest.py`.

---

## Semver policy

| Surface | Stability |
|---------|-----------|
| `campaign_rpg_engine.__all__` | Semver |
| Documented `Session` methods | Semver |
| `campaign_rpg_engine.area_edit` string helpers | Internal — for tests and app-owned GM dispatch |
| `snapshot_version` | Migration notes in [changelogs](../changelog/README.md) |

---

## Related

- [Documentation hub](../README.md)
- [Migration 0.7 → 1.0](../MIGRATION-0.7-to-1.0.md)
- [Roadmap](../ROADMAP.md)
