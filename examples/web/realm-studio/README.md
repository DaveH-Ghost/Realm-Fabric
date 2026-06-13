# realm-studio

Example web app for [Realm-Fabric](https://github.com/) — wraps the engine `Session` API over HTTP.

**Location:** `examples/web/realm-studio` in the Realm-Fabric repo.

**Status:** **0.3.1c** — grid UI + right-click create/edit/delete and active-agent switch.

## Prerequisites

- Python ≥3.11
- [uv](https://docs.astral.sh/uv/)
- Realm-Fabric engine at repo root (this example uses a path dependency on `realm-fabric`)

## Setup

From this directory:

```powershell
cd examples\web\realm-studio
uv sync
```

## Run (dev server)

```powershell
uv run realm-studio
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) — opens automatically in your default browser (5×5 grid with Explorer, ball, sign). Use `--no-browser` to skip:

```powershell
uv run realm-studio --no-browser
```

Alternative:

```powershell
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8765 --reload
```

## UI (0.3.1b–c)

- **Grid** — agents (green) and objects (purple) at snapshot positions; active agent marked with ★
- **Right-click** empty tile → create object or agent; right-click chip → edit, delete, or **Play as** (agents)
- **Stacked tiles** — manage menu lists entities on the cell
- **Toolbar** — active-agent dropdown (same as Play as; no turn consumed)
- **Refresh** — manual re-fetch; successful edits auto-refresh

**Note:** `realm-studio` and the terminal `realm` CLI use separate in-memory sessions — CLI edits do not appear in the browser.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | `{ "ok": true }` |
| `GET` | `/api/state` | Engine `Session.snapshot()` |
| `POST` | `/api/command` | `{ "line": "create-object ..." }` → `run_command` |
| `POST` | `/api/active-agent` | `{ "name_or_id": "Explorer" }` → `set_active_agent` |

LLM turns arrive in **0.3.1d** (`POST /api/turn`).

## Tests

```powershell
uv run pytest
```

Uses FastAPI `TestClient` — no API key or running server required.

## Environment

**0.3.1c** does not call the LLM. For **0.3.1d**, copy `.env` with `OPENROUTER_API_KEY` to the repo root or this folder.

## Dev: test stacked objects (temporary)

To verify tile scrollbars, start the server with 10 extra objects on tile **(3, 3)**:

```powershell
$env:REALM_STUDIO_DEV_STACK = "1"
uv run realm-studio
```

Unset the variable (or omit it) for the normal demo room.
