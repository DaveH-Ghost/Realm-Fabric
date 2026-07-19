# CampAIgn RPG Engine

Grid-based LLM agent simulation engine: multi-area worlds, compound turns (move → look → speak → interact/emote), pluggable memory modules, and a stable **`campaign_rpg_engine`** library API. Build your own UI and scenarios on the engine; use [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) as a full GM reference app.

**License:** [MIT](LICENSE) — open source.

**Current version:** **1.5.2** — OpenRouter + Featherless providers, max input-token budget. See [changelog index](docs/changelog/README.md).

## Quick start

```powershell
cd path\to\CampAIgn-RPG-Engine
uv sync
uv run pytest
```

```python
from campaign_rpg_engine import Session, load_profile, AgentCompoundTurn

session = Session.from_profile(load_profile("default_compound"))
session.create_agent(name="Scout", position=(0, 0), personality="Curious.")
session.create_object(name="Chest", position=(2, 1), passive_description="An old chest.")
prompt = session.build_prompt()
result = session.run_compound_turn(
    AgentCompoundTurn(reasoning="look around", action="none"),
)
```

**GM web UI:** clone [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) (separate GitHub repo):

```powershell
cd path\to\CampAIgn-RPG-Studio
uv sync
copy .env.example .env   # optional; or use Settings gear in the UI
uv run campaign-rpg-studio
```

On Windows, if Smart App Control blocks `uv run campaign-rpg-studio`, use `uv run python -m backend.main`. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).

## Environment

Copy [`.env.example`](.env.example) to `.env` and set `OPENROUTER_API_KEY` for LLM turns. Optional `OPENROUTER_MODEL` (default `deepseek/deepseek-v4-flash`). Engine tests mock the LLM — no key required for `uv run pytest`.

CampAIgn-RPG-Studio **Settings** (gear icon) can set API key and model **in memory for the current server process only** — nothing is written to disk.

## Lorebooks

Load SillyTavern-style `.json` lorebooks via `session.load_lorebook_from_path(...)` or CampAIgn-RPG-Studio **Lorebooks** tab. Add a `lorebook` prompt block in Prompt layout to inject matched world info. Not included in the default prompt layout.

## Tests

```powershell
uv run pytest
```

CampAIgn-RPG-Studio API tests live in the [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) repo.

## Documentation

Start at **[docs/README.md](docs/README.md)** — guides, API overview, and changelog index.

| Doc | Topic |
|-----|--------|
| [Building on CampAIgn-RPG-Engine](docs/guides/building-on-campaign-rpg-engine.md) | App integration (typed API, hosting) |
| [Plugin primitives](docs/guides/plugins.md) | Extensions, events, turn verbs, prompt slots (1.2.0) |
| [API reference](docs/guides/api-reference.md) | `campaign_rpg_engine` exports and Session methods |
| [Migration realm-fabric → campaign-rpg-engine](docs/MIGRATION-realm-fabric-to-campaign-rpg-engine.md) | Rename from Realm-Fabric / `realm_fabric` |
| [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) | Full GM reference UI (GitHub) |
| [Roadmap](docs/ROADMAP.md) | Version plans |
| [Long-term goals](LONG_TERM_GOALS.md) | Aspirational features |

Older version notes: [changelog index](docs/changelog/README.md).
