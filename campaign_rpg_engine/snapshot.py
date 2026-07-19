"""
snapshot.py

V0.3.0b — JSON-friendly area state for web clients and future save/load.

Produces plain dicts (JSON-serializable) from live ``Area`` / ``Session`` state.
Does not expose LLM-only fields in the public snapshot unless requested.
"""

from __future__ import annotations

from typing import Any

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.decoration import (
    DECORATION_KIND_BACKGROUND,
    Decoration,
)
from campaign_rpg_engine.object import Object
from campaign_rpg_engine.object_action import ObjectAction
from campaign_rpg_engine.perception import build_passive_vision

DEFAULT_AREA_ID = "room"


def _position_list(position: tuple[int, int]) -> list[int]:
    x, y = position
    return [x, y]


def serialize_object_action(action: ObjectAction) -> dict[str, Any]:
    data: dict[str, Any] = {
        "range": action.range,
        "result": action.result,
        "passive_result": action.passive_result,
        "handler_id": action.handler_id,
        "handler_params": dict(action.handler_params),
        "kind": action.kind,
        "enabled": action.enabled,
    }
    if action.kind == "trigger":
        data["halt_movement"] = action.halt_movement
        data["delete_after_trigger"] = action.delete_after_trigger
        data["trigger_exceptions"] = list(action.trigger_exceptions)
    return data


def serialize_object(obj: Object, *, include_private: bool = False) -> dict[str, Any]:
    """Public object fields for clients."""
    data: dict[str, Any] = {
        "id": obj.id,
        "name": obj.name,
        "position": _position_list(obj.position),
        "actions": sorted(obj.actions.keys()),
        "actions_detail": {
            name: serialize_object_action(action) for name, action in sorted(obj.actions.items())
        },
        "appearance": obj.appearance,
        "blocks_movement": obj.blocks_movement,
        "movement_exceptions": list(obj.movement_exceptions),
        "width": obj.width,
        "height": obj.height,
        "hidden": obj.hidden,
        "private_data": obj.private_data,
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
        "blocks_movement": agent.blocks_movement,
        "movement_exceptions": list(agent.movement_exceptions),
        "is_player": agent.is_player,
        "private_data": agent.private_data,
    }
    if area_id is not None:
        data["area_id"] = area_id
    if include_private:
        data["personality"] = agent.personality
        data["passive_description"] = agent.passive_description
        data["description"] = agent.description
    return data


def serialize_decoration(decoration: Decoration) -> dict[str, Any]:
    """Public decoration fields for clients."""
    data: dict[str, Any] = {
        "id": decoration.id,
        "kind": decoration.kind,
        "image": decoration.image,
        "z_index": decoration.z_index,
    }
    if decoration.kind == DECORATION_KIND_BACKGROUND:
        data["repeat"] = decoration.repeat
        data["width"] = decoration.width
        data["height"] = decoration.height
    else:
        data["x"] = decoration.x
        data["y"] = decoration.y
        data["width"] = decoration.width
        data["height"] = decoration.height
    return data


def serialize_area_block(
    area: Area,
    *,
    include_private: bool = False,
) -> dict[str, Any]:
    """Per-area grid, description, objects, decorations, and events (no agents)."""
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
        "decorations": [serialize_decoration(d) for d in area.decorations],
        "recent_events": [
            {"session_turn": event.session_turn, "text": event.text} for event in area.recent_events
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
    from campaign_rpg_engine.session import Session

    if not isinstance(session, Session):
        raise TypeError(f"Expected Session, got {type(session)!r}")

    snap: dict[str, Any] = {
        "session_turn": session.session_turn,
        "active_agent_id": session.active_agent_id,
        "active_area_id": session.active_area_id,
        "vision_units": session.vision_units,
        "vision_units_per_tile": session.vision_units_per_tile,
        "coordinate_mode": session.coordinate_mode,
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

    if include_private:
        snap["extensions"] = dict(session.extensions)

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
        "decorations": [serialize_decoration(d) for d in area.decorations],
        "recent_events": [
            {"session_turn": event.session_turn, "text": event.text} for event in area.recent_events
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
