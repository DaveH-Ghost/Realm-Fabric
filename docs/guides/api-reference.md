# API reference

Stable **`campaign_rpg_engine`** surface (**1.0.0**). Import from this package in application code.

```python
import campaign_rpg_engine
assert "Session" in campaign_rpg_engine.__all__
```

CI enforces export drift via `tests/test_public_api_surface.py`.

---

## Core types

| Export | Description |
|--------|-------------|
| `Session` | Simulation entry point |
| `Agent`, `Object`, `Area`, `GridBounds` | World model |
| `AgentCompoundTurn` | Structured turn input (Pydantic) — see [schemas](../schemas/README.md) |
| `ObjectAction`, `ActionKind` | Object interaction definitions |
| `GameProfile`, `load_profile` | Profile loading (`default_compound`) |
| `WorldMutationResult`, `AreaMutationResult` | Typed world-edit outcomes |
| `SessionResult`, `TurnResult` | Operation outcomes |

---

## Session — turns & prompts

| Method | Description |
|--------|-------------|
| `from_profile(profile)` | New session from profile |
| `from_snapshot(data)` | Restore from save dict |
| `run_compound_turn(turn, *, agent_id=None)` | Execute one compound turn |
| `gate_agent_turn(name_or_id=None)` | Pre-turn checks (memory consolidation) |
| `build_prompt(name_or_id=None)` | LLM prompt string |
| `build_prompt_context_for_agent(...)` | Structured prompt context |
| `snapshot(*, include_private=False, ...)` | Client JSON view |
| `to_save_dict()` | Full save document |

---

## Session — typed world editing

| Method | Description |
|--------|-------------|
| `create_object(name, position, *, area_id=None, ...)` | Add object |
| `create_agent(name, position, *, is_player=False, memory_module=None, ...)` | Add agent |
| `edit_object(object_id, *, description, position, target_area_id, ...)` | Update object |
| `edit_agent(agent_id, *, name, personality, position, area_id, ...)` | Update agent |
| `delete_object(object_id)` | Remove object (any area) |
| `delete_agent(agent_id)` | Remove agent |
| `add_object_action(object_id, action)` | Attach `ObjectAction` |
| `remove_object_action(object_id, action_name)` | Remove action |
| `create_area(area_id, *, description, width, height)` | New area |
| `edit_area(area_id, *, description, width, height, ...)` | Update area bounds / description |
| `delete_area(area_id)` | Remove empty area |

All return **`WorldMutationResult`** or **`AreaMutationResult`** with `ok` and `message`.

---

## Session — agents, areas & events

| Method | Description |
|--------|-------------|
| `get_agent(name_or_id)` | Lookup by name or id |
| `get_active_agent()` | Active agent |
| `set_active_agent(name_or_id)` | Switch active agent |
| `set_active_area(area_id)` | Switch GM edit scope |
| `get_area_for_agent(agent)` | Resolve agent's area |
| `transfer_agent(agent_id, dest_area_id, position)` | Move agent between areas |
| `emit_area_event(text, agent_ids=None)` | GM narration → agent memory |

---

## Handlers & memory registration

| Export | Description |
|--------|-------------|
| `register_interaction_handler(id, fn, ...)` | Process-wide handler |
| `list_registered_handlers()`, `is_handler_registered()` | Introspection |
| `run_interaction_handler(...)` | Direct invoke (advanced) |
| `register_memory_module_from_path(path)` | Load custom memory module |
| `MemoryModule` | Protocol type |

---

## Lorebooks & prompts

| Export | Description |
|--------|-------------|
| `Lorebook`, `LoreEntry`, `LorebookScanConfig` | Lorebook model |
| `load_lorebook_from_path`, `load_lorebook_from_dict` | Import ST JSON |
| `match_lorebook_entries`, `render_lorebook` | Matching / render |
| `PromptBlock`, `default_prompt_blocks` | Prompt layout |
| `validate_prompt_blocks`, `prompt_blocks_from_dicts` | Validation |
| `estimate_prompt_tokens`, `get_compound_turn` | LLM helpers |

---

## Snapshots & persistence helpers

| Export | Description |
|--------|-------------|
| `build_save_snapshot`, `load_session_from_snapshot` | Save helpers |
| `build_session_snapshot`, `build_area_snapshot` | Snapshot builders |
| `DEFAULT_AREA_ID` | Default room id (`"room"`) |

---

## Not in `__all__` (internal / app-owned)

| Module | Use |
|--------|-----|
| `campaign_rpg_engine.area_edit` | String parsers for tests and GM command dispatch |
| `campaign_rpg_engine.area_edit_parse` | `tokenize_args` / `parse_field_tokens` |
| `campaign_rpg_engine.session_area_edit` | Typed area CRUD helpers used by `Session` |

CampAIgn-RPG-Studio owns stepper-style command strings in `backend/command_dispatch.py`. Product apps should call typed `Session` methods instead.

**Removed in 1.0:** `Session.run_command()`, `CommandResult`, `realm` console script. See [Migration 0.7 → 1.0](../MIGRATION-0.7-to-1.0.md).

---

## Related

- [Building on CampAIgn-RPG-Engine](building-on-campaign-rpg-engine.md)
- [Overview](overview.md)
- [Changelog index](../changelog/README.md)
