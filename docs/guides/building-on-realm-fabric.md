# Building on Realm-Fabric

Guide for application authors integrating **Realm-Fabric** as a library (V0.7.0+). The engine ships a stable **`realm_fabric`** package; **`src.*`** imports are for the CLI, tests, and reference clients only and are not semver-guaranteed.

**Read first:** [Overview](overview.md) — mental model. **Then:** topic guides below.

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
| Debug CLI | [CLI reference](cli.md) |

Runnable template: [minimal-server](../../examples/minimal-server/).

---

## Install

```powershell
# From PyPI (when published)
uv add realm-fabric

# During co-development with the monorepo
uv add --editable path/to/Realm-Fabric
```

Python **3.11+** required.

---

## Project layout

```
my-realm-game/
  pyproject.toml          # depends on realm-fabric>=0.7.0
  my_game/
    handlers/             # your interaction handlers
    server.py             # FastAPI / your HTTP layer
    bootstrap.py          # typed world setup
```

Keep **scenario content** (handlers, lorebooks, UI) in your repo. Do not fork [realm-studio](../../examples/web/realm-studio/) unless you need a full GM editor.

The **product-shaped demo** will live in a **separate repository** (app version **0.1.0**+). Engine gaps from that work ship as **0.7.1+** here. Use **minimal-server** until the demo exists.

---

## Session lifecycle

```python
from realm_fabric import Session, load_profile, AgentCompoundTurn

session = Session.from_profile(load_profile("default_compound"))

# Bootstrap world with typed API (not CLI strings)
session.create_agent(name="Player", position=(0, 0), is_player=True, personality="...")
session.create_object(name="Chest", position=(2, 1), passive_description="...")

# NPC: build_prompt → LLM → run_compound_turn (see turns.md)
# Player: run_compound_turn(AgentCompoundTurn(...), agent_id=player.id)

save_doc = session.to_save_dict()
restored = Session.from_snapshot(save_doc)
```

### Anti-pattern: CLI strings in app code

**Do not** build world state with `session.run_command("create-object ...")` in product code.

| Layer | Use |
|-------|-----|
| App bootstrap / gameplay | `session.create_object(...)`, `session.create_agent(...)`, … |
| Human debugging | `realm` stepper or optional `POST /api/command` |
| realm-studio GM UI | `run_command` via HTTP (reference only) |

---

## Typed world-editing API

All methods return **`WorldMutationResult`** (`ok`, `message`, optional `object` / `agent` / `area_id`):

| Method | Purpose |
|--------|---------|
| `create_object(name, position, *, area_id=None, ...)` | Add object |
| `create_agent(name, position, *, personality, is_player, memory_module, ...)` | Add agent |
| `edit_object(object_id, *, description, position, target_area_id, ...)` | Update / move object |
| `delete_object(object_id)` | Remove object (session-wide) |
| `delete_agent(agent_id)` | Remove agent |
| `add_object_action(object_id, action: ObjectAction)` | Attach handler-backed action |
| `remove_object_action(object_id, action_name)` | Remove action |
| `create_area(area_id, *, description, width, height)` | New area |

Full signatures: [API reference](api-reference.md).

---

## Register handlers and memory at startup

Process-wide — register before `Session.from_snapshot()` if the save references them:

```python
from realm_fabric import register_interaction_handler, register_memory_module_from_path

register_interaction_handler("my_effect", my_handler_fn, label="My effect")
register_memory_module_from_path("path/to/my_memory_module.py")
```

Details: [Handlers](handlers.md), [Memory & lorebooks](memory-and-lorebooks.md).  
Reference: [reference_handlers](../../examples/reference_handlers/).

---

## Session hosting

- **One `Session` per match / lobby / campaign**
- **Singleton** (like realm-studio) is fine for local demos
- **Handlers / memory modules**: process start; shared across sessions in that process
- **Persistence**: [Persistence guide](persistence.md)

---

## Testing without an LLM

Use manual `AgentCompoundTurn` payloads or mock the LLM layer. Engine tests: `tests/conftest.py` (auto-registers reference handlers).

---

## Semver policy

| Surface | Stability |
|---------|-----------|
| `realm_fabric.__all__` | Semver |
| Documented `Session` methods | Semver |
| `src.*` | Internal |
| `snapshot_version` | Migration notes in [changelogs](../changelog/README.md) |

---

## Related

- [Documentation hub](../README.md)
- [Roadmap](../ROADMAP.md)
- [v0.7.0 changelog](../changelog/v0.7.0-changelog.md)
