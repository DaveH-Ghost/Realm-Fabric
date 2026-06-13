"""
realm-studio FastAPI application (V0.3.1a+).

Exposes engine state via ``Session.snapshot()`` for the web frontend.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.schemas import ActiveAgentRequest, CommandRequest, TurnRequest
from backend.session_store import get_session_store
from backend.turn_runner import run_llm_turn

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def create_app() -> FastAPI:
    app = FastAPI(
        title="realm-studio",
        description="Example web UI for Realm-Fabric",
        version="0.3.1",
    )

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
        """JSON snapshot of the live session (grid, agents, objects, passive vision)."""
        return get_session_store().session.snapshot()

    @app.post("/api/command")
    def post_command(body: CommandRequest) -> dict[str, object]:
        """Run a stepper-style command (create/edit/delete, listings)."""
        result = get_session_store().session.run_command(body.line)
        return {"ok": result.ok, "message": result.message}

    @app.post("/api/active-agent")
    def post_active_agent(body: ActiveAgentRequest) -> dict[str, object]:
        """Change the active agent without consuming a turn."""
        result = get_session_store().session.set_active_agent(body.name_or_id)
        return {"ok": result.ok, "message": result.message}

    @app.post("/api/turn")
    def post_turn(body: TurnRequest) -> dict[str, object]:
        """Run one LLM compound turn for the active (or specified) agent."""
        return run_llm_turn(
            get_session_store().session,
            agent_id=body.agent_id,
            include_examples=body.include_examples,
        )

    @app.get("/api/prompt")
    def get_prompt(agent_id: str | None = None) -> dict[str, object]:
        """Build the compound-turn prompt for the active (or specified) agent."""
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
    """Run dev server: ``uv run realm-studio`` from this example directory."""
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

    uvicorn.run(
        "backend.app:app",
        host=_DEFAULT_HOST,
        port=_DEFAULT_PORT,
        reload=True,
        reload_dirs=[str(Path(__file__).resolve().parent.parent)],
    )


if __name__ == "__main__":
    main()
