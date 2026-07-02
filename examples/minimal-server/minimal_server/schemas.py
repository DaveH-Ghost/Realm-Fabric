"""Pydantic request bodies for minimal-server."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TurnRequest(BaseModel):
    agent_id: str | None = None


class ManualTurnRequest(BaseModel):
    agent_id: str | None = None
    turn: dict[str, Any] = Field(default_factory=dict)


class CommandRequest(BaseModel):
    command: str
