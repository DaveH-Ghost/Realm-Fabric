"""
world_edit_api.py

Typed programmatic world editing (V0.7.0) — same validation as CLI, structured arguments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.area_edit import (
    _apply_footprint_dim_fields,
    _apply_hidden_fields,
    _apply_movement_fields,
    _apply_object_content_fields,
    _apply_object_location_fields,
    _build_agent_memory,
    _parse_footprint_dims,
    _validate_object_footprint_in_area,
    agent_name_conflicts_with_commands,
    agent_name_taken,
    format_memory_module_label,
    generate_agent_id,
    generate_object_id,
    parse_bool_field,
    parse_move_speed,
    reserved_agent_name_message,
)
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.object import Object
from campaign_rpg_engine.object_action import ObjectAction

if TYPE_CHECKING:
    from campaign_rpg_engine.session import Session


@dataclass(frozen=True)
class WorldMutationResult:
    """Outcome of typed world-editing methods on ``Session``."""

    ok: bool
    message: str
    object: Object | None = None
    agent: Agent | None = None
    area_id: str | None = None


def _format_position(position: tuple[int, int]) -> str:
    x, y = position
    return f"{x},{y}"


def create_object_in_area(
    area: Area,
    *,
    name: str,
    position: tuple[int, int],
    description: str = "",
    passive_description: str = "",
    appearance: str = "",
    width: int = 1,
    height: int = 1,
    blocks_movement: bool | None = None,
    movement_exceptions: list[str] | None = None,
    hidden: bool | None = None,
    actions: dict[str, ObjectAction] | None = None,
) -> tuple[Object | None, str]:
    """Create an object with the same rules as ``create-object`` CLI."""
    if not name.strip():
        return None, "Missing required field: name"
    if not area.is_valid_position(position):
        return None, f"Invalid position {position}. {area.format_grid_bounds_message()}"

    fields: dict[str, str] = {
        "name": name,
        "at": _format_position(position),
        "width": str(width),
        "height": str(height),
    }
    if description:
        fields["desc"] = description
    if passive_description:
        fields["pdesc"] = passive_description
    if appearance:
        fields["appearance"] = appearance
    if blocks_movement is not None:
        fields["blocks-movement"] = "true" if blocks_movement else "false"
    if movement_exceptions:
        fields["movement-exception"] = ",".join(movement_exceptions)
    if hidden is not None:
        fields["hidden"] = "true" if hidden else "false"

    w, h, dim_err = _parse_footprint_dims(fields)
    if dim_err:
        return None, dim_err

    obj_id = generate_object_id(area, name)
    obj = Object(
        id=obj_id,
        name=name,
        description=description,
        position=position,
        passive_description=passive_description,
        actions=dict(actions or {}),
        appearance=appearance,
        width=w,
        height=h,
    )
    movement_err = _apply_movement_fields(obj, fields, [])
    if movement_err:
        return None, movement_err
    hidden_err = _apply_hidden_fields(obj, fields, [])
    if hidden_err:
        return None, hidden_err
    footprint_err = _validate_object_footprint_in_area(area, obj)
    if footprint_err:
        return None, footprint_err
    area.add_object(obj)
    action_note = ""
    if obj.actions:
        action_note = f" Action(s): {', '.join(sorted(obj.actions))}."
    size_note = ""
    if w != 1 or h != 1:
        size_note = f" footprint {w}x{h}."
    return obj, (
        f'Created object {obj_id} "{name}" at {position}.{size_note}{action_note} '
        f"Use 'objects' or 'list' to see all object ids."
    )


def create_agent_in_area(
    area: Area,
    *,
    name: str,
    position: tuple[int, int],
    personality: str = "",
    passive_description: str = "",
    description: str = "",
    appearance: str = "",
    move_speed: int | None = None,
    memory_module: str | None = None,
    memory_window: int | None = None,
    memory_budget: int | None = None,
    memory_summary_interval: int | None = None,
    memory_summary_max: int | None = None,
    memory_summary_tail: int | None = None,
    blocks_movement: bool | None = None,
    movement_exceptions: list[str] | None = None,
    is_player: bool | None = None,
    memory: Memory | None = None,
) -> tuple[Agent | None, str]:
    """Create an agent with the same rules as ``create-agent`` CLI."""
    if not name.strip():
        return None, "Missing required field: name"
    if agent_name_conflicts_with_commands(name):
        return None, reserved_agent_name_message(name)
    if agent_name_taken(area, name):
        return None, f"Agent name '{name}' is already in use."
    if not area.is_valid_position(position):
        return None, f"Invalid position {position}. {area.format_grid_bounds_message()}"

    fields: dict[str, str] = {"name": name, "at": _format_position(position)}
    if personality:
        fields["personality"] = personality
    if passive_description:
        fields["pdesc"] = passive_description
    if description:
        fields["desc"] = description
    if appearance:
        fields["appearance"] = appearance
    if move_speed is not None:
        fields["move-speed"] = str(move_speed)
    if memory_module is not None:
        fields["memory"] = memory_module
    if memory_window is not None:
        fields["memory-window"] = str(memory_window)
    if memory_budget is not None:
        fields["memory-budget"] = str(memory_budget)
    if memory_summary_interval is not None:
        fields["memory-summary-interval"] = str(memory_summary_interval)
    if memory_summary_max is not None:
        fields["memory-summary-max"] = str(memory_summary_max)
    if memory_summary_tail is not None:
        fields["memory-summary-tail"] = str(memory_summary_tail)
    if blocks_movement is not None:
        fields["blocks-movement"] = "true" if blocks_movement else "false"
    if movement_exceptions:
        fields["movement-exception"] = ",".join(movement_exceptions)
    if is_player is not None:
        fields["player"] = "true" if is_player else "false"

    if memory is None:
        built_memory, mem_err = _build_agent_memory(fields)
        if mem_err:
            return None, mem_err
        memory = built_memory
    assert memory is not None

    if move_speed is None and "move-speed" in fields:
        move_speed, speed_err = parse_move_speed(fields["move-speed"])
        if speed_err:
            return None, speed_err

    agent_id = generate_agent_id(area, name)
    agent = Agent(
        id=agent_id,
        name=name,
        personality=personality,
        position=position,
        passive_description=passive_description,
        description=description,
        appearance=appearance,
        move_speed=move_speed,
        memory=memory,
        last_action=None,
    )
    movement_err = _apply_movement_fields(agent, fields, [])
    if movement_err:
        return None, movement_err
    if is_player is not None:
        agent.is_player = is_player
    area.add_agent(agent)
    module_note = f" {format_memory_module_label(memory.module)}"
    return agent, (
        f'Created agent {agent_id} "{name}" at {position}.{module_note}'
        f" Use 'agents' or 'list' to see all agent ids."
    )


def find_object_in_session(
    session: Session, object_id: str
) -> tuple[str, Area, Object] | None:
    for area_id, area in session.areas.items():
        obj = area.get_object_by_id(object_id)
        if obj is not None:
            return area_id, area, obj
    return None


def add_object_action_to_object(obj: Object, action: ObjectAction) -> str | None:
    """Add or replace a named action on an object. Returns error message or None."""
    if not action.name.strip():
        return "Action name must not be empty."
    from campaign_rpg_engine.interaction_handlers.registry import validate_handler_params

    if action.handler_id:
        err = validate_handler_params(action.handler_id, action.handler_params)
        if err:
            return err
    obj.actions[action.name] = action
    return None


def create_object_from_fields(
    area: Area, fields: dict[str, str]
) -> tuple[Object | None, str]:
    """Bridge from CLI field dict to typed create (used by ``create_object_from_args``)."""
    from campaign_rpg_engine.area_edit import parse_object_action_fields, parse_position

    if "name" not in fields:
        return None, "Missing required field: name"
    if "at" not in fields:
        return None, "Missing required field: at"
    position, err = parse_position(fields["at"])
    if err:
        return None, err
    assert position is not None

    actions, err = parse_object_action_fields(fields)
    if err:
        return None, err
    assert actions is not None

    width, height, dim_err = _parse_footprint_dims(fields)
    if dim_err:
        return None, dim_err

    blocks_movement: bool | None = None
    if "blocks-movement" in fields:
        blocks_movement, berr = parse_bool_field(
            fields["blocks-movement"], field_name="blocks-movement"
        )
        if berr:
            return None, berr
    hidden: bool | None = None
    if "hidden" in fields:
        hidden, herr = parse_bool_field(fields["hidden"], field_name="hidden")
        if herr:
            return None, herr
    movement_exceptions = None
    if "movement-exception" in fields:
        movement_exceptions = [
            p.strip() for p in fields["movement-exception"].split(",") if p.strip()
        ]

    return create_object_in_area(
        area,
        name=fields["name"],
        position=position,
        description=fields.get("desc", ""),
        passive_description=fields.get("pdesc", ""),
        appearance=fields.get("appearance", ""),
        width=width,
        height=height,
        blocks_movement=blocks_movement,
        movement_exceptions=movement_exceptions,
        hidden=hidden,
        actions=actions,
    )


def create_agent_from_fields(
    area: Area, fields: dict[str, str]
) -> tuple[Agent | None, str]:
    """Bridge from CLI field dict to typed create (used by ``create_agent_from_args``)."""
    from campaign_rpg_engine.area_edit import parse_position

    if "name" not in fields:
        return None, "Missing required field: name"
    if "at" not in fields:
        return None, "Missing required field: at"
    position, err = parse_position(fields["at"])
    if err:
        return None, err
    assert position is not None

    move_speed: int | None = None
    if "move-speed" in fields:
        move_speed, speed_err = parse_move_speed(fields["move-speed"])
        if speed_err:
            return None, speed_err
    is_player: bool | None = None
    if "player" in fields:
        is_player, player_err = parse_bool_field(fields["player"], field_name="player")
        if player_err:
            return None, player_err
    movement_exceptions = None
    if "movement-exception" in fields:
        movement_exceptions = [
            p.strip() for p in fields["movement-exception"].split(",") if p.strip()
        ]
    blocks_movement: bool | None = None
    if "blocks-movement" in fields:
        blocks_movement, berr = parse_bool_field(
            fields["blocks-movement"], field_name="blocks-movement"
        )
        if berr:
            return None, berr

    memory, mem_err = _build_agent_memory(fields)
    if mem_err:
        return None, mem_err
    assert memory is not None

    return create_agent_in_area(
        area,
        name=fields["name"],
        position=position,
        personality=fields.get("personality", ""),
        passive_description=fields.get("pdesc", ""),
        description=fields.get("desc", ""),
        appearance=fields.get("appearance", ""),
        move_speed=move_speed,
        blocks_movement=blocks_movement,
        movement_exceptions=movement_exceptions,
        is_player=is_player,
        memory=memory,
    )


def delete_object_in_session(session: Session, object_id: str) -> tuple[bool, str]:
    """Delete an object anywhere in the session."""
    object_id = object_id.strip()
    if not object_id:
        return False, "Usage: delete-object <id>"
    if not object_id.startswith("obj_"):
        return (
            False,
            f"Commands require object id (e.g. obj_ball_01), not display name. "
            f"Use 'objects' or 'list' to look up ids.",
        )
    located = find_object_in_session(session, object_id)
    if located is None:
        return (
            False,
            f"Object '{object_id}' not found. Use 'objects' or 'list' to look up ids.",
        )
    _area_id, area, _obj = located
    if not area.remove_object(object_id):
        return (
            False,
            f"Object '{object_id}' not found. Use 'objects' or 'list' to look up ids.",
        )
    return True, f"Deleted object {object_id}."


def edit_object_with_fields(
    session: Session, object_id: str, fields: dict[str, str]
) -> WorldMutationResult:
    """Apply field updates to an object (same rules as ``edit-object`` CLI)."""
    object_id = object_id.strip()
    if not object_id.startswith("obj_"):
        return WorldMutationResult(
            ok=False,
            message=(
                f"Commands require object id (e.g. obj_ball_01), not display name. "
                f"Use 'objects' or 'list' to look up ids."
            ),
        )
    located = find_object_in_session(session, object_id)
    if located is None:
        return WorldMutationResult(
            ok=False,
            message=f"Object '{object_id}' not found. Use 'objects' or 'list' to look up ids.",
        )
    located_area_id, area, obj = located
    if not fields:
        return WorldMutationResult(
            ok=False,
            message=(
                "At least one field to change is required "
                "(name, pdesc, desc, appearance, area, pos, width, height, "
                "blocks-movement, movement-exception, or hidden)."
            ),
        )

    changes: list[str] = []
    location_err = _apply_object_location_fields(
        session, area, obj, object_id, located_area_id, fields, changes
    )
    if location_err:
        return WorldMutationResult(ok=False, message=location_err)

    current_area_id = located_area_id
    if "area" in fields and fields["area"].strip() != located_area_id:
        current_area_id = fields["area"].strip()
    current_area = session.areas[current_area_id]

    content_err = _apply_object_content_fields(current_area, obj, object_id, fields, changes)
    if content_err:
        return WorldMutationResult(ok=False, message=content_err)

    footprint_err = _apply_footprint_dim_fields(current_area, obj, fields, changes)
    if footprint_err:
        return WorldMutationResult(ok=False, message=footprint_err)

    if not changes:
        return WorldMutationResult(
            ok=False,
            message=f"No changes applied to {object_id}.",
        )
    return WorldMutationResult(
        ok=True,
        message=f"Updated object {object_id} ({', '.join(changes)}).",
        object=obj,
        area_id=current_area_id,
    )
