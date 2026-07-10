# Migration: 0.7.x → 1.0.0

CampAIgn-RPG-Engine **1.0.0** is a **library-first** release. The engine ships as a single `campaign_rpg_engine` package on PyPI. The bundled `realm` CLI and `Session.run_command()` string layer are removed.

**CampAIgn-RPG-Studio** (GM web app) lives in a [separate GitHub repository](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) and is not published to PyPI.

---

## Install

```powershell
uv add "campaign-rpg-engine>=1.0.0"
```

Pre-1.0 archive: branch `archive/0.7.x` on GitHub (tag `v0.7.2`).

---

## Breaking changes

### Package layout

| 0.7.x | 1.0.0 |
|-------|-------|
| `src/` tree + thin `campaign_rpg_engine` facade | Single `campaign_rpg_engine/` package at repo root |
| `from src.session import Session` (tests/CLI) | `from campaign_rpg_engine import Session` |
| `import campaign_rpg_engine` re-exported from `src/` | Import only `campaign_rpg_engine` in apps |

### CLI removed

| 0.7.x | 1.0.0 |
|-------|-------|
| `uv run realm` stepper | **Removed** — use CampAIgn-RPG-Studio or your own UI |
| `docs/guides/cli.md` | **Removed** — see [API reference](guides/api-reference.md) |
| `[project.scripts] realm = ...` | **Removed** from `pyproject.toml` |

### `Session.run_command()` removed

| 0.7.x | 1.0.0 |
|-------|-------|
| `session.run_command("create-object ...")` | `session.create_object(name=..., position=..., ...)` |
| `session.run_command("create-agent ...")` | `session.create_agent(name=..., position=..., ...)` |
| `session.run_command("edit-agent ...")` | `session.edit_agent(agent_id, ...)` |
| `session.run_command("emit-event ...")` | `session.emit_area_event(text)` |
| `session.run_command("list")` | `session.snapshot()` |
| `CommandResult` | **Removed** — use `WorldMutationResult`, `SessionResult`, `TurnResult` |

See [Building on CampAIgn-RPG-Engine](guides/building-on-campaign-rpg-engine.md) for the full typed API table.

### Public exports trimmed

Removed from `campaign_rpg_engine.__all__` (import submodules if you own GM string dispatch):

- `CommandResult`
- `create_area_from_args`, `edit_area_from_args` (moved to `campaign_rpg_engine.area_edit`)
- `edit_agent_for_session`, `edit_object_for_session`
- `parse_area_event_arg` (use `session.emit_area_event` or `campaign_rpg_engine.area_event`)

### CampAIgn-RPG-Studio location

| 0.7.x | 1.0.0 |
|-------|-------|
| `examples/web/campaign-rpg-studio/` in monorepo | [github.com/DaveH-Ghost/CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) |

Studio depends on `campaign-rpg-engine` from PyPI (or local editable during co-dev). It keeps stepper-style GM commands in **`backend/command_dispatch.py`**, which imports `campaign_rpg_engine.area_edit` helpers — not `Session.run_command()`.

### Examples removed in 1.0

| 0.7.x | 1.0.0 |
|-------|-------|
| `examples/minimal-server/` | **Removed** — use [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) `backend/` as HTTP reference |
| `examples/reference_handlers/` | **Removed** — canonical copy in [CampAIgn-RPG-Studio/reference_handlers](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio/tree/main/reference_handlers) |
| `examples/custom_memory/` | **Removed** — sample + upload UI in [CampAIgn-RPG-Studio/fixtures/custom_memory](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio/tree/main/fixtures/custom_memory) |

Use typed `Session` methods in your HTTP handlers. See [Building on CampAIgn-RPG-Engine](guides/building-on-campaign-rpg-engine.md).

---

## Migration checklist

1. **Bump dependency:** `campaign-rpg-engine>=1.0.0`
2. **Fix imports:** replace all `src.*` with `campaign_rpg_engine`
3. **Replace `run_command`:** map each command to typed `Session` methods (table above)
4. **Remove CLI assumptions:** no `uv run realm` in docs or CI
5. **Re-test saves:** `snapshot_version` 4 unchanged; `Session.from_snapshot()` API stable
6. **Studio:** use external repo; verify against 1.0 wheel (`uv build` + install `.whl`)

---

## Unchanged (stable)

- `AgentCompoundTurn` schema and compound-turn simulation
- `Session.run_compound_turn()`, `build_prompt()`, `snapshot()`, `to_save_dict()`
- Interaction handler registration API
- Memory modules and lorebooks
- `snapshot_version: 4` save format (v1–v3 import still supported)

---

## Related

- [API reference](guides/api-reference.md)
- [Building on CampAIgn-RPG-Engine](guides/building-on-campaign-rpg-engine.md)
- [Changelog index](changelog/README.md)
