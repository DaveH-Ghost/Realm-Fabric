"""FastAPI app for minimal-server."""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from minimal_server.schemas import CommandRequest, ManualTurnRequest, TurnRequest
from minimal_server.session_store import get_session_store, reset_session_store
from minimal_server.turn_runner import run_llm_turn, run_manual_turn


def create_app() -> FastAPI:
    app = FastAPI(title="realm-minimal-server", version="0.7.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/state")
    def get_state() -> dict:
        store = get_session_store()
        return store.session.snapshot(include_private=True)

    @app.post("/api/turn")
    def post_turn(body: TurnRequest) -> dict:
        store = get_session_store()
        return run_llm_turn(store.session, agent_id=body.agent_id)

    @app.post("/api/turn/manual")
    def post_manual_turn(body: ManualTurnRequest) -> dict:
        store = get_session_store()
        return run_manual_turn(
            store.session,
            body.turn,
            agent_id=body.agent_id,
        )

    @app.get("/api/session/export")
    def export_session() -> Response:
        store = get_session_store()
        payload = json.dumps(store.export_session(), indent=2)
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="realm-save.json"'},
        )

    @app.post("/api/session/import")
    def import_session(data: dict) -> dict[str, bool]:
        store = get_session_store()
        try:
            store.import_session(data)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/api/command")
    def post_command(body: CommandRequest) -> dict:
        """Debug / GM only — apps should use typed Session methods."""
        store = get_session_store()
        result = store.session.run_command(body.command)
        return {
            "ok": result.ok,
            "message": result.message,
            "snapshot": store.session.snapshot(include_private=True),
        }

    return app


app = create_app()

__all__ = ["app", "create_app", "reset_session_store"]
