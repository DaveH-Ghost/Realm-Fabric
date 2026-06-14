"""realm-studio FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.area_api import create_area as api_create_area
from backend.area_api import delete_area as api_delete_area
from backend.area_api import dispatch_area_cli_command
from backend.area_api import edit_area as api_edit_area
from backend.schemas import (
    ActiveAgentRequest,
    ActiveAreaRequest,
    CommandRequest,
    CreateAreaRequest,
    DeleteAreaRequest,
    EditAreaRequest,
    EventRequest,
    TurnRequest,
)
from backend.session_store import get_session_store
from backend.snapshot_compat import normalize_state_snapshot
from backend.turn_runner import run_llm_turn

_STUDIO_DIR = Path(__file__).resolve().parent.parent
_FRONTEND_DIR = _STUDIO_DIR / "frontend"
_REPO_ROOT = _STUDIO_DIR.parent.parent.parent
_ENGINE_SRC = _REPO_ROOT / "src"


def create_app() -> FastAPI:
    app = FastAPI(title="realm-studio", version="0.4.0c2")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/state")
    def get_state() -> dict:
        snap = get_session_store().session.snapshot(include_private=True)
        return normalize_state_snapshot(snap)

    @app.post("/api/command")
    def post_command(body: CommandRequest) -> dict[str, object]:
        """Run a stepper-style command (create/edit/delete, listings)."""
        session = get_session_store().session
        line = body.line.strip()
        parts = line.split(None, 1)
        cmd = parts[0].lower().replace("-", "_") if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in {"create_area", "edit_area", "delete_area"}:
            return dispatch_area_cli_command(session, cmd, arg)

        result = session.run_command(line)
        return {"ok": result.ok, "message": result.message}

    @app.post("/api/create-area")
    def post_create_area(body: CreateAreaRequest) -> dict[str, object]:
        """Create a new empty area (same pattern as /api/event)."""
        session = get_session_store().session
        return api_create_area(
            session,
            area_id=body.area_id.strip().lower(),
            description=body.description,
            width=body.width,
            height=body.height,
        )

    @app.post("/api/edit-area")
    def post_edit_area(body: EditAreaRequest) -> dict[str, object]:
        """Edit an area description and/or grid size."""
        session = get_session_store().session
        return api_edit_area(
            session,
            area_id=body.area_id.strip().lower(),
            description=body.description,
            width=body.width,
            height=body.height,
        )

    @app.post("/api/delete-area")
    def post_delete_area(body: DeleteAreaRequest) -> dict[str, object]:
        """Delete an empty area."""
        session = get_session_store().session
        return api_delete_area(session, area_id=body.area_id.strip().lower())

    @app.post("/api/active-agent")
    def post_active_agent(body: ActiveAgentRequest) -> dict[str, object]:
        result = get_session_store().session.set_active_agent(body.name_or_id)
        return {"ok": result.ok, "message": result.message}

    @app.post("/api/active-area")
    def post_active_area(body: ActiveAreaRequest) -> dict[str, object]:
        session = get_session_store().session
        result = session.set_active_area(body.area_id)
        payload: dict[str, object] = {"ok": result.ok, "message": result.message}
        if result.ok:
            payload["snapshot"] = normalize_state_snapshot(
                session.snapshot(include_private=True)
            )
        return payload

    @app.post("/api/turn")
    def post_turn(body: TurnRequest) -> dict[str, object]:
        return run_llm_turn(
            get_session_store().session,
            agent_id=body.agent_id,
            include_examples=body.include_examples,
        )

    @app.get("/api/prompt")
    def get_prompt(agent_id: str | None = None) -> dict[str, object]:
        session = get_session_store().session
        if agent_id is not None and session.get_agent(agent_id) is None:
            return {"ok": False, "message": f"Agent {agent_id!r} not found."}
        prompt = session.build_prompt(agent_id)
        return {
            "ok": True,
            "prompt": prompt,
            "length": len(prompt),
            "include_examples": session.include_examples,
        }

    @app.post("/api/event")
    def post_event(body: EventRequest) -> dict[str, object]:
        session = get_session_store().session
        result = session.emit_area_event(body.text)
        payload: dict[str, object] = {"ok": result.ok, "message": result.message}
        if result.ok:
            payload["snapshot"] = normalize_state_snapshot(
                session.snapshot(include_private=True)
            )
        return payload

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_FRONTEND_DIR / "index.html")

    if _FRONTEND_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

    return app


app = create_app()

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765
_DEFAULT_URL = f"http://{_DEFAULT_HOST}:{_DEFAULT_PORT}"


def main() -> None:
    import argparse
    import threading
    import webbrowser

    import uvicorn

    parser = argparse.ArgumentParser(prog="realm-studio")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the default browser on startup",
    )
    args = parser.parse_args()

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(_DEFAULT_URL)).start()

    reload_dirs = [str(_STUDIO_DIR)]
    if _ENGINE_SRC.is_dir():
        reload_dirs.append(str(_ENGINE_SRC))

    uvicorn.run(
        "backend.app:app",
        host=_DEFAULT_HOST,
        port=_DEFAULT_PORT,
        reload=True,
        reload_dirs=reload_dirs,
    )


if __name__ == "__main__":
    main()
