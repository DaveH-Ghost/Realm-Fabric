# Changelog & version history

Release notes and historical implementation checklists for CampAIgn-RPG-Engine.

**Current:** [v1.6.1-changelog.md](v1.6.1-changelog.md) — joint release with Studio 1.6.1 (engine = 1.6.0 content).

---

## Recent releases

| Version | Summary |
|---------|---------|
| [1.6.1](v1.6.1-changelog.md) | PyPI/tag train with Studio 1.6.1 (no engine API delta vs 1.6.0) |
| [1.6.0](v1.6.0-changelog.md) | Ruff/CI, edit+templates packages, Mermaid UML, GM-host docs |
| [1.5.2](v1.5.2-changelog.md) | Featherless provider, token budget, missing-`{` JSON repair |
| [1.5.1](v1.5.1-changelog.md) | Enabled actions, `[far]` vision, `[emote]` tagging, interact verb hints |
| [1.5.0](v1.5.0-changelog.md) | Affinity memory — relationships (-10…+10) + rolling summary |
| [1.4.2](v1.4.2-changelog.md) | ``run_named_handler`` / ``collect_prefixed_params`` (plugin follow-ups) |
| [1.4.1](v1.4.1-changelog.md) | Interaction handlers may return ``ActionOutcome`` (fail templates) |
| [1.4.0](v1.4.0-changelog.md) | Turn verb pathing (opt-in); `passive_witness_exclude_agent_ids` |
| [1.3.1](v1.3.1-changelog.md) | Area templates — export/spawn whole areas (`kind: "area"`) |
| [1.3.0](v1.3.0-changelog.md) | Scene decorations — background + sprite layers (`snapshot_version` 5) |
| [1.2.1](v1.2.1-changelog.md) | Entity templates — export/spawn objects and agents without ids or placement |
| [1.2.0](v1.2.0-changelog.md) | Session extensions, event registry, turn verbs, prompt slots, `plugin_slot` blocks |
| [1.0.0](v1.0.0-changelog.md) | Single `campaign_rpg_engine` package; no CLI; typed API only; Studio external |
| [0.7.2](v0.7.2-changelog.md) | `from __future__ import annotations` across engine for Python 3.12 |
| [0.7.1](v0.7.1-changelog.md) | Straight-line movement fix, targeted `emit_area_event`, PyPI version read |
| [0.7.0](v0.7.0-changelog.md) | Public API, typed `Session` world editing, app docs, minimal-server |
| [0.6.1](v0.6.1-changelog.md) | Pluggable interaction handlers, snapshot v4 |
| [0.6.0](v0.6.0-changelog.md) | Grid simulation, blocking, triggers, footprints, snapshot v3 |
| [0.5.0](v0.5.0-changelog.md) | Lorebooks, lorebook prompt slot |
| [0.4.6](v0.4.6-changelog.md) | Custom memory modules |
| [0.4.5](v0.4.5-changelog.md) | Full session save/load round-trip |

---

## Older releases

| Version | Doc |
|---------|-----|
| 0.4.4 | [v0.4.4-changelog.md](v0.4.4-changelog.md) |
| 0.4.3 | [v0.4.3-changelog.md](v0.4.3-changelog.md) |
| 0.4.2 | [v0.4.2-changelog.md](v0.4.2-changelog.md) |
| 0.4.1 | [v0.4.1-changelog.md](v0.4.1-changelog.md) |
| 0.4.0 | [v0.4.0-changelog.md](v0.4.0-changelog.md) |
| 0.3.2 | [v0.3.2-changelog.md](v0.3.2-changelog.md) |
| 0.3.1 | [v0.3.1-changelog.md](v0.3.1-changelog.md) |
| 0.3.0 | [v0.3.0-changelog.md](v0.3.0-changelog.md) |
| 0.2.5 | [v0.2.5-changelog.md](v0.2.5-changelog.md) |

---

## Historical readiness checklists

Pre-0.3 planning documents (superseded by changelogs for newer work):

| Doc | Era |
|-----|-----|
| [v0.2-implementation-readiness-checklist.md](v0.2-implementation-readiness-checklist.md) | V0.2 compound turns, object actions |
| [v0.1-implementation-readiness-checklist.md](v0.1-implementation-readiness-checklist.md) | V0.1 multi-agent, editing |
| [v0-implementation-readiness-checklist.md](v0-implementation-readiness-checklist.md) | Original V0 (historical) |

See also [ROADMAP.md](../ROADMAP.md).
