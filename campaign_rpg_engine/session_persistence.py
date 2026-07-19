"""
session_persistence.py

V0.4.5 — full session save/load (world + memory + prompt blocks).
V0.6.1 — snapshot v4 with interaction handlers.
"""

from __future__ import annotations

from typing import Any

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area, GridBounds
from campaign_rpg_engine.area_event import AreaEventRecord
from campaign_rpg_engine.decoration import (
    DECORATION_KIND_BACKGROUND,
    DECORATION_KIND_SPRITE,
    Decoration,
)
from campaign_rpg_engine.game_profile import load_profile
from campaign_rpg_engine.interaction_handlers.registry import is_handler_registered
from campaign_rpg_engine.lorebook.models import Lorebook
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.memory_modules.registry import (
    create_module_from_state,
    export_module_state,
    is_module_loaded,
    unknown_memory_module_message,
)
from campaign_rpg_engine.object import Object
from campaign_rpg_engine.object_action import ObjectAction, migrate_legacy_effects_to_handler
from campaign_rpg_engine.prompt_blocks import prompt_blocks_from_dicts
from campaign_rpg_engine.snapshot import serialize_area_block

SNAPSHOT_VERSION = 5
SUPPORTED_SNAPSHOT_VERSIONS = frozenset({1, 2, 3, 4, 5})

__all__ = [
    "SNAPSHOT_VERSION",
    "build_save_snapshot",
    "load_session_from_snapshot",
    "validate_snapshot_modules",
    "validate_snapshot_handlers",
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
        raise ValueError(unknown_memory_module_message(module_id))


def validate_snapshot_handlers(data: dict[str, Any]) -> None:
    """Ensure every object action handler_id in a save is currently registered."""
    missing: list[str] = []
    seen: set[str] = set()
    for area_data in (data.get("areas") or {}).values():
        for obj_data in area_data.get("objects", []):
            for detail in (obj_data.get("actions_detail") or {}).values():
                handler_id = detail.get("handler_id")
                if not handler_id or handler_id in seen:
                    continue
                seen.add(handler_id)
                if not is_handler_registered(handler_id):
                    missing.append(handler_id)
    for handler_id in missing:
        raise ValueError(
            f"Interaction handler '{handler_id}' is not registered. "
            "Register the handler before loading this save."
        )


def _engine_version() -> str:
    try:
        from campaign_rpg_engine import __version__

        return __version__
    except ImportError:
        return "unknown"


def _position_tuple(position: list[int]) -> tuple[int, int]:
    return int(position[0]), int(position[1])


def deserialize_object_action(name: str, data: dict[str, Any]) -> ObjectAction:
    if "handler_id" in data or "handler_params" in data:
        handler_id = data.get("handler_id")
        handler_params = {str(k): str(v) for k, v in dict(data.get("handler_params", {})).items()}
    else:
        handler_id, handler_params = migrate_legacy_effects_to_handler(
            list(data.get("effects", []))
        )

    return ObjectAction(
        name=name,
        range=int(data["range"]),
        result=data["result"],
        passive_result=data["passive_result"],
        handler_id=handler_id,
        handler_params=handler_params,
        kind=data.get("kind", "interact"),
        halt_movement=bool(data.get("halt_movement", False)),
        delete_after_trigger=bool(data.get("delete_after_trigger", True)),
        trigger_exceptions=list(data.get("trigger_exceptions", [])),
        enabled=bool(data.get("enabled", True)),
    )


def deserialize_object(data: dict[str, Any]) -> Object:
    actions_detail = data.get("actions_detail", {})
    actions = {
        name: deserialize_object_action(name, detail) for name, detail in actions_detail.items()
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
        width=int(data.get("width", 1)),
        height=int(data.get("height", 1)),
        hidden=bool(data.get("hidden", False)),
        private_data=data.get("private_data", ""),
    )


def deserialize_decoration(data: dict[str, Any]) -> Decoration:
    kind = str(data.get("kind", DECORATION_KIND_SPRITE)).strip().lower()
    if kind == DECORATION_KIND_BACKGROUND:
        return Decoration(
            id=data["id"],
            kind=kind,
            image=data.get("image", ""),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            z_index=int(data.get("z_index", -1000)),
            repeat=str(data.get("repeat", "repeat")),
        )
    return Decoration(
        id=data["id"],
        kind=kind,
        image=data.get("image", ""),
        x=int(data.get("x", 0)),
        y=int(data.get("y", 0)),
        width=int(data.get("width", 0)),
        height=int(data.get("height", 0)),
        z_index=int(data.get("z_index", 0)),
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
    for decor_data in data.get("decorations", []):
        area.decorations.append(deserialize_decoration(decor_data))
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
        "private_data": agent.private_data,
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
        private_data=data.get("private_data", ""),
    )


def _prepare_session_for_save(session: object) -> None:
    from campaign_rpg_engine.session import Session

    if not isinstance(session, Session):
        raise TypeError(f"Expected Session, got {type(session)!r}")
    for area in session.areas.values():
        for agent in area.agents:
            agent.memory.ensure_ready_for_turn()


def build_save_snapshot(session: object) -> dict[str, Any]:
    """Build a JSON-friendly full session save document."""
    from campaign_rpg_engine.session import Session

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
        "coordinate_mode": session.coordinate_mode,
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
        "extensions": dict(session.extensions),
    }


def load_session_from_snapshot(data: dict[str, Any]):
    """Reconstruct a ``Session`` from a save document."""
    from campaign_rpg_engine.session import Session

    version = data.get("snapshot_version")
    if version not in SUPPORTED_SNAPSHOT_VERSIONS:
        raise ValueError(
            f"Unsupported snapshot_version {version!r} "
            f"(supported: {sorted(SUPPORTED_SNAPSHOT_VERSIONS)})"
        )

    validate_snapshot_modules(data)
    validate_snapshot_handlers(data)

    profile_id = data.get("profile_id")
    if not profile_id:
        raise ValueError("Missing profile_id in session snapshot")
    profile = load_profile(profile_id)

    areas_data = data.get("areas")
    if not areas_data:
        raise ValueError("Session snapshot has no areas")

    areas = {
        area_id: deserialize_area(area_id, area_data) for area_id, area_data in areas_data.items()
    }

    agent_area: dict[str, str] = dict(data.get("agent_area", {}))
    for agent_data in data.get("agents", []):
        agent = deserialize_agent(agent_data)
        area_id = agent_data.get("area_id") or agent_area.get(agent.id)
        if not area_id or area_id not in areas:
            raise ValueError(f"Agent {agent.id!r} references unknown area {area_id!r}")
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
    from campaign_rpg_engine.coordinate_mode import normalize_coordinate_mode

    session.coordinate_mode = normalize_coordinate_mode(data.get("coordinate_mode"))
    session.lorebook_char_budget = int(
        data.get("lorebook_char_budget", session.lorebook_char_budget)
    )
    from campaign_rpg_engine.lorebook.scan_config import LorebookScanConfig

    session.lorebook_scan_config = LorebookScanConfig.from_dict(data.get("lorebook_scan_config"))

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

    extensions = data.get("extensions")
    if isinstance(extensions, dict):
        session.extensions = dict(extensions)

    return session
