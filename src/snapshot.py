"""
snapshot.py

V0.3.0b — JSON-friendly area state for web clients and future save/load.

Produces plain dicts (JSON-serializable) from live ``Area`` / ``Session`` state.
Does not expose LLM-only fields in the public snapshot unless requested.
"""

from __future__ import annotations

from typing import Any

from src.agent import Agent
from src.area import Area
from src.object import Object
from src.perception import build_passive_vision

DEFAULT_AREA_ID = "room"


def _position_list(position: tuple[int, int]) -> list[int]:
    x, y = position
    return [x, y]


def serialize_object(obj: Object, *, include_private: bool = False) -> dict[str, Any]:
    """Public object fields for clients."""
    data: dict[str, Any] = {
        "id": obj.id,
        "name": obj.name,
        "position": _position_list(obj.position),
        "actions": sorted(obj.actions.keys()),
        "appearance": obj.appearance,
    }
    if include_private:
        data["passive_description"] = obj.passive_description
        data["description"] = obj.description
    return data


def serialize_agent(
    agent: Agent,
    *,
    area_id: str | None = None,
    include_private: bool = False,
) -> dict[str, Any]:
    """Public agent fields for clients."""
    data: dict[str, Any] = {
        "id": agent.id,
        "name": agent.name,
        "position": _position_list(agent.position),
        "passive_result": agent.passive_result,
        "memory_module": agent.memory.module_id,
        "appearance": agent.appearance,
        "move_speed": agent.move_speed,
    }
    if area_id is not None:
        data["area_id"] = area_id
    if include_private:
        data["personality"] = agent.personality
        data["passive_description"] = agent.passive_description
        data["description"] = agent.description
    return data


def serialize_area_block(
    area: Area,
    *,
    include_private: bool = False,
) -> dict[str, Any]:
    """Per-area grid, description, objects, and events (no agents)."""
    return {
        "grid": {
            "min_x": area.min_x,
            "max_x": area.max_x,
            "min_y": area.min_y,
            "max_y": area.max_y,
        },
        "area_description": area.area_description,
        "objects": [
            serialize_object(o, include_private=include_private) for o in area.get_objects()
        ],
        "recent_events": [
            {"session_turn": event.session_turn, "text": event.text}
            for event in area.recent_events
        ],
    }


def build_session_snapshot(
    session: object,
    *,
    include_private: bool = False,
    include_passive_vision: bool = True,
) -> dict[str, Any]:
    """
    Build a JSON-friendly snapshot of a multi-area ``Session``.

    Agents are listed once at the top level with ``area_id``; each area block
    holds grid, description, objects, and recent events only.
    """
    from src.session import Session

    if not isinstance(session, Session):
        raise TypeError(f"Expected Session, got {type(session)!r}")

    snap: dict[str, Any] = {
        "session_turn": session.session_turn,
        "active_agent_id": session.active_agent_id,
        "active_area_id": session.active_area_id,
        "areas": {
            area_id: serialize_area_block(area, include_private=include_private)
            for area_id, area in session.areas.items()
        },
        "agents": [
            serialize_agent(
                agent,
                area_id=session.agent_area.get(agent.id),
                include_private=include_private,
            )
            for area in session.areas.values()
            for agent in area.agents
        ],
    }

    if include_passive_vision and session.active_agent_id:
        agent = session.get_active_agent()
        area = session.get_area_for_agent(agent)
        snap["passive_vision"] = build_passive_vision(agent, area)

    return snap


def build_area_snapshot(
    area: Area,
    *,
    active_agent_id: str | None = None,
    session_turn: int = 0,
    include_private: bool = False,
    include_passive_vision: bool = True,
) -> dict[str, Any]:
    """
    Build a JSON-friendly snapshot of one area.

    When ``active_agent_id`` is set and ``include_passive_vision`` is true,
    adds ``passive_vision`` for that agent (engine-built; clients need not
    reimplement ``[?]`` rules).
    """
    snap: dict[str, Any] = {
        "grid": {
            "min_x": area.min_x,
            "max_x": area.max_x,
            "min_y": area.min_y,
            "max_y": area.max_y,
        },
        "area_description": area.area_description,
        "session_turn": session_turn,
        "active_agent_id": active_agent_id,
        "agents": [serialize_agent(a, include_private=include_private) for a in area.agents],
        "objects": [
            serialize_object(o, include_private=include_private) for o in area.get_objects()
        ],
        "recent_events": [
            {"session_turn": event.session_turn, "text": event.text}
            for event in area.recent_events
        ],
    }

    if include_passive_vision and active_agent_id:
        agent = area.get_agent_by_id(active_agent_id)
        if agent is not None:
            snap["passive_vision"] = build_passive_vision(agent, area)

    return snap


def snapshot_to_json_ready(data: dict[str, Any]) -> dict[str, Any]:
    """Return *data* unchanged; exists as a hook for future normalization."""
    return data
