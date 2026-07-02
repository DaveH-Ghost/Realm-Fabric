# realm-studio

Example web app for [Realm-Fabric](https://github.com/) — wraps the engine `Session` API over HTTP.

**Location:** `examples/web/realm-studio` in the Realm-Fabric repo.

**Status:** **V0.6.0** — grid simulation UI: footprints, blocking, hidden triggers, player agents, grouped entity modals.

## Quick start

```powershell
cd examples\web\realm-studio
uv sync
copy ..\..\..\.env.example .env   # optional; or use Settings gear
uv run realm-studio
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) (opens automatically). Right-click the grid to edit; switch **Area** for multi-room sessions; **Emit event…** for GM narration; **Run turn ▶** for the active agent.

### Windows Smart App Control

If `uv run realm-studio` is blocked, start the server directly:

```powershell
uv run python -m backend.main
```

Use `--no-browser` to skip opening the browser.

## Prerequisites

- Python ≥3.11
- [uv](https://docs.astral.sh/uv/)
- Realm-Fabric engine at repo root (path dependency on `realm-fabric` **`0.6.0`**)
- **OpenRouter API key** for LLM turns (area edits and object actions work without it)

## Grid simulation (V0.6.0)

- **Footprint overlay** — multi-tile objects and agents on `#grid-overlay`
- **Blocking** — create/edit object: Simulation group → blocks movement + exceptions
- **Hidden objects** — ghost markers; **Hide** / **Reveal** in context menu
- **Create hidden trigger…** — hidden object + `trigger` action in one flow (width/height for tripwires / room zones)
- **Manage actions…** — `interact` vs `trigger` kinds
- **Player agents** — manual compound-turn form instead of LLM on **Run turn ▶**
- **Entity modals** — collapsible groups (Basic, Descriptions, Placement, Simulation, Advanced)
- **Private data** (Advanced) — app-owned text via API; not used by studio simulation or prompts

## Lorebooks (V0.5.0)

Use the **Lorebooks** tab (top nav) to load SillyTavern-style `.json` files and edit entries (enable, constant, keys, content, add/delete). The right-hand **Keyword scan sources** panel shows what text is scanned for keyword matches (per active agent) and lets you toggle each source, including **passive vision**. **Download JSON** exports the session copy in ST load format. Each loaded book gets its own id (from the filename).

To inject lore into prompts:

1. Load one or more lorebooks in the **Lorebooks** tab.
2. On **Main**, open **Prompt layout** → add a **Dynamic slot** → choose **lorebook** → pick which book.
3. Save layout. Matched entries appear as `World info:` in the prompt (constants always; others when keywords match).

Lorebooks are saved in session JSON. New saves from **0.6.0** use **`snapshot_version: 3`** (v1–v2 import still works).

## Settings (V0.4.6)

Click the **gear** icon (next to save/load in the header):

1. **LLM** — API key (password field; shows “configured” after set; never returned by API) and model name. Applied **in memory only** for this server process.
2. **Memory modules** — upload a `.py` custom module; list shows loaded customs (id + filename). Re-upload overwrites the same `MODULE_ID`.

Create-agent memory dropdown lists **only loaded modules** (three built-ins always present + any uploaded customs). Upload a module in Settings before it appears in the dropdown.

## UI

- **Grid** — pannable map for the **active area**; token images from `appearance`; active agent ★; ghost styling for hidden objects
- **Header** — save/load session, **settings gear**, area toolbar, **Run turn ▶**
- **Right-click** — create/edit/delete; **Create hidden trigger…**; **Manage actions…** on objects
- **Create agent** — memory module dropdown from `GET /api/memory-modules` + module-specific options
- **Sidebar** — session meta (Units), events, turn log, **Prompt layout**, debug panels

`realm-studio` and the terminal `realm` CLI use **separate in-memory sessions**.

## Session save/load

- **Save** — downloads `realm-session-<timestamp>.json`
- **Load** — file picker replaces the in-memory session

If the save uses a **custom** memory module, upload/load that module in Settings (or CLI `add-memory-module`) **before** import — otherwise import fails with a clear error.

## Custom memory modules

See [examples/custom_memory/README.md](../../../examples/custom_memory/README.md) for the module contract. Uploaded files are cached under `.custom_modules/` (gitignored). The server reloads them on startup (and after dev-server reload), so custom modules survive restarts.

## API (selected)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/settings/llm` | `{ model, key_configured }` — no secret |
| `PUT` | `/api/settings/llm` | Set in-memory `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` |
| `GET` | `/api/memory-modules` | Loaded modules only (built-ins + customs) |
| `POST` | `/api/memory-modules/upload` | Multipart `.py` → register |
| `GET` | `/api/session/export` | Full save JSON |
| `POST` | `/api/session/import` | Load save (validates modules) |
| `POST` | `/api/turn` | LLM compound turn |
| `POST` | `/api/turn/manual` | Player agent compound turn JSON |
| `POST` | `/api/command` | CLI-style command; returns **snapshot** on success |
| `PUT` | `/api/entity-private-data` | Set `private_data` on agent/object (not CLI) |

Full route list and older features: [v0.6.0-changelog](../../../docs/changelog/v0.6.0-changelog.md), [v0.4.5-changelog](../../../docs/changelog/v0.4.5-changelog.md).

## Tests

```powershell
uv run pytest
```

HTTP smoke tests via FastAPI `TestClient` (mocked LLM — no API key or running server).

From repo root:

```powershell
cd ..\..\..
uv run pytest
```

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | For **Run turn** | [OpenRouter](https://openrouter.ai/) API key |
| `OPENROUTER_MODEL` | No | Default: `deepseek/deepseek-v4-flash` |

`python-dotenv` loads `.env` at server start. **Settings gear** overrides these in memory until restart (not written to disk).

## What's next

**V0.6.1** — pluggable interaction handlers (interact + trigger effects) — see [ROADMAP.md](../../../docs/ROADMAP.md).
