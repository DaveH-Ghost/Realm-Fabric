# Realm-Fabric documentation

**Realm-Fabric** is a grid-based LLM agent simulation engine with a stable **`realm_fabric`** library API, a `realm` CLI for debugging, and reference applications ([realm-studio](../examples/web/realm-studio/), [minimal-server](../examples/minimal-server/)).

**Current release:** **0.7.0** — see [changelog/v0.7.0-changelog.md](changelog/v0.7.0-changelog.md).

---

## New here?

1. [Overview](guides/overview.md) — mental model (Session, areas, compound turns)
2. [Building on Realm-Fabric](guides/building-on-realm-fabric.md) — install, typed API, hosting
3. [minimal-server](../examples/minimal-server/) — runnable thin HTTP example

---

## Guides

| Guide | Description |
|-------|-------------|
| [Overview](guides/overview.md) | Architecture and core concepts |
| [Building on Realm-Fabric](guides/building-on-realm-fabric.md) | App integration entry point |
| [Compound turns](guides/turns.md) | `AgentCompoundTurn`, LLM vs player agents |
| [Interaction handlers](guides/handlers.md) | Pluggable object behavior |
| [Persistence & snapshots](guides/persistence.md) | `to_save_dict()` vs `snapshot()` |
| [Memory & lorebooks](guides/memory-and-lorebooks.md) | Modules, lore injection, prompt blocks |
| [API reference](guides/api-reference.md) | `realm_fabric` exports and Session methods |
| [CLI reference](guides/cli.md) | `realm` stepper (debug / GM tooling) |
| [LLM turn schemas](schemas/README.md) | `AgentCompoundTurn` JSON shape |

---

## Planning & history

| Doc | Description |
|-----|-------------|
| [Roadmap](ROADMAP.md) | Version plans (0.7.1 engine follow-up; external demo 0.1.0+) |
| [Changelog index](changelog/README.md) | Per-version release notes and old readiness checklists |
| [Long-term goals](../LONG_TERM_GOALS.md) | Aspirational / out-of-scope items |

---

## Examples

| Example | Role |
|---------|------|
| [minimal-server](../examples/minimal-server/) | Thin FastAPI — start here for HTTP apps |
| [realm-studio](../examples/web/realm-studio/) | Full GM grid UI (reference only) |
| [reference_handlers](../examples/reference_handlers/) | Copy-paste interaction handler pattern |
| [custom_memory](../examples/custom_memory/) | Custom memory module sample |

---

## Stability

- Import from **`realm_fabric`** in application code.
- **`src.*`** is for the CLI, tests, and reference clients — not semver-guaranteed.
- Save format version: **`snapshot_version`** in save JSON (currently **4**).
