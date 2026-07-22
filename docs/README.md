# CampAIgn-RPG-Engine documentation

**CampAIgn-RPG-Engine** is a grid-based LLM agent simulation engine with a stable **`campaign_rpg_engine`** library API. The GM host is **[CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio)** (GitHub only) — it owns the world/session today; player clients attaching later are planned, not implemented.

**Current release:** **1.7.3** — Verb pathing parity with interact (`path_range_from_turn`, honor explicit move in range) and `area_event` session hook for plugins. See [changelog index](changelog/README.md). Library-first since 1.0; [Migration 0.7 → 1.0](MIGRATION-0.7-to-1.0.md) still applies for older upgrades.

---

## New here?

1. [Overview](guides/overview.md) — mental model (Session, areas, compound turns)
2. [Building on CampAIgn-RPG-Engine](guides/building-on-campaign-rpg-engine.md) — install, typed API, hosting
3. [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) — GM host (grid, lorebooks, handlers, session save/load)

---

## Guides

| Guide | Description |
|-------|-------------|
| [Overview](guides/overview.md) | Architecture and core concepts |
| [Building on CampAIgn-RPG-Engine](guides/building-on-campaign-rpg-engine.md) | App integration entry point |
| [Compound turns](guides/turns.md) | `AgentCompoundTurn`, LLM vs player agents |
| [Interaction handlers](guides/handlers.md) | Pluggable object behavior |
| [Persistence & snapshots](guides/persistence.md) | `to_save_dict()` vs `snapshot()` |
| [Memory & lorebooks](guides/memory-and-lorebooks.md) | Modules, lore injection, prompt blocks |
| [Plugins](guides/plugins.md) | Extensions, events, turn verbs, prompt slots (1.2.0) |
| [API reference](guides/api-reference.md) | `campaign_rpg_engine` exports and Session methods |
| [LLM turn schemas](schemas/README.md) | `AgentCompoundTurn` JSON shape |
| [UML diagrams](UML/README.md) | Mermaid architecture diagrams (1.6.0) |

---

## Planning & history

| Doc | Description |
|-----|-------------|
| [Migration 0.7 → 1.0](MIGRATION-0.7-to-1.0.md) | Breaking changes for library-only 1.0 |
| [Roadmap](ROADMAP.md) | Version plans |
| [Changelog index](changelog/README.md) | Per-version release notes |
| [Long-term goals](../LONG_TERM_GOALS.md) | Aspirational / out-of-scope items |

---

## Examples in this repo

| Path | Role |
|------|------|
| [examples/README.md](../examples/README.md) | Points to CampAIgn-RPG-Studio for runnable apps |
| [examples/lorebook/](../examples/lorebook/) | Sample SillyTavern lorebook JSON |

Engine tests use [`tests/fixtures/`](../tests/fixtures/) (not published in the PyPI wheel).

---

## Stability

- Import from **`campaign_rpg_engine`** in application code (`campaign_rpg_engine.__all__` is semver-guaranteed).
- Submodules such as `campaign_rpg_engine.area_edit` are for tests and app-owned command dispatch — not top-level exports.
- Save format version: **`snapshot_version`** in save JSON (currently **5**).
