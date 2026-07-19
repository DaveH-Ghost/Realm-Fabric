# API reference

Stable **`campaign_rpg_engine`** surface (**1.5.2**). Import from this package in application code.

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
| `create_decoration(kind, image, *, area_id=None, ...)` | Add background or sprite decoration |
| `update_decoration(decoration_id, *, ...)` | Update decoration fields |
| `delete_decoration(decoration_id)` | Remove decoration |
| `reorder_decoration(decoration_id, direction)` | Move decoration in z-order (`"up"` / `"down"`) |

World/area edits return **`WorldMutationResult`** or **`AreaMutationResult`**; decoration edits return **`DecorationMutationResult`** — all with `ok` and `message`.

### Area templates (1.3.1)

| Function | Description |
|----------|-------------|
| `export_area_template(session, area_id, *, name, include_hidden_objects)` | Portable whole-area blueprint |
| `export_decoration_template(decoration)` | Decoration entry without id |
| `spawn_area_from_template(session, template, *, area_id, mode)` | Create (`new`) or replace (`replace`) area from template |
| `validate_area_template(data)` | Validate area template JSON |

Returns **`AreaTemplateMutationResult`** from `spawn_area_from_template`.

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

## Handlers & memory

| Export | Description |
|--------|-------------|
| `register_interaction_handler(id, fn, ...)` | Process-wide handler |
| `list_registered_handlers()`, `is_handler_registered()` | Introspection |
| `run_interaction_handler(...)` | Direct invoke; may return ``ActionOutcome`` (1.4.1) |
| `run_named_handler(...)` | Invoke any registered handler by id with explicit params (1.4.2) |
| `collect_prefixed_params(...)` | Strip a branch prefix from nested handler params (1.4.2) |
| `handler_catalog_entry(id)` | Catalog dict with description, ``param_fields``, ``summary_template`` (1.4.2) |
| `loaded_module_ids()` | Built-in memory module ids (`recent_turns`, `salient_turns`, `rolling_summary`, `affinity`) |
| `MemoryModule` | Protocol type |
| `AffinityModule` | Relationships (-10…+10) + rolling summary (1.5.0) |
| `AFFINITY_MIN` / `AFFINITY_MAX` / `DEFAULT_RELATIONSHIP_SUMMARY_MAX_CHARS` | Affinity constants (1.5.0) |

### Plugin primitives (1.2.0)

| Export | Description |
|--------|-------------|
| `register_turn_verb(id, fn, ...)` | Compound `action: "verb"`; optional `path_range` + `path_target_from_turn` (1.4.0) |
| `list_registered_turn_verbs()`, `run_turn_verb(...)`, `run_turn_verb_phases(...)` | Turn verb introspection / dispatch |
| `ActionOutcome.passive_witness_exclude_agent_ids` | Skip passive witness for named observers (1.4.0) |
| `register_prompt_slot(name, renderer, ...)` | Named prompt layout slot |
| `register_event_listener(event, fn, *, plugin_id=...)` | Session event hook |
| `unregister_event_listeners(plugin_id)` | Remove listeners for a plugin |
| `emit_session_event(session, event, **payload)` | App-emitted events (e.g. `session_loaded`) |

`Session.get_extension` / `Session.set_extension` store plugin state in `session.extensions` (save round-trip). See [plugins.md](plugins.md).

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
