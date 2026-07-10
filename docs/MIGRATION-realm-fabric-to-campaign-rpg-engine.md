# Migration: realm-fabric → campaign-rpg-engine

The project was renamed to **CampAIgn** — clearer branding for the map-based LLM RPG engine and reference GM app.

| Old | New |
|-----|-----|
| PyPI `realm-fabric` | PyPI `campaign-rpg-engine` |
| `from realm_fabric import …` | `from campaign_rpg_engine import …` |
| GitHub `Realm-Fabric` | [CampAIgn-RPG-Engine](https://github.com/DaveH-Ghost/CampAIgn-RPG-Engine) |
| GitHub `Realm-Studio` | [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) |
| `uv run realm-studio` | `uv run campaign-rpg-studio` |

## Install

```powershell
uv add campaign-rpg-engine
```

## Code changes

```python
# Before
from realm_fabric import Session, AgentCompoundTurn

# After
from campaign_rpg_engine import Session, AgentCompoundTurn
```

Submodules follow the same rename (`realm_fabric.area_edit` → `campaign_rpg_engine.area_edit`).

## Session saves

Save JSON format is unchanged (`snapshot_version` still **4**). The `engine_version` field in exports will show the new package version after re-save.

## PyPI `realm-fabric`

The old package name may remain on PyPI with a deprecation notice. **Do not start new projects on `realm-fabric`.**

## See also

- [Migration 0.7 → 1.0](MIGRATION-0.7-to-1.0.md) — CLI removal, `run_command`, package layout
- [Building on CampAIgn-RPG-Engine](guides/building-on-campaign-rpg-engine.md)
