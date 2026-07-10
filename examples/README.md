# Examples

CampAIgn-RPG-Engine **1.0** ships as a library only. Runnable reference apps live in separate repos:

| Reference | Where |
|-----------|--------|
| **GM web UI** (grid, lorebooks, handlers, memory upload) | [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) |
| Interaction handlers (`delete_self`, `move_area`, …) | [CampAIgn-RPG-Studio/reference_handlers](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio/tree/main/reference_handlers) |
| Custom memory module sample + upload UI | [CampAIgn-RPG-Studio/fixtures/custom_memory](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio/tree/main/fixtures/custom_memory) |

### In this repo

| Path | Role |
|------|------|
| [lorebook/](lorebook/) | Sample SillyTavern lorebook JSON for docs/tests |

Engine tests use copies under [`tests/fixtures/`](../tests/fixtures/) — not published in the PyPI wheel.

**Integrating the library:** [docs/guides/building-on-campaign-rpg-engine.md](../docs/guides/building-on-campaign-rpg-engine.md).
