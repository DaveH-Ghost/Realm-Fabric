# realm-studio

Example web app for [Realm-Fabric](https://github.com/) — wraps the engine `Session` API over HTTP.

**Location:** `examples/web/realm-studio` in the Realm-Fabric repo.

**Status:** **0.3.1b** — grid UI from snapshot; right-click editing in 0.3.1c.

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

## API (0.3.1a)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | `{ "ok": true }` |
| `GET` | `/api/state` | Engine `Session.snapshot()` — grid, agents, objects, passive vision |

LLM turns and area-edit commands arrive in **0.3.1c** / **0.3.1d**.

## Tests

```powershell
uv run pytest
```

Uses FastAPI `TestClient` — no API key or running server required.

## Environment

**0.3.1a** does not call the LLM. For future slices, copy `.env` with `OPENROUTER_API_KEY` to the repo root or this folder as documented in 0.3.1d.

## Dev: test stacked objects (temporary)

To verify tile scrollbars, start the server with 10 extra objects on tile **(3, 3)**:

```powershell
$env:REALM_STUDIO_DEV_STACK = "1"
uv run realm-studio
```

Unset the variable (or omit it) for the normal demo room. Removed when the UI can create objects (**0.3.1c**).
