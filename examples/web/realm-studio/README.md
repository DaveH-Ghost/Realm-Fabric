# realm-studio

Example web app for [Realm-Fabric](https://github.com/) — wraps the engine `Session` API over HTTP.

**Location:** `examples/web/realm-studio` in the Realm-Fabric repo.

**Status:** **V0.3.2b** in progress — adds **Emit event…** (GM area events) on top of V0.3.1.

## Quick start

```powershell
cd examples\web\realm-studio
uv sync
copy ..\..\..\.env.example .env   # set OPENROUTER_API_KEY for Run turn
uv run realm-studio
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) (opens automatically). Right-click the grid to edit; **Emit event…** for GM narration; **Run turn ▶** for the active agent.

## Prerequisites

- Python ≥3.11
- [uv](https://docs.astral.sh/uv/)
- Realm-Fabric engine at repo root (path dependency on `realm-fabric`)
- **OpenRouter API key** for LLM turns (area edits work without it)

## Run (dev server)

```powershell
uv run realm-studio
```

Use `--no-browser` to skip opening the browser:

```powershell
uv run realm-studio --no-browser
```

Alternative:

```powershell
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8765 --reload
```

## UI

- **Grid** — agents (green) and objects (purple); active agent marked with ★
- **Right-click** — create/edit/delete on tiles and entity chips; **Play as** for agents
- **Stacked tiles** — manage menu when multiple entities share a cell
- **Toolbar** — active-agent dropdown; **Emit event…**; **Run turn ▶**
- **Sidebar** — session meta, passive vision, recent GM events, turn log
- **Refresh** — manual re-fetch; edits and turns auto-refresh

**Note:** `realm-studio` and the terminal `realm` CLI use **separate in-memory sessions** — CLI edits do not appear in the browser.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Liveness |
| `GET` | `/api/state` | `Session.snapshot()` |
| `POST` | `/api/command` | `{ "line": "create-object ..." }` → `run_command` |
| `POST` | `/api/active-agent` | `{ "name_or_id": "Explorer" }` → `set_active_agent` |
| `POST` | `/api/turn` | LLM compound turn (optional `agent_id`, `include_examples`) |
| `POST` | `/api/event` | `{ "text": "..." }` → `emit_area_event` (no turn consumed) |
| `GET` | `/api/prompt` | Build compound prompt (debug) |

See [v0.3.2-changelog.md](../../../docs/v0.3.2-changelog.md) for V0.3.2 slices.

## Tests

```powershell
uv run pytest
```

16 smoke/integration tests via FastAPI `TestClient` (mocked LLM — no API key or running server).

From repo root, engine tests remain separate:

```powershell
cd ..\..\..
uv run pytest
```

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | For **Run turn** | [OpenRouter](https://openrouter.ai/) API key |
| `OPENROUTER_MODEL` | No | Default: `deepseek/deepseek-v4-flash` |

`python-dotenv` loads `.env` from the working directory when the server starts.

## Dev: stacked objects on one tile

```powershell
$env:REALM_STUDIO_DEV_STACK = "1"
uv run realm-studio
```

Adds 10 objects on tile **(3, 3)** to test scrollbars. Omit for the normal demo room.

## What's next

**V0.3.2** (planned): GM **area events** and grid **appearance** — see [v0.3.2-changelog](docs/v0.3.2-changelog.md).
