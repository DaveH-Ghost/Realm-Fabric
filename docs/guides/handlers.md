# Interaction handlers

Pluggable code that runs when an agent **interacts** with an object or when a **trigger** fires on a path step.

Introduced in **0.6.1** — replaces hardcoded engine effects. See [v0.6.1 changelog](../changelog/v0.6.1-changelog.md).

---

## Model

Each **`ObjectAction`** on an object has:

| Field | Purpose |
|-------|---------|
| `name` | Action verb shown to LLM (`open`, `kick`, …) |
| `range` | Chebyshev distance (to nearest footprint tile) |
| `result` | Template when agent performs action (`{actor}`, `{object}`) |
| `passive_result` | What witnesses / passive vision see |
| `handler_id` | Registered handler id (optional — flavor-only if omitted) |
| `handler_params` | String key-value params validated per handler |
| `kind` | `"interact"` (default) or `"trigger"` (hidden / zone fires on step) |

Handlers are **process-wide**. Register at startup before loading saves that reference them.

---

## Register a handler

```python
from campaign_rpg_engine import register_interaction_handler, Session

def eat_food(session: Session, agent, obj, action) -> str | None:
    area = session.get_area_for_agent(agent)
    area.remove_object(obj.id)
    return None  # success

register_interaction_handler("eat_food", eat_food, label="Consume object")
```

Return **`None`** on success, or an **error message string** to abort the action.

Reference handlers: [CampAIgn-RPG-Studio/reference_handlers](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio/tree/main/reference_handlers) (`delete_self`, `random_move_self`, `move_area`).

---

## Attach actions (typed API)

```python
from campaign_rpg_engine import ObjectAction

session.create_object(name="Door", position=(2, 1), passive_description="A closed door.")
session.add_object_action(
    "obj_door_01",
    ObjectAction(
        name="open",
        range=1,
        result="You open the door.",
        passive_result="{actor} opens the door.",
        handler_id="move_area",
        handler_params={"dest-area": "hall", "dest-at": "0,0"},
    ),
)
```

Or at create time via `actions={...}` on `create_object`.

---

## Save / load requirement

Saves store `handler_id` + `handler_params`. On **`Session.from_snapshot()`**, every referenced handler must already be registered — same rule as custom memory modules.

---

## Interact vs trigger

| Kind | When it runs |
|------|----------------|
| `interact` | Agent chooses `action: "interact"` with matching `verb` |
| `trigger` | Agent's path step enters range of a hidden (or visible) trigger object |

Triggers can emit area events, run handlers, and optionally delete the object after fire.

---

## Related

- [Building on CampAIgn-RPG-Engine](building-on-campaign-rpg-engine.md)
- [Overview](overview.md) — compound turn action phase
- [API reference](api-reference.md) — `list_registered_handlers()`
