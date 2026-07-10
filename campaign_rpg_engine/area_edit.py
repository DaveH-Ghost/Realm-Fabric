"""
area_edit.py

Validation and mutation helpers for world editing.

Typed apps should use ``Session.create_*`` / ``Session.edit_*`` and
``world_edit_api``. String parsers in ``area_edit_parse`` support tests and
app-owned command dispatch (CampAIgn-RPG-Studio).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from campaign_rpg_engine.session import Session

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area_edit_parse import parse_field_tokens, tokenize_args
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.memory_modules.registry import (
    format_memory_module_label,
    is_builtin_module_id,
    is_module_loaded,
)
from campaign_rpg_engine.object import Object, object_footprint_fits_bounds
from campaign_rpg_engine.object_action import ObjectAction
from campaign_rpg_engine.interaction_handlers.registry import validate_handler_params
from campaign_rpg_engine.reserved_names import (
    agent_name_conflicts_with_commands,
    reserved_agent_name_message,
)
from campaign_rpg_engine.area import Area


@dataclass
class DeleteAgentResult:
    ok: bool
    message: str
    deleted_agent: Optional[Agent] = None


@dataclass
class EditAgentResult:
    ok: bool
    message: str
    agent: Optional[Agent] = None
    old_name_lower: Optional[str] = None


def slugify_display_name(name: str) -> str:
    """Lowercase, spaces to underscores, strip non-alphanumeric."""
    slug = name.lower().replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "new"


def generate_object_id(area: Area, display_name: str) -> str:
    """Auto-generate a unique object id from a display name."""
    slug = slugify_display_name(display_name)
    existing = {obj.id for obj in area.objects}
    counter = 1
    while True:
        candidate = f"obj_{slug}_{counter:02d}"
        if candidate not in existing:
            return candidate
        counter += 1


def generate_agent_id(area: Area, display_name: str) -> str:
    """Auto-generate a unique agent id from a display name."""
    slug = slugify_display_name(display_name)
    existing = {agent.id for agent in area.agents}
    counter = 1
    while True:
        candidate = f"agent_{slug}_{counter:02d}"
        if candidate not in existing:
            return candidate
        counter += 1


def agent_name_taken(
    area: Area, name: str, exclude_agent_id: Optional[str] = None
) -> bool:
    """Return True if another agent already has this name (case-insensitive)."""
    name_lower = name.lower()
    for agent in area.agents:
        if exclude_agent_id and agent.id == exclude_agent_id:
            continue
        if agent.name.lower() == name_lower:
            return True
    return False


def parse_position(value: str) -> tuple[Optional[tuple[int, int]], Optional[str]]:
    """Parse x,y position. Returns (position, error_message)."""
    value = value.strip()
    if " " in value:
        return None, "Position must be x,y with no spaces (e.g. 2,2)."
    parts = value.split(",")
    if len(parts) != 2:
        return None, "Position must be x,y (e.g. 2,2)."
    try:
        x, y = int(parts[0]), int(parts[1])
    except ValueError:
        return None, "Position coordinates must be integers."
    return (x, y), None


def parse_move_speed(value: str) -> tuple[Optional[int], Optional[str]]:
    """Parse move-speed field. Empty string clears to unlimited (None)."""
    text = value.strip()
    if not text:
        return None, None
    try:
        speed = int(text)
    except ValueError:
        return None, f"move-speed must be an integer (got {value!r})."
    if speed < 1:
        return None, "move-speed must be at least 1 (omit or clear for unlimited)."
    return speed, None


def parse_bool_field(value: str, *, field_name: str) -> tuple[Optional[bool], Optional[str]]:
    """Parse true/false CLI flag values."""
    text = value.strip().lower()
    if text in ("true", "yes", "1", "on"):
        return True, None
    if text in ("false", "no", "0", "off"):
        return False, None
    return None, f"{field_name} must be true or false (got {value!r})."


def parse_movement_exceptions(value: str) -> list[str]:
    """Parse comma-separated entity ids for movement_exceptions."""
    return [part.strip() for part in value.split(",") if part.strip()]


def _apply_movement_fields(
    entity: Agent | Object,
    fields: dict[str, str],
    changes: list[str],
) -> Optional[str]:
    if "blocks-movement" in fields:
        blocks, err = parse_bool_field(
            fields["blocks-movement"], field_name="blocks-movement"
        )
        if err:
            return err
        assert blocks is not None
        if blocks != entity.blocks_movement:
            entity.blocks_movement = blocks
            changes.append("blocks-movement")

    if "movement-exception" in fields:
        exceptions = parse_movement_exceptions(fields["movement-exception"])
        if exceptions != entity.movement_exceptions:
            entity.movement_exceptions = exceptions
            changes.append("movement-exception")
    return None


def _apply_hidden_fields(
    obj: Object,
    fields: dict[str, str],
    changes: list[str],
) -> Optional[str]:
    if "hidden" not in fields:
        return None
    hidden, err = parse_bool_field(fields["hidden"], field_name="hidden")
    if err:
        return err
    assert hidden is not None
    if hidden != obj.hidden:
        obj.hidden = hidden
        changes.append("hidden")
    return None


def format_objects_list(area: Area) -> str:
    """Format the objects listing block."""
    lines = ["Objects in area:"]
    objects = area.get_objects()
    if not objects:
        lines.append("  No objects in area.")
    else:
        for obj in objects:
            action_suffix = ""
            if obj.actions:
                names = ", ".join(sorted(obj.actions))
                action_suffix = f" actions: {names}"
            size_suffix = ""
            if obj.width != 1 or obj.height != 1:
                size_suffix = f" {obj.width}×{obj.height}"
            hidden_suffix = " (hidden)" if obj.hidden else ""
            lines.append(
                f"  - {obj.name} ({obj.id}) at {obj.position}{size_suffix}{hidden_suffix}{action_suffix}"
            )
    return "\n".join(lines)


def format_agents_list(area: Area, active_agent: Optional[Agent]) -> str:
    """Format the agents listing block."""
    lines = ["Agents in area:"]
    if not area.agents:
        lines.append("  No agents in area.")
    else:
        for agent in area.agents:
            marker = " (active)" if agent is active_agent else ""
            player_marker = " (player)" if agent.is_player else ""
            lines.append(
                f"  - {agent.name} ({agent.id}) at {agent.position}"
                f" {format_memory_module_label(agent.memory.module)}"
                f"{player_marker}{marker}"
            )
    return "\n".join(lines)


def format_full_list(area: Area, active_agent: Optional[Agent]) -> str:
    """Format agents then objects (same as running agents + objects)."""
    return f"{format_agents_list(area, active_agent)}\n\n{format_objects_list(area)}"


def parse_handler_from_fields(
    fields: dict[str, str],
) -> tuple[str | None, dict[str, str], Optional[str]]:
    """Build handler id + params from optional handler / dest-area / dest-at fields."""
    handler_id = fields.get("handler") or fields.get("effect")
    if not handler_id:
        if "dest-area" in fields or "dest-at" in fields:
            return None, {}, "dest-area and dest-at require handler move_area."
        return None, {}, None

    params: dict[str, str] = {}
    if handler_id == "move_area":
        if "dest-area" not in fields:
            return None, {}, "move_area handler requires dest-area <area_id>."
        if "dest-at" not in fields:
            return None, {}, "move_area handler requires dest-at x,y."
        params["dest-area"] = fields["dest-area"]
        params["dest-at"] = fields["dest-at"]
    elif "dest-area" in fields or "dest-at" in fields:
        return None, {}, "dest-area and dest-at are only valid with handler move_area."

    err = validate_handler_params(handler_id, params)
    if err:
        return None, {}, err
    return handler_id, params, None


def parse_object_action_fields(
    fields: dict[str, str],
) -> tuple[dict[str, ObjectAction] | None, Optional[str]]:
    """
    Build actions dict from optional action/range/handler/result/passive fields.

    When ``action`` is absent, returns an empty dict. When present, requires
    result and passive; range defaults to 0; handler is optional.
    """
    if "action" not in fields:
        return {}, None

    name = fields["action"]
    if not name.strip():
        return None, "Action name must not be empty."

    range_raw = fields.get("range", "0")
    try:
        action_range = int(range_raw)
    except ValueError:
        return None, f"Range must be an integer (got {range_raw!r})."
    if action_range < 0:
        return None, "Range must be non-negative."

    result = fields.get("result")
    passive = fields.get("passive")
    if not result:
        return None, "Missing required field: result (when action is set)"
    if not passive:
        return None, "Missing required field: passive (when action is set)"

    kind = fields.get("kind", "interact").strip().lower()
    if kind not in ("interact", "trigger"):
        return None, "kind must be interact or trigger."

    halt_movement = False
    delete_after_trigger = True
    trigger_exceptions: list[str] = []

    if kind == "trigger":
        if "halt-movement" in fields:
            halt_movement, err = parse_bool_field(
                fields["halt-movement"], field_name="halt-movement"
            )
            if err:
                return None, err
            assert halt_movement is not None
        if "delete-after-trigger" in fields:
            delete_after_trigger, err = parse_bool_field(
                fields["delete-after-trigger"], field_name="delete-after-trigger"
            )
            if err:
                return None, err
            assert delete_after_trigger is not None
        if "trigger-exception" in fields:
            trigger_exceptions = parse_movement_exceptions(fields["trigger-exception"])

    handler_id, handler_params, err = parse_handler_from_fields(fields)
    if err:
        return None, err

    action = ObjectAction(
        name=name,
        range=action_range,
        result=result,
        passive_result=passive,
        handler_id=handler_id,
        handler_params=handler_params,
        kind=kind,  # type: ignore[arg-type]
        halt_movement=halt_movement,
        delete_after_trigger=delete_after_trigger,
        trigger_exceptions=trigger_exceptions,
    )
    return {name: action}, None



def _parse_footprint_dims(
    fields: dict[str, str],
    *,
    default_width: int = 1,
    default_height: int = 1,
) -> tuple[int, int, str | None]:
    try:
        width = int(fields.get("width", str(default_width)))
        height = int(fields.get("height", str(default_height)))
    except ValueError:
        return 0, 0, "width and height must be integers."
    if width < 1 or height < 1:
        return 0, 0, "width and height must be at least 1."
    return width, height, None


def _validate_object_footprint_in_area(area: Area, obj: Object) -> str | None:
    if object_footprint_fits_bounds(obj, area):
        return None
    return (
        f"Footprint ({obj.width}x{obj.height}) at {obj.position} extends outside the room. "
        f"{area.format_grid_bounds_message()}"
    )


def _apply_footprint_dim_fields(
    area: Area,
    obj: Object,
    fields: dict[str, str],
    changes: list[str],
) -> str | None:
    if "width" in fields:
        try:
            width = int(fields["width"])
        except ValueError:
            return "width must be an integer."
        if width < 1:
            return "width must be at least 1."
        if width != obj.width:
            obj.width = width
            changes.append("width")
    if "height" in fields:
        try:
            height = int(fields["height"])
        except ValueError:
            return "height must be an integer."
        if height < 1:
            return "height must be at least 1."
        if height != obj.height:
            obj.height = height
            changes.append("height")
    if "width" in fields or "height" in fields:
        return _validate_object_footprint_in_area(area, obj)
    return None


def create_object_from_args(area: Area, arg: str) -> tuple[Optional[Object], str]:
    """
    Parse and create an object from command arguments.

    Usage: name "..." [pdesc "..."] [desc "..."] [appearance "..."] at x,y
           [width N] [height N]
           [action NAME range N [handler HANDLER] result "..." passive "..."]
    """
    tokens, err = tokenize_args(arg)
    if err:
        return None, err
    if not tokens:
        return None, (
            'Usage: create-object name "..." [pdesc "..."] [desc "..."] [appearance "..."] at x,y '
            '[width N] [height N] '
            '[action NAME range N [effect EFFECT] result "..." passive "..."]'
        )

    fields, err = parse_field_tokens(
        tokens,
        {
            "name",
            "desc",
            "pdesc",
            "appearance",
            "at",
            "action",
            "range",
            "handler",
            "effect",
            "dest-area",
            "dest-at",
            "result",
            "passive",
            "blocks-movement",
            "movement-exception",
            "width",
            "height",
            "hidden",
            "kind",
            "halt-movement",
            "delete-after-trigger",
            "trigger-exception",
        },
    )
    if err:
        return None, err

    from campaign_rpg_engine.world_edit_api import create_object_from_fields

    return create_object_from_fields(area, fields)


def _edit_object_add_action(obj: Object, tokens: list[str]) -> str:
    """Parse add-action subcommand on edit-object."""
    if len(tokens) < 3:
        return (
            'Usage: edit-object <id> add-action <name> range N '
            '[effect E] result "..." passive "..."'
        )

    action_name = tokens[2]
    fields, err = parse_field_tokens(
        tokens[3:],
        {
            "range",
            "handler",
            "effect",
            "dest-area",
            "dest-at",
            "result",
            "passive",
            "kind",
            "halt-movement",
            "delete-after-trigger",
            "trigger-exception",
        },
    )
    if err:
        return err
    fields["action"] = action_name
    actions, err = parse_object_action_fields(fields)
    if err:
        return err
    assert actions is not None
    if action_name in obj.actions:
        return f"Object {obj.id} already has action '{action_name}'."
    obj.actions[action_name] = actions[action_name]
    return f"Added action '{action_name}' to {obj.id}."


def _edit_object_remove_action(obj: Object, tokens: list[str]) -> str:
    """Parse remove-action subcommand on edit-object."""
    if len(tokens) < 3:
        return "Usage: edit-object <id> remove-action <name>"
    action_name = tokens[2]
    if action_name not in obj.actions:
        return f"Object {obj.id} has no action '{action_name}'."
    del obj.actions[action_name]
    return f"Removed action '{action_name}' from {obj.id}."


def _apply_object_content_fields(
    area: Area,
    obj: Object,
    object_id: str,
    fields: dict[str, str],
    changes: list[str],
) -> Optional[str]:
    if "name" in fields and fields["name"] != obj.name:
        obj.name = fields["name"]
        changes.append("name")

    if "pdesc" in fields and fields["pdesc"] != obj.passive_description:
        obj.passive_description = fields["pdesc"]
        changes.append("pdesc")

    if "appearance" in fields and fields["appearance"] != obj.appearance:
        obj.appearance = fields["appearance"]
        changes.append("appearance")

    if "desc" in fields and fields["desc"] != obj.description:
        obj.description = fields["desc"]
        if fields["desc"]:
            area.invalidate_object_knowledge(object_id)
        else:
            area.clear_object_examination_history(object_id)
        changes.append("desc")

    return _apply_movement_fields(obj, fields, changes) or _apply_hidden_fields(
        obj, fields, changes
    )


def _apply_object_location_fields(
    session: Session,
    area: Area,
    obj: Object,
    object_id: str,
    located_area_id: str,
    fields: dict[str, str],
    changes: list[str],
) -> Optional[str]:
    dest_area_id = (
        fields.get("area", located_area_id).strip()
        if "area" in fields
        else located_area_id
    )
    if "area" in fields and dest_area_id not in session.areas:
        return f"Unknown area {dest_area_id!r}."

    target_pos = obj.position
    if "pos" in fields:
        target_pos, err = parse_position(fields["pos"])
        if err:
            return err
        assert target_pos is not None

    dest_area = session.areas[dest_area_id]
    original_pos = obj.position
    if "pos" in fields:
        obj.position = target_pos
    footprint_err = _validate_object_footprint_in_area(dest_area, obj)
    if footprint_err:
        obj.position = original_pos
        return footprint_err

    if dest_area_id != located_area_id:
        for index, candidate in enumerate(area.objects):
            if candidate.id == object_id:
                area.objects.pop(index)
                break
        dest_area.add_object(obj)
        changes.append("area")
        if "pos" in fields:
            changes.append("pos")
    elif "pos" in fields and target_pos != original_pos:
        changes.append("pos")
    return None


def edit_object_for_session(session: Session, arg: str) -> str:
    """
    Parse and edit an object anywhere in a multi-area session.

    Supports ``area <area_id>`` to move the object between areas (with optional ``pos``).
    """
    tokens, err = tokenize_args(arg)
    if err:
        return err
    if not tokens:
        return (
            'Usage: edit-object <id> [pdesc "..."] [desc "..."] [appearance "..."] '
            '[name "..."] [area <area_id>] [pos x,y] ... '
            '| add-action ... | remove-action <name>'
        )

    object_id = tokens[0]
    if not object_id.startswith("obj_"):
        return (
            f"Commands require object id (e.g. obj_ball_01), not display name. "
            f"Use 'objects' or 'list' to look up ids."
        )

    located: tuple[str, Area, Object] | None = None
    for area_id, area in session.areas.items():
        obj = area.get_object_by_id(object_id)
        if obj is not None:
            located = (area_id, area, obj)
            break
    if located is None:
        return f"Object '{object_id}' not found. Use 'objects' or 'list' to look up ids."

    located_area_id, area, obj = located

    if len(tokens) > 1:
        sub = tokens[1].lower()
        if sub == "add-action":
            return _edit_object_add_action(obj, tokens)
        if sub == "remove-action":
            return _edit_object_remove_action(obj, tokens)

    fields, err = parse_field_tokens(
        tokens[1:],
        {"name", "desc", "pdesc", "appearance", "pos", "area", "blocks-movement", "movement-exception", "width", "height", "hidden"},
    )
    if err:
        return err
    if not fields:
        return (
            "At least one field to change is required "
            "(name, pdesc, desc, appearance, area, pos, width, height, blocks-movement, movement-exception, or hidden)."
        )

    changes: list[str] = []
    location_err = _apply_object_location_fields(
        session, area, obj, object_id, located_area_id, fields, changes
    )
    if location_err:
        return location_err

    current_area_id = located_area_id
    if "area" in fields and fields["area"].strip() != located_area_id:
        current_area_id = fields["area"].strip()
    current_area = session.areas[current_area_id]

    content_err = _apply_object_content_fields(current_area, obj, object_id, fields, changes)
    if content_err:
        return content_err

    footprint_err = _apply_footprint_dim_fields(current_area, obj, fields, changes)
    if footprint_err:
        return footprint_err

    if not changes:
        return f"No changes applied to {object_id}."

    return f"Updated object {object_id} ({', '.join(changes)})."


def edit_object_from_args(area: Area, arg: str) -> str:
    """
    Parse and edit an object.

    Usage: <object_id> [desc "..."] [name "..."] [pos x,y] ...
           <object_id> add-action <name> range N [effect E] result "..." passive "..."
           <object_id> remove-action <name>
    """
    tokens, err = tokenize_args(arg)
    if err:
        return err
    if not tokens:
        return (
            'Usage: edit-object <id> [pdesc "..."] [desc "..."] [appearance "..."] [name "..."] [pos x,y] ... '
            '| add-action ... | remove-action <name>'
        )

    object_id = tokens[0]
    if not object_id.startswith("obj_"):
        return (
            f"Commands require object id (e.g. obj_ball_01), not display name. "
            f"Use 'objects' or 'list' to look up ids."
        )

    obj = area.get_object_by_id(object_id)
    if obj is None:
        return f"Object '{object_id}' not found. Use 'objects' or 'list' to look up ids."

    if len(tokens) > 1:
        sub = tokens[1].lower()
        if sub == "add-action":
            return _edit_object_add_action(obj, tokens)
        if sub == "remove-action":
            return _edit_object_remove_action(obj, tokens)

    fields, err = parse_field_tokens(tokens[1:], {"name", "desc", "pdesc", "appearance", "pos", "blocks-movement", "movement-exception", "width", "height", "hidden"})
    if err:
        return err
    if not fields:
        return "At least one field to change is required (name, pdesc, desc, appearance, pos, width, height, blocks-movement, or movement-exception)."

    changes: list[str] = []
    content_err = _apply_object_content_fields(area, obj, object_id, fields, changes)
    if content_err:
        return content_err

    footprint_err = _apply_footprint_dim_fields(area, obj, fields, changes)
    if footprint_err:
        return footprint_err

    if "pos" in fields:
        position, err = parse_position(fields["pos"])
        if err:
            return err
        assert position is not None
        original_pos = obj.position
        obj.position = position
        bounds_err = _validate_object_footprint_in_area(area, obj)
        if bounds_err:
            obj.position = original_pos
            return bounds_err
        if position != original_pos:
            changes.append("pos")

    if not changes:
        return f"No changes applied to {object_id}."

    return f"Updated object {object_id} ({', '.join(changes)})."


def delete_object_by_id(area: Area, object_id: str) -> str:
    """Delete an object by id."""
    object_id = object_id.strip()
    if not object_id:
        return "Usage: delete-object <id>"
    if not object_id.startswith("obj_"):
        return (
            f"Commands require object id (e.g. obj_ball_01), not display name. "
            f"Use 'objects' or 'list' to look up ids."
        )
    if not area.remove_object(object_id):
        return f"Object '{object_id}' not found. Use 'objects' or 'list' to look up ids."
    return f"Deleted object {object_id}."


def _build_agent_memory(fields: dict[str, str]) -> tuple[Optional[Memory], Optional[str]]:
    """Construct Memory from create-agent fields (memory + optional module config)."""
    memory_module_id = fields.get("memory")
    memory_window_raw = fields.get("memory-window")
    memory_budget_raw = fields.get("memory-budget")
    summary_interval_raw = fields.get("memory-summary-interval")
    summary_max_raw = fields.get("memory-summary-max")
    summary_tail_raw = fields.get("memory-summary-tail")

    if memory_window_raw is not None and memory_module_id not in (None, "recent_turns"):
        if memory_module_id is None or is_builtin_module_id(memory_module_id):
            return None, "memory-window is only valid with memory recent_turns."

    if memory_budget_raw is not None and memory_module_id not in (None, "salient_turns"):
        if memory_module_id is None or is_builtin_module_id(memory_module_id):
            return None, "memory-budget is only valid with memory salient_turns."

    if (
        summary_interval_raw is not None
        or summary_max_raw is not None
        or summary_tail_raw is not None
    ):
        if memory_module_id not in (None, "rolling_summary"):
            if memory_module_id is None or is_builtin_module_id(memory_module_id):
                return (
                    None,
                    "memory-summary-interval, memory-summary-max, and memory-summary-tail "
                    "are only valid with memory rolling_summary.",
                )

    module_config: dict[str, int] = {}
    if memory_window_raw is not None:
        try:
            module_config["window"] = int(memory_window_raw)
        except ValueError:
            return None, "memory-window must be an integer."

    if memory_budget_raw is not None:
        try:
            module_config["char_budget"] = int(memory_budget_raw)
        except ValueError:
            return None, "memory-budget must be an integer."

    if summary_interval_raw is not None:
        try:
            module_config["summary_interval"] = int(summary_interval_raw)
        except ValueError:
            return None, "memory-summary-interval must be an integer."

    if summary_max_raw is not None:
        try:
            module_config["max_summary_chars"] = int(summary_max_raw)
        except ValueError:
            return None, "memory-summary-max must be an integer."

    if summary_tail_raw is not None:
        try:
            module_config["summary_tail"] = int(summary_tail_raw)
        except ValueError:
            return None, "memory-summary-tail must be an integer."

    if (
        memory_module_id is None
        and memory_window_raw is None
        and memory_budget_raw is None
        and summary_interval_raw is None
        and summary_max_raw is None
        and summary_tail_raw is None
    ):
        return Memory(), None

    resolved_id = memory_module_id
    if resolved_id is None:
        if memory_budget_raw is not None:
            resolved_id = "salient_turns"
        elif summary_interval_raw is not None or summary_max_raw is not None or summary_tail_raw is not None:
            resolved_id = "rolling_summary"
        else:
            resolved_id = "recent_turns"
    if not is_module_loaded(resolved_id):
        return None, (
            f"Memory module {resolved_id!r} is not loaded. "
            "Use add-memory-module or load the module before create-agent."
        )
    try:
        return Memory(module_id=resolved_id, **module_config), None
    except ValueError as exc:
        return None, str(exc)


def create_agent_from_args(area: Area, arg: str) -> tuple[Optional[Agent], str]:
    """
    Parse and create an agent.

    Usage: name "..." [pdesc "..."] [desc "..."] [appearance "..."] [personality "..."] [memory MODULE_ID] [memory-window N] [memory-budget N] [memory-summary-interval N] [memory-summary-max N] [memory-summary-tail N] at x,y
    """
    tokens, err = tokenize_args(arg)
    if err:
        return None, err
    if not tokens:
        return None, (
            'Usage: create-agent name "..." [pdesc "..."] [desc "..."] [appearance "..."] '
            '[personality "..."] [move-speed N] [memory MODULE_ID] [memory-window N] '
            '[memory-budget N] [memory-summary-interval N] [memory-summary-max N] '
            '[memory-summary-tail N] at x,y'
        )

    fields, err = parse_field_tokens(
        tokens,
        {
            "name",
            "pdesc",
            "desc",
            "appearance",
            "personality",
            "move-speed",
            "memory",
            "memory-window",
            "memory-budget",
            "memory-summary-interval",
            "memory-summary-max",
            "memory-summary-tail",
            "at",
            "blocks-movement",
            "movement-exception",
            "player",
        },
    )
    if err:
        return None, err

    from campaign_rpg_engine.world_edit_api import create_agent_from_fields

    return create_agent_from_fields(area, fields)


def _apply_agent_content_fields(
    area: Area,
    agent: Agent,
    agent_id: str,
    fields: dict[str, str],
    changes: list[str],
) -> Optional[str]:
    if "name" in fields and fields["name"] != agent.name:
        if agent_name_conflicts_with_commands(fields["name"]):
            return reserved_agent_name_message(fields["name"])
        if agent_name_taken(area, fields["name"], exclude_agent_id=agent_id):
            return f"Agent name '{fields['name']}' is already in use."
        agent.name = fields["name"]
        changes.append("name")

    if "pdesc" in fields and fields["pdesc"] != agent.passive_description:
        agent.passive_description = fields["pdesc"]
        changes.append("pdesc")

    if "appearance" in fields and fields["appearance"] != agent.appearance:
        agent.appearance = fields["appearance"]
        changes.append("appearance")

    if "desc" in fields and fields["desc"] != agent.description:
        agent.description = fields["desc"]
        if fields["desc"]:
            area.invalidate_entity_knowledge(agent_id)
        else:
            area.clear_entity_examination_history(agent_id)
        changes.append("desc")

    if "personality" in fields and fields["personality"] != agent.personality:
        agent.personality = fields["personality"]
        changes.append("personality")

    if "move-speed" in fields:
        move_speed, speed_err = parse_move_speed(fields["move-speed"])
        if speed_err:
            return speed_err
        if move_speed != agent.move_speed:
            agent.move_speed = move_speed
            changes.append("move-speed")

    if "player" in fields:
        is_player, player_err = parse_bool_field(fields["player"], field_name="player")
        if player_err:
            return player_err
        assert is_player is not None
        if is_player != agent.is_player:
            agent.is_player = is_player
            changes.append("player")

    return _apply_movement_fields(agent, fields, changes)


def _apply_agent_location_fields(
    session: Session,
    agent_id: str,
    located_area_id: str,
    agent: Agent,
    fields: dict[str, str],
    changes: list[str],
) -> Optional[str]:
    dest_area_id = (
        fields.get("area", located_area_id).strip()
        if "area" in fields
        else located_area_id
    )
    if "area" in fields and dest_area_id not in session.areas:
        return f"Unknown area {dest_area_id!r}."

    target_pos = agent.position
    if "pos" in fields:
        target_pos, err = parse_position(fields["pos"])
        if err:
            return err
        assert target_pos is not None

    if dest_area_id != located_area_id:
        result = session.transfer_agent(agent_id, dest_area_id, target_pos)
        if not result.ok:
            return result.message
        changes.append("area")
        if "pos" in fields:
            changes.append("pos")
    elif "pos" in fields and target_pos != agent.position:
        area = session.areas[located_area_id]
        if not area.is_valid_position(target_pos):
            return (
                f"Invalid position {target_pos}. "
                f"{area.format_grid_bounds_message()}"
            )
        agent.position = target_pos
        changes.append("pos")
    return None


def edit_agent_for_session(session: Session, arg: str) -> EditAgentResult:
    """
    Parse and edit an agent anywhere in a multi-area session.

    Supports ``area <area_id>`` to move the agent between areas (with optional ``pos``).
    """
    tokens, err = tokenize_args(arg)
    if err:
        return EditAgentResult(ok=False, message=err)
    if not tokens:
        return EditAgentResult(
            ok=False,
            message=(
                'Usage: edit-agent <id> [pdesc "..."] [desc "..."] [appearance "..."] '
                '[personality "..."] [move-speed N] [name "..."] [area <area_id>] [pos x,y] ...'
            ),
        )

    agent_id = tokens[0]
    if not agent_id.startswith("agent_"):
        return EditAgentResult(
            ok=False,
            message=(
                f"Commands require agent id (e.g. agent_01), not display name. "
                f"Use 'agents' or 'list' to look up ids."
            ),
        )

    located_area_id = session.agent_area.get(agent_id)
    if located_area_id is None or located_area_id not in session.areas:
        return EditAgentResult(
            ok=False,
            message=f"Agent '{agent_id}' not found. Use 'agents' or 'list' to look up ids.",
        )
    area = session.areas[located_area_id]
    agent = area.get_agent_by_id(agent_id)
    if agent is None:
        return EditAgentResult(
            ok=False,
            message=f"Agent '{agent_id}' not found. Use 'agents' or 'list' to look up ids.",
        )

    fields, err = parse_field_tokens(
        tokens[1:],
        {
            "name",
            "pdesc",
            "desc",
            "appearance",
            "personality",
            "move-speed",
            "pos",
            "area",
            "blocks-movement",
            "movement-exception",
            "player",
        },
    )
    if err:
        return EditAgentResult(ok=False, message=err)
    if not fields:
        return EditAgentResult(
            ok=False,
            message=(
                "At least one field to change is required "
                "(name, pdesc, desc, appearance, personality, move-speed, area, pos, or player)."
            ),
        )

    old_name_lower = agent.name.lower()
    changes: list[str] = []

    location_err = _apply_agent_location_fields(
        session, agent_id, located_area_id, agent, fields, changes
    )
    if location_err:
        return EditAgentResult(ok=False, message=location_err)

    current_area_id = located_area_id
    if "area" in fields and fields["area"].strip() != located_area_id:
        current_area_id = fields["area"].strip()
    current_area = session.areas[current_area_id]

    content_err = _apply_agent_content_fields(
        current_area, agent, agent_id, fields, changes
    )
    if content_err:
        return EditAgentResult(ok=False, message=content_err)

    if not changes:
        return EditAgentResult(ok=False, message=f"No changes applied to {agent_id}.")

    return EditAgentResult(
        ok=True,
        message=f"Updated agent {agent_id} ({', '.join(changes)}).",
        agent=agent,
        old_name_lower=old_name_lower if "name" in changes else None,
    )


def edit_agent_from_args(area: Area, arg: str) -> EditAgentResult:
    """
    Parse and edit an agent.

    Usage: <agent_id> [pdesc "..."] [desc "..."] [appearance "..."] [personality "..."] [move-speed N] [name "..."] [pos x,y] ...

    Memory module is set only at create-agent; edit-agent cannot change it.
    """
    tokens, err = tokenize_args(arg)
    if err:
        return EditAgentResult(ok=False, message=err)
    if not tokens:
        return EditAgentResult(
            ok=False,
            message=(
                'Usage: edit-agent <id> [pdesc "..."] [desc "..."] [appearance "..."] [personality "..."] '
                '[move-speed N] [name "..."] [pos x,y] ...'
            ),
        )

    agent_id = tokens[0]
    if not agent_id.startswith("agent_"):
        return EditAgentResult(
            ok=False,
            message=(
                f"Commands require agent id (e.g. agent_01), not display name. "
                f"Use 'agents' or 'list' to look up ids."
            ),
        )

    agent = area.get_agent_by_id(agent_id)
    if agent is None:
        return EditAgentResult(
            ok=False,
            message=f"Agent '{agent_id}' not found. Use 'agents' or 'list' to look up ids.",
        )

    fields, err = parse_field_tokens(
        tokens[1:],
        {
            "name",
            "pdesc",
            "desc",
            "appearance",
            "personality",
            "move-speed",
            "pos",
            "blocks-movement",
            "movement-exception",
            "player",
        },
    )
    if err:
        return EditAgentResult(ok=False, message=err)
    if not fields:
        return EditAgentResult(
            ok=False,
            message=(
                "At least one field to change is required "
                "(name, pdesc, desc, appearance, personality, move-speed, pos, or player)."
            ),
        )

    old_name_lower = agent.name.lower()
    changes: list[str] = []

    content_err = _apply_agent_content_fields(area, agent, agent_id, fields, changes)
    if content_err:
        return EditAgentResult(ok=False, message=content_err)

    if "pos" in fields:
        position, err = parse_position(fields["pos"])
        if err:
            return EditAgentResult(ok=False, message=err)
        assert position is not None
        if not area.is_valid_position(position):
            return EditAgentResult(
                ok=False,
                message=f"Invalid position {position}. {area.format_grid_bounds_message()}",
            )
        if position != agent.position:
            agent.position = position
            changes.append("pos")

    if not changes:
        return EditAgentResult(ok=False, message=f"No changes applied to {agent_id}.")

    return EditAgentResult(
        ok=True,
        message=f"Updated agent {agent_id} ({', '.join(changes)}).",
        agent=agent,
        old_name_lower=old_name_lower if "name" in changes else None,
    )


def delete_agent_by_id(area: Area, agent_id: str) -> DeleteAgentResult:
    """Delete an agent by id. Rejects deleting the last agent."""
    agent_id = agent_id.strip()
    if not agent_id:
        return DeleteAgentResult(ok=False, message="Usage: delete-agent <id>")
    if not agent_id.startswith("agent_"):
        return DeleteAgentResult(
            ok=False,
            message=(
                f"Commands require agent id (e.g. agent_01), not display name. "
                f"Use 'agents' or 'list' to look up ids."
            ),
        )

    agent = area.get_agent_by_id(agent_id)
    if agent is None:
        return DeleteAgentResult(
            ok=False,
            message=f"Agent '{agent_id}' not found. Use 'agents' or 'list' to look up ids.",
        )

    if len(area.agents) <= 1:
        return DeleteAgentResult(
            ok=False,
            message="Cannot delete the last agent in the area.",
        )

    area.remove_agent(agent_id)
    return DeleteAgentResult(
        ok=True,
        message=f"Deleted agent {agent_id}.",
        deleted_agent=agent,
    )


def create_area_from_args(session: Session, arg: str):
    """
    Parse ``create-area`` stepper arguments and call typed area CRUD.

    For app-owned command dispatch — not part of ``Session`` public API.
    """
    from campaign_rpg_engine.session_area_edit import (
        AreaMutationResult,
        create_area_in_session,
        parse_bounds_fields,
        validate_area_id,
    )

    tokens, err = tokenize_args(arg)
    if err:
        return AreaMutationResult(ok=False, message=err)
    if not tokens:
        return AreaMutationResult(
            ok=False,
            message=(
                'Usage: create-area id <area_id> [desc "..."] '
                "[width N] [height N]  (defaults: 5x5 grid)"
            ),
        )

    fields, err = parse_field_tokens(
        tokens,
        {"id", "desc", "width", "height", "min-x", "min-y", "max-x", "max-y"},
    )
    if err:
        return AreaMutationResult(ok=False, message=err)
    if "id" not in fields:
        return AreaMutationResult(ok=False, message="create-area requires id <area_id>.")

    area_id = fields["id"]
    id_err = validate_area_id(area_id)
    if id_err:
        return AreaMutationResult(ok=False, message=id_err)
    if area_id in session.areas:
        return AreaMutationResult(ok=False, message=f"Area {area_id!r} already exists.")

    bounds, err = parse_bounds_fields(fields)
    if err:
        return AreaMutationResult(ok=False, message=err)
    assert bounds is not None

    return create_area_in_session(
        session,
        area_id,
        description=fields.get("desc", ""),
        bounds=bounds,
    )


def edit_area_from_args(session: Session, arg: str):
    """
    Parse ``edit-area`` stepper arguments and call typed area CRUD.

    For app-owned command dispatch — not part of ``Session`` public API.
    """
    from campaign_rpg_engine.session_area_edit import AreaMutationResult, edit_area_in_session, validate_area_id

    tokens, err = tokenize_args(arg)
    if err:
        return AreaMutationResult(ok=False, message=err)
    if not tokens:
        return AreaMutationResult(
            ok=False,
            message='Usage: edit-area <area_id> [desc "..."] [width N] [height N]',
        )

    area_id = tokens[0]
    id_err = validate_area_id(area_id)
    if id_err:
        return AreaMutationResult(ok=False, message=id_err)
    if area_id not in session.areas:
        return AreaMutationResult(ok=False, message=f"Unknown area {area_id!r}.")

    fields, err = parse_field_tokens(
        tokens[1:],
        {"desc", "width", "height", "min-x", "min-y", "max-x", "max-y"},
    )
    if err:
        return AreaMutationResult(ok=False, message=err)
    if not fields:
        return AreaMutationResult(
            ok=False,
            message="edit-area requires at least one field to change.",
        )

    area = session.areas[area_id]
    description = fields["desc"] if "desc" in fields else None
    width = height = min_x = min_y = max_x = max_y = None
    if any(k in fields for k in ("width", "height", "min-x", "min-y", "max-x", "max-y")):
        if any(k in fields for k in ("min-x", "min-y", "max-x", "max-y")):
            min_x = int(fields.get("min-x", str(area.bounds.min_x)))
            min_y = int(fields.get("min-y", str(area.bounds.min_y)))
            max_x = int(fields.get("max-x", str(area.bounds.max_x)))
            max_y = int(fields.get("max-y", str(area.bounds.max_y)))
        else:
            width = int(fields.get("width", str(area.bounds.width)))
            height = int(fields.get("height", str(area.bounds.height)))

    return edit_area_in_session(
        session,
        area_id,
        description=description,
        width=width,
        height=height,
        min_x=min_x,
        min_y=min_y,
        max_x=max_x,
        max_y=max_y,
    )
