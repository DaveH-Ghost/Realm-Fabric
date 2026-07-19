# 1.6.0 structural audit

**Purpose:** Snapshot of Engine + Studio structure before moderate reorganization. Diagrams in this folder reflect the **post-1.6.0** layout; this note records what we changed and why.

**Baseline:** 1.5.2

---

## Hotspots (pre-1.6.0)

### Engine (`campaign_rpg_engine/`)

| Module | ~Lines | Issue |
|--------|-------:|-------|
| `session.py` | 1213 | Large facade — keep as public API surface; do not split in 1.6.0 |
| `area_edit.py` | 1160 | String + typed helpers; circular with `world_edit_api` |
| `world_edit_api.py` | 440 | Typed mutations; imports private appliers from `area_edit` |
| `prompt_blocks.py` | 526 | Large but already cohesive — leave |
| `session_area_edit.py` / `decoration_edit.py` / `area_edit_parse.py` | 200–240 | Same edit cluster |
| `entity_templates.py` / `area_templates.py` / `interact_templates.py` | — | Template cluster at package root |

Already clean packages: `llm/`, `memory_modules/`, `actions/`, `simulation.py`.

### Studio

| Area | Issue |
|------|--------|
| `backend/app.py` | ~72 routes in one module |
| `frontend/ui.js` / `api.js` | Large monoliths (~1.2k–1.7k) |
| `session_store.py` | Single-session process singleton — intentional GM-host seam |

---

## Move vs keep (1.6.0)

| Action | Targets | Compat |
|--------|---------|--------|
| **Move** → `edit/` | `area_edit`, `area_edit_parse`, `world_edit_api`, `session_area_edit`, `decoration_edit` | Shim modules at old top-level paths |
| **Move** → `templates/` | `entity_templates`, `area_templates`, `interact_templates` | Shim modules at old top-level paths |
| **Keep** | `session.py`, `llm/`, `memory_modules/`, `actions/`, `simulation.py`, `__all__` | Public API unchanged |
| **Untangle** | Shared field appliers between `area_edit` ↔ `world_edit_api` | Internal helper in `edit/` |

Studio and plugins import `campaign_rpg_engine.area_edit`, `world_edit_api`, `interact_templates` by path — shims must preserve those.

---

## Non-goals (1.6.0)

- Player-client protocol, auth, multi-session Studio
- mypy-strict / full type coverage
- Splitting `session.py` into many public classes
- Renaming `reference_handlers/`
- Frontend framework rewrite
- New LLM/gameplay features

---

## Product positioning

- **Engine** — simulation library (`campaign_rpg_engine`)
- **Studio** — GM **host** (world authority), not a “reference demo”
- **Future** — player clients attach to Studio; not implemented in 1.6.0
