# Persistence & snapshots

Two JSON shapes serve different purposes — do not confuse them.

---

## Comparison

| | **`session.to_save_dict()`** | **`session.snapshot()`** |
|--|------------------------------|---------------------------|
| **Purpose** | Full save / restore | API view for clients |
| **Restore** | `Session.from_snapshot(data)` | Not round-trippable alone |
| **Includes** | Memory state, prompt blocks, lorebooks, vision settings, all areas | Grid, objects, agents, events, optional `passive_vision` |
| **Typical use** | Download upload, database blob | `GET /api/state` after a turn |

Save documents include **`snapshot_version`** (currently **5**). Older versions are migrated on import when supported.

---

## Save / load

```python
# Export
save_doc = session.to_save_dict()

# Import (replaces session contents)
restored = Session.from_snapshot(save_doc)
```

**Before import**, register the same **interaction handlers** and **memory modules** referenced in the save.

HTTP: `GET /api/session/export`, `POST /api/session/import` on [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio).

---

## Snapshot for HTTP clients

```python
data = session.snapshot(include_private=True)
```

Top-level shape (multi-area):

- `session_turn`, `active_agent_id`, `active_area_id`
- `agents` — flat list with `area_id` per agent
- `areas` — per-area grid, objects, events (no agents nested)
- `passive_vision` — for active agent when enabled
- `vision_units`, `vision_units_per_tile`

Use **`include_private=True`** when your UI needs `personality`, `private_data`, or other non-public fields.

**`private_data`** is app-owned text — not used in LLM prompts. Set via `session.set_entity_private_data(entity_id, text)`.

---

## Multi-area

- `session.areas` — all area ids
- `session.agent_area[agent_id]` — where each agent lives
- `session.set_active_area(area_id)` — GM edit scope
- `session.create_area(...)` — typed API; switches active area until you change it

Moving entities across areas: `edit_object(..., target_area_id="hall", position=(x, y))`.

---

## Related

- [Building on CampAIgn-RPG-Engine](building-on-campaign-rpg-engine.md) — hosting patterns
- [v0.4.5 changelog](../changelog/v0.4.5-changelog.md) — save format details
