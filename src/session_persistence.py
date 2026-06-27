"""
session_persistence.py

V0.4.5 — full session save/load (world + memory + prompt blocks).

Distinct from ``snapshot.build_session_snapshot`` (API view for web clients).
"""

from __future__ import annotations

from typing import Any

from src.agent import Agent
from src.area import Area, GridBounds
from src.area_event import AreaEventRecord
from src.effect_spec import EffectSpec
from src.game_profile import load_profile
from src.memory import Memory
from src.memory_modules.registry import (
    create_module_from_state,
    export_module_state,
    is_module_loaded,
)
from src.object import Object
from src.object_action import ObjectAction
from src.lorebook.models import Lorebook
from src.prompt_blocks import prompt_blocks_from_dicts
from src.snapshot import serialize_area_block, serialize_object

SNAPSHOT_VERSION = 2
SUPPORTED_SNAPSHOT_VERSIONS = frozenset({1, 2})

__all__ = [
    "SNAPSHOT_VERSION",
    "build_save_snapshot",
    "load_session_from_snapshot",
    "validate_snapshot_modules",
]


def validate_snapshot_modules(data: dict[str, Any]) -> None:
    """Ensure every agent memory module_id in a save is currently loaded."""
    agents = data.get("agents") or []
    missing: list[str] = []
    seen: set[str] = set()
    for agent_data in agents:
        memory = agent_data.get("memory") or {}
        module_id = memory.get("module_id")
        if not module_id or module_id in seen:
            continue
        seen.add(module_id)
        if not is_module_loaded(module_id):
            missing.append(module_id)
    for module_id in missing:
        raise ValueError(
            f"Memory module '{module_id}' is not found. "
            "Load the module before loading this save."
        )


def _engine_version() -> str:
    try:
        from realm_fabric import __version__

        return __version__
    except ImportError:
        return "unknown"


def _position_tuple(position: list[int]) -> tuple[int, int]:
    return int(position[0]), int(position[1])


def deserialize_object_action(name: str, data: dict[str, Any]) -> ObjectAction:
    effects = [
        EffectSpec(name=e["name"], params=dict(e.get("params", {})))
        for e in data.get("effects", [])
    ]
    return ObjectAction(
        name=name,
        range=int(data["range"]),
        result=data["result"],
        passive_result=data["passive_result"],
        effects=effects,
    )


def deserialize_object(data: dict[str, Any]) -> Object:
    actions_detail = data.get("actions_detail", {})
    actions = {
        name: deserialize_object_action(name, detail)
        for name, detail in actions_detail.items()
    }
    return Object(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        position=_position_tuple(data["position"]),
        passive_description=data.get("passive_description", ""),
        actions=actions,
        appearance=data.get("appearance", ""),
        blocks_movement=bool(data.get("blocks_movement", True)),
        movement_exceptions=list(data.get("movement_exceptions", [])),
    )


def deserialize_area(area_id: str, data: dict[str, Any]) -> Area:
    del area_id  # key is authoritative on load
    grid = data["grid"]
    area = Area(
        bounds=GridBounds(
            min_x=int(grid["min_x"]),
            max_x=int(grid["max_x"]),
            min_y=int(grid["min_y"]),
            max_y=int(grid["max_y"]),
        ),
        area_description=data["area_description"],
    )
    for obj_data in data.get("objects", []):
        area.add_object(deserialize_object(obj_data))
    area._recent_events = [
        AreaEventRecord(session_turn=int(ev["session_turn"]), text=ev["text"])
        for ev in data.get("recent_events", [])
    ]
    return area


def serialize_agent_for_save(agent: Agent, *, area_id: str) -> dict[str, Any]:
    x, y = agent.position
    return {
        "id": agent.id,
        "name": agent.name,
        "personality": agent.personality,
        "position": [x, y],
        "passive_description": agent.passive_description,
        "description": agent.description,
        "passive_result": agent.passive_result,
        "last_action": agent.last_action,
        "appearance": agent.appearance,
        "move_speed": agent.move_speed,
        "blocks_movement": agent.blocks_movement,
        "movement_exceptions": list(agent.movement_exceptions),
        "is_player": agent.is_player,
        "area_id": area_id,
        "memory": {
            "looked_at": sorted(agent.memory.looked_at),
            "ever_looked": sorted(agent.memory.ever_looked),
            "module_id": agent.memory.module_id,
            "module_state": export_module_state(agent.memory.module),
        },
    }


def deserialize_agent(data: dict[str, Any]) -> Agent:
    memory_data = data["memory"]
    module = create_module_from_state(
        memory_data["module_id"],
        memory_data["module_state"],
    )
    memory = Memory(module=module)
    memory.restore_look_state(
        memory_data.get("looked_at", []),
        memory_data.get("ever_looked", []),
    )
    return Agent(
        id=data["id"],
        name=data["name"],
        personality=data.get("personality", ""),
        position=_position_tuple(data["position"]),
        passive_description=data.get("passive_description", ""),
        description=data.get("description", ""),
        memory=memory,
        passive_result=data.get("passive_result", ""),
        last_action=data.get("last_action"),
        appearance=data.get("appearance", ""),
        move_speed=data.get("move_speed"),
        blocks_movement=bool(data.get("blocks_movement", False)),
        movement_exceptions=list(data.get("movement_exceptions", [])),
        is_player=bool(data.get("is_player", False)),
    )


def _prepare_session_for_save(session: object) -> None:
    from src.session import Session

    if not isinstance(session, Session):
        raise TypeError(f"Expected Session, got {type(session)!r}")
    for area in session.areas.values():
        for agent in area.agents:
            agent.memory.ensure_ready_for_turn()


def build_save_snapshot(session: object) -> dict[str, Any]:
    """Build a JSON-friendly full session save document."""
    from src.session import Session

    if not isinstance(session, Session):
        raise TypeError(f"Expected Session, got {type(session)!r}")

    _prepare_session_for_save(session)

    prompt_blocks = None
    if not session.prompt_blocks_use_default():
        prompt_blocks = [block.to_dict() for block in session.get_prompt_blocks()]

    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "engine_version": _engine_version(),
        "profile_id": session.profile.profile_id,
        "include_examples": session.include_examples,
        "session_turn": session.session_turn,
        "active_agent_id": session.active_agent_id,
        "active_area_id": session.active_area_id,
        "vision_units": session.vision_units,
        "vision_units_per_tile": session.vision_units_per_tile,
        "lorebook_char_budget": session.lorebook_char_budget,
        "lorebook_scan_config": session.lorebook_scan_config.to_dict(),
        "lorebooks": [book.to_dict() for book in session.list_lorebooks()],
        "prompt_blocks": prompt_blocks,
        "agent_area": dict(session.agent_area),
        "areas": {
            area_id: serialize_area_block(area, include_private=True)
            for area_id, area in session.areas.items()
        },
        "agents": [
            serialize_agent_for_save(
                agent,
                area_id=session.agent_area.get(agent.id, ""),
            )
            for area in session.areas.values()
            for agent in area.agents
        ],
    }


def load_session_from_snapshot(data: dict[str, Any]):
    """Reconstruct a ``Session`` from a save document."""
    from src.session import Session

    version = data.get("snapshot_version")
    if version not in SUPPORTED_SNAPSHOT_VERSIONS:
        raise ValueError(
            f"Unsupported snapshot_version {version!r} "
            f"(supported: {sorted(SUPPORTED_SNAPSHOT_VERSIONS)})"
        )

    validate_snapshot_modules(data)

    profile_id = data.get("profile_id")
    if not profile_id:
        raise ValueError("Missing profile_id in session snapshot")
    profile = load_profile(profile_id)

    areas_data = data.get("areas")
    if not areas_data:
        raise ValueError("Session snapshot has no areas")

    areas = {
        area_id: deserialize_area(area_id, area_data)
        for area_id, area_data in areas_data.items()
    }

    agent_area: dict[str, str] = dict(data.get("agent_area", {}))
    for agent_data in data.get("agents", []):
        agent = deserialize_agent(agent_data)
        area_id = agent_data.get("area_id") or agent_area.get(agent.id)
        if not area_id or area_id not in areas:
            raise ValueError(
                f"Agent {agent.id!r} references unknown area {area_id!r}"
            )
        areas[area_id].add_agent(agent)
        agent_area[agent.id] = area_id

    active_area_id = data.get("active_area_id")
    if active_area_id not in areas:
        raise ValueError(f"Unknown active_area_id: {active_area_id!r}")

    active_agent_id = data.get("active_agent_id")
    session = Session(
        areas=areas,
        agent_area=agent_area,
        profile=profile,
        include_examples=bool(data.get("include_examples", False)),
        active_agent_id=active_agent_id,
        active_area_id=active_area_id,
    )
    session.session_turn = int(data.get("session_turn", 0))
    session.vision_units = str(data.get("vision_units", ""))
    per_tile = data.get("vision_units_per_tile")
    session.vision_units_per_tile = int(per_tile) if per_tile is not None else None
    session.lorebook_char_budget = int(
        data.get("lorebook_char_budget", session.lorebook_char_budget)
    )
    from src.lorebook.scan_config import LorebookScanConfig

    session.lorebook_scan_config = LorebookScanConfig.from_dict(
        data.get("lorebook_scan_config")
    )

    lorebooks_raw = data.get("lorebooks") or []
    if lorebooks_raw:
        for item in lorebooks_raw:
            book = Lorebook.from_dict(item)
            session.update_lorebook(book)

    prompt_blocks = data.get("prompt_blocks")
    if prompt_blocks is not None:
        blocks, err = prompt_blocks_from_dicts(prompt_blocks)
        if err:
            raise ValueError(f"Invalid prompt_blocks in snapshot: {err}")
        session.set_prompt_blocks(blocks)

    return session
