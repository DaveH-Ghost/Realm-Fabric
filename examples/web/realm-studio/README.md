# realm-studio

Example web app for [Realm-Fabric](https://github.com/) — wraps the engine `Session` API over HTTP.

**Location:** `examples/web/realm-studio` in the Realm-Fabric repo.

**Status:** **V0.4.4** — compact prompt + JSON schema, plus V0.4.3 create-agent memory and V0.4.2 emote/speak/debug.

## Quick start

```powershell
cd examples\web\realm-studio
uv sync
copy ..\..\..\.env.example .env   # set OPENROUTER_API_KEY for Run turn
uv run realm-studio
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) (opens automatically). Right-click the grid to edit; switch **Area** for multi-room sessions; **Emit event…** for GM narration; **Run turn ▶** for the active agent.

## Prerequisites

- Python ≥3.11
- [uv](https://docs.astral.sh/uv/)
- Realm-Fabric engine at repo root (path dependency on `realm-fabric`)
- **OpenRouter API key** for LLM turns (area edits and object actions work without it)

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

- **Grid** — white pannable map scoped to the **active area**; token images from `appearance` (else name chips); active agent ★
- **Area toolbar** — dropdown (room / hall / …); **+ Area**, **Edit area**, **Delete area**
- **Agents elsewhere** — sidebar list when agents are in other areas
- **Right-click** — create/edit/delete on tiles and tokens; **Play as** for agents; **Manage actions…** on objects
- **Create agent** — memory module dropdown (`recent_turns`, `salient_turns`, `rolling_summary`) and module-specific options
- **Manage actions…** — add/edit/remove object actions; effect picker (`delete_self`, `random_move_self`, `move_area`); **?** on result/passive fields lists template variables
- **Stacked tiles** — manage menu when multiple entities share a cell
- **Toolbar** — active-agent dropdown; **Emit event…**; **Run turn ▶** (hover shows ~input token estimate)
- **Sidebar** — session meta (**Units** / **Units per tile**), passive vision, recent GM events, turn log, **Prompt layout**, **Last prompt (debug)**, **Last response (debug)**
- **Refresh** — manual re-fetch; edits and turns auto-refresh

**Note:** `realm-studio` and the terminal `realm` CLI use **separate in-memory sessions** — CLI edits do not appear in the browser.

**Demo areas:** server seeds **room** (default profile) plus empty **hall**. Add a door object and a `move_area` action via **Manage actions…** or CLI to test cross-area travel.

## Token images

Entity `appearance` is an image path (engine field). realm-studio resolves it under `/static/` — e.g. `tokens/explorer.svg` → `/static/tokens/explorer.svg`.

Bundled demo tokens live in `frontend/tokens/`. Add PNG/SVG files there and set the path in create/edit modals or via CLI:

```text
edit-agent agent_01 appearance "tokens/explorer.svg"
create-object name "Crate" appearance "tokens/ball.svg" at 3,3
```

Empty path falls back to a name chip. Broken paths fall back at render time.

## Prompt layout (V0.4.1)

Open **Prompt layout** in the sidebar to edit how the compound prompt is assembled:

- **Reorder** — ↑↓ on `slot`, `text`, and `section` blocks
- **Edit** — `text` glue and `section` bodies (`compound_rules`, `output_format`)
- **Add / remove** — block catalog (`GET /api/prompt-block-catalog`)
- **Slot ⚙** — Character (name / personality / description), Passive vision (you-are-at, coordinates, direction+distance), Move instructions (coordinate moves)
- **Reset to default** — restore profile block list
- **Preview** — full rendered prompt; syncs **Last prompt (debug)** when open

**Units** and **Units per tile** under Session meta enable relative bearing (`South-East of you, 10 ft away`), move-speed lines, and **object action range** labels in session units. Direction and distance requires both fields.

Changes are session-scoped (in-memory until server restart).

## Compound turns (V0.4.2)

Engine pipeline: **move → look → speak → turn action** (`interact` | `emote` | `none`).

- **Speak** — optional dialogue via `content`; can combine with interact or emote in one turn
- **Emote** — non-verbal gestures (`turn_action: "emote"`, past-tense `action_name`, optional `target`)
- **Breaking:** `"turn_action": "speak"` and `confidence` / `emotion` JSON fields removed — use `content` + `"turn_action": "none"` for speech

After **Run turn**, open **Last prompt (debug)** or **Last response (debug)** in the sidebar to inspect the rendered prompt and raw LLM JSON.

## Agent move speed

Set **Move speed (steps per turn)** in create/edit agent modals, or via CLI (`move-speed N`). Blank = unlimited (teleport). Limited speed uses Chebyshev pathing — agents may stop **towards** a target without reaching it in one turn.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Liveness |
| `GET` | `/api/state` | Full session snapshot (all areas, `actions_detail` on objects) |
| `POST` | `/api/command` | `{ "line": "create-object ..." }` → `run_command` |
| `POST` | `/api/active-agent` | `{ "name_or_id": "Explorer" }` → `set_active_agent` |
| `POST` | `/api/active-area` | `{ "area_id": "hall" }` → set GM active area |
| `POST` | `/api/create-area` | Create empty area |
| `POST` | `/api/edit-area` | Edit area description / grid size |
| `POST` | `/api/delete-area` | Delete empty area |
| `POST` | `/api/turn` | LLM compound turn (optional `agent_id`, `include_examples`); returns `prompt`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `prompt_tokens_estimate`, `llm_response`, `steps` |
| `POST` | `/api/event` | `{ "text": "..." }` → `emit_area_event` (no turn consumed) |
| `GET` | `/api/prompt` | Build compound prompt (debug); includes `prompt_tokens` estimate |
| `GET` | `/api/prompt-blocks` | Session prompt block list |
| `PUT` | `/api/prompt-blocks` | `{ "blocks": [...] }` — reorder / edit static sections |
| `POST` | `/api/prompt-blocks/reset` | Restore profile default blocks |
| `GET` | `/api/prompt-slots` | Slot names + preview snippets (optional `agent_id`) |
| `GET` | `/api/prompt-block-catalog` | Addable block types, slot/section options, section defaults |
| `PUT` | `/api/vision-units` | `{ "units": "ft", "units_per_tile": 5 }` — session distance labels |
| `GET` | `/api/memory-modules` | Memory module catalog for create-agent (ids, defaults, option ranges) |
| `GET` | `/api/interact-template-vars` | Placeholders for object action result/passive text |

See [v0.4.3-changelog.md](../../../docs/v0.4.3-changelog.md) for V0.4.3 release notes. [v0.4.2-changelog.md](../../../docs/v0.4.2-changelog.md) covers emote and debug panels.

## Tests

```powershell
uv run pytest
```

**51** smoke/integration tests (`test_api.py`, `test_snapshot_compat.py`) via FastAPI `TestClient` (mocked LLM — no API key or running server).

From repo root, engine tests remain separate:

```powershell
cd ..\..\..
uv run pytest
```

(396 engine tests as of 0.4.2e.)

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

**V0.5+** — swappable turn schemas, tile blockers, cross-area vision — see [ROADMAP.md](../../../docs/ROADMAP.md).
