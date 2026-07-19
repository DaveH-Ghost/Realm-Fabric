"""Entity templates — portable object/agent blueprints without placement or ids (1.2.1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.edit.world_edit_api import (
    WorldMutationResult,
    create_agent_in_area,
    create_object_in_area,
)
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.memory_modules.registry import (
    create_module_from_state,
    export_module_state,
    is_module_loaded,
    unknown_memory_module_message,
)
from campaign_rpg_engine.object import Object
from campaign_rpg_engine.object_action import ObjectAction
from campaign_rpg_engine.session_persistence import deserialize_object_action
from campaign_rpg_engine.snapshot import serialize_object_action

if TYPE_CHECKING:
    from campaign_rpg_engine.session import Session

TEMPLATE_VERSION = 1


def export_object_template(obj: Object) -> dict[str, Any]:
    """Export a portable object template (no id or position)."""
    return {
        "template_version": TEMPLATE_VERSION,
        "kind": "object",
        "name": obj.name,
        "description": obj.description,
        "passive_description": obj.passive_description,
        "appearance": obj.appearance,
        "width": obj.width,
        "height": obj.height,
        "blocks_movement": obj.blocks_movement,
        "movement_exceptions": list(obj.movement_exceptions),
        "hidden": obj.hidden,
        "private_data": obj.private_data,
        "actions_detail": {
            name: serialize_object_action(action) for name, action in sorted(obj.actions.items())
        },
    }


def export_agent_template(agent: Agent, *, include_memory: bool = False) -> dict[str, Any]:
    """Export a portable agent template (no id or position)."""
    data: dict[str, Any] = {
        "template_version": TEMPLATE_VERSION,
        "kind": "agent",
        "name": agent.name,
        "personality": agent.personality,
        "passive_description": agent.passive_description,
        "description": agent.description,
        "appearance": agent.appearance,
        "move_speed": agent.move_speed,
        "blocks_movement": agent.blocks_movement,
        "movement_exceptions": list(agent.movement_exceptions),
        "is_player": agent.is_player,
        "memory_module": agent.memory.module_id,
        "private_data": agent.private_data,
        "include_memory": include_memory,
    }
    if include_memory:
        data["memory"] = {
            "looked_at": sorted(agent.memory.looked_at),
            "ever_looked": sorted(agent.memory.ever_looked),
            "module_id": agent.memory.module_id,
            "module_state": export_module_state(agent.memory.module),
        }
    return data


def validate_template(data: dict[str, Any]) -> str | None:
    """Return an error message if *data* is not a valid template document."""
    if not isinstance(data, dict):
        return "Template must be a JSON object."
    version = data.get("template_version")
    if version != TEMPLATE_VERSION:
        return f"Unsupported template_version {version!r} (expected {TEMPLATE_VERSION})."
    kind = data.get("kind")
    if kind not in ("object", "agent"):
        return "Template kind must be 'object' or 'agent'."
    if not str(data.get("name", "")).strip():
        return "Template name is required."
    if kind == "agent":
        module_id = data.get("memory_module") or ((data.get("memory") or {}).get("module_id"))
        if not module_id:
            return "Agent template requires memory_module."
        if data.get("memory"):
            memory = data["memory"]
            mid = memory.get("module_id")
            if mid and not is_module_loaded(mid):
                return unknown_memory_module_message(mid)
    try:
        validate_template_handlers(data)
    except ValueError as exc:
        return str(exc)
    return None


def validate_template_handlers(data: dict[str, Any]) -> None:
    """Ensure handlers referenced by an object template are registered."""
    from campaign_rpg_engine.interaction_handlers.registry import is_handler_registered

    if data.get("kind") != "object":
        return
    missing: list[str] = []
    for detail in (data.get("actions_detail") or {}).values():
        if not isinstance(detail, dict):
            continue
        handler_id = detail.get("handler_id")
        if not handler_id or is_handler_registered(handler_id):
            continue
        missing.append(str(handler_id))
    if missing:
        raise ValueError(
            f"Interaction handler(s) not registered: {', '.join(sorted(set(missing)))}."
        )


def _deserialize_actions(actions_detail: Any) -> dict[str, ObjectAction]:
    if not isinstance(actions_detail, dict):
        return {}
    actions: dict[str, ObjectAction] = {}
    for name, detail in actions_detail.items():
        if isinstance(detail, dict):
            actions[str(name)] = deserialize_object_action(str(name), detail)
    return actions


def _memory_from_template_block(memory_data: dict[str, Any]) -> Memory:
    module_id = str(memory_data.get("module_id", ""))
    module_state = dict(memory_data.get("module_state", {}))
    if not is_module_loaded(module_id):
        raise ValueError(unknown_memory_module_message(module_id))
    module = create_module_from_state(module_id, module_state)
    memory = Memory(module=module)
    memory.restore_look_state(
        list(memory_data.get("looked_at", [])),
        list(memory_data.get("ever_looked", [])),
    )
    return memory


def spawn_object_from_template(
    session: Session,
    template: dict[str, Any],
    position: tuple[int, int],
    *,
    area_id: str | None = None,
) -> WorldMutationResult:
    """Place a new object from a template (always generates a fresh object id)."""
    err = validate_template(template)
    if err:
        return WorldMutationResult(ok=False, message=err)
    if template.get("kind") != "object":
        return WorldMutationResult(ok=False, message="Template kind must be 'object'.")

    area, area_err = session._resolve_edit_area(area_id)
    if area is None:
        return WorldMutationResult(ok=False, message=area_err or "Unknown area.")

    actions = _deserialize_actions(template.get("actions_detail"))
    obj, message = create_object_in_area(
        area,
        name=str(template["name"]),
        position=position,
        description=str(template.get("description", "")),
        passive_description=str(template.get("passive_description", "")),
        appearance=str(template.get("appearance", "")),
        width=int(template.get("width", 1)),
        height=int(template.get("height", 1)),
        blocks_movement=bool(template.get("blocks_movement", True)),
        movement_exceptions=[str(x) for x in list(template.get("movement_exceptions", []))],
        hidden=bool(template.get("hidden", False)),
        actions=actions or None,
        session=session,
    )
    resolved_area = area_id or session.active_area_id
    if obj is None:
        return WorldMutationResult(ok=False, message=message, area_id=resolved_area)
    if template.get("private_data"):
        obj.private_data = str(template["private_data"])
    session._emit_event("object_created", object=obj, area_id=resolved_area)
    return WorldMutationResult(
        ok=True,
        message=message,
        object=obj,
        area_id=resolved_area,
    )


def spawn_agent_from_template(
    session: Session,
    template: dict[str, Any],
    position: tuple[int, int],
    *,
    area_id: str | None = None,
) -> WorldMutationResult:
    """Place a new agent from a template (always generates a fresh agent id)."""
    err = validate_template(template)
    if err:
        return WorldMutationResult(ok=False, message=err)
    if template.get("kind") != "agent":
        return WorldMutationResult(ok=False, message="Template kind must be 'agent'.")

    area, area_err = session._resolve_edit_area(area_id)
    if area is None:
        return WorldMutationResult(ok=False, message=area_err or "Unknown area.")

    memory_block = template.get("memory")
    memory: Memory | None = None
    memory_module: str | None = None
    if isinstance(memory_block, dict) and memory_block:
        try:
            memory = _memory_from_template_block(memory_block)
        except ValueError as exc:
            return WorldMutationResult(ok=False, message=str(exc))
    else:
        memory_module = str(template.get("memory_module", "")).strip() or None

    move_speed = template.get("move_speed")
    if move_speed is not None:
        move_speed = int(move_speed)

    is_player = template.get("is_player")
    if is_player is not None:
        is_player = bool(is_player)

    agent, message = create_agent_in_area(
        area,
        name=str(template["name"]),
        position=position,
        personality=str(template.get("personality", "")),
        passive_description=str(template.get("passive_description", "")),
        description=str(template.get("description", "")),
        appearance=str(template.get("appearance", "")),
        move_speed=move_speed,
        memory_module=memory_module,
        blocks_movement=bool(template.get("blocks_movement", False)),
        movement_exceptions=[str(x) for x in list(template.get("movement_exceptions", []))],
        is_player=is_player,
        memory=memory,
        allow_duplicate_name=True,
    )
    resolved_area = area_id or session.active_area_id
    if agent is None:
        return WorldMutationResult(ok=False, message=message, area_id=resolved_area)
    if template.get("private_data"):
        agent.private_data = str(template["private_data"])
    session._register_agent(agent, area_id=area_id)
    session._emit_event("agent_created", agent=agent, area_id=resolved_area)
    return WorldMutationResult(
        ok=True,
        message=message,
        agent=agent,
        area_id=resolved_area,
    )
