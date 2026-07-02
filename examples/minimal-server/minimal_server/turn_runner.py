"""Compound turn execution for minimal-server."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from realm_fabric import Session
from src.llm.schemas import AgentCompoundTurn
from src.memory import TurnRecord


def _serialize_steps(record: TurnRecord) -> list[dict[str, Any]]:
    return [
        {
            "kind": step.kind,
            "result": step.result,
            "reasoning": step.reasoning,
            "target": step.target,
            "content": step.content,
        }
        for step in record.steps
    ]


def run_manual_turn(
    session: Session,
    turn_payload: dict[str, Any],
    *,
    agent_id: str | None = None,
) -> dict[str, Any]:
    if agent_id is not None and session.get_agent(agent_id) is None:
        return {"ok": False, "message": f"Agent {agent_id!r} not found."}
    agent = session.get_agent(agent_id) if agent_id else session.get_active_agent()
    if agent is None:
        return {"ok": False, "message": "No active agent."}
    if not agent.is_player:
        return {
            "ok": False,
            "message": "Manual turns are only available for player agents.",
        }
    gate = session.gate_agent_turn(agent_id)
    if not gate.ok:
        return {"ok": False, "message": gate.message}
    try:
        compound_turn = AgentCompoundTurn.model_validate(turn_payload)
    except ValidationError as exc:
        return {"ok": False, "message": str(exc)}
    result = session.run_compound_turn(compound_turn, agent_id=agent_id)
    if not result.ok or result.record is None:
        return {"ok": False, "message": result.message}
    return {
        "ok": True,
        "message": result.message,
        "snapshot": session.snapshot(include_private=True),
        "steps": _serialize_steps(result.record),
        "manual_turn": True,
    }


def run_llm_turn(session: Session, *, agent_id: str | None = None) -> dict[str, Any]:
    if agent_id is not None and session.get_agent(agent_id) is None:
        return {"ok": False, "message": f"Agent {agent_id!r} not found."}
    agent = session.get_agent(agent_id) if agent_id else session.get_active_agent()
    if agent is not None and agent.is_player:
        return {
            "ok": False,
            "message": (
                f"{agent.name} is a player agent; use POST /api/turn/manual instead."
            ),
        }
    gate = session.gate_agent_turn(agent_id)
    if not gate.ok:
        return {"ok": False, "message": gate.message}

    from src.llm.client import LLMParseError, get_compound_turn

    try:
        prompt = session.build_prompt(agent_id)
        response = get_compound_turn(prompt)
        compound_turn = response.parsed
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}
    except LLMParseError as exc:
        return {"ok": False, "message": str(exc)}

    result = session.run_compound_turn(compound_turn, agent_id=agent_id)
    if not result.ok or result.record is None:
        return {"ok": False, "message": result.message}
    return {
        "ok": True,
        "message": result.message,
        "snapshot": session.snapshot(include_private=True),
        "steps": _serialize_steps(result.record),
        "manual_turn": False,
    }
