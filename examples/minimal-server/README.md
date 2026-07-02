# minimal-server

Thin **FastAPI** reference for embedding Realm-Fabric in an HTTP service. Bootstraps a demo world with the **typed `Session` API** (no CLI strings). For a full GM UI see [realm-studio](../web/realm-studio/).

## Run

```powershell
cd examples\minimal-server
uv sync
uv run realm-minimal-server
```

Open [http://127.0.0.1:8770/api/health](http://127.0.0.1:8770/api/health).

## Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness |
| GET | `/api/state` | `session.snapshot()` |
| POST | `/api/turn` | LLM compound turn (active agent) |
| POST | `/api/turn/manual` | Player agent turn (`AgentCompoundTurn` JSON) |
| GET | `/api/session/export` | Download save JSON |
| POST | `/api/session/import` | Replace session from save JSON |
| POST | `/api/command` | **Debug only** — forwards to `run_command` |

## App integration pattern

1. Depend on `realm-fabric>=0.7.0`.
2. Register handlers at startup.
3. Bootstrap scenarios with `session.create_*` methods.
4. Expose your own routes; use this server as a starting point, not a framework.

See [building-on-realm-fabric.md](../../docs/guides/building-on-realm-fabric.md).
