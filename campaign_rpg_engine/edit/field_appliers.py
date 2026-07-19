"""
field_appliers.py (1.6.0)

Shared low-level field parsers, id/name helpers, and entity field-appliers used
by both ``area_edit`` (CLI-style dispatch) and ``world_edit_api`` (typed API).

Extracted from ``area_edit`` to break the ``world_edit_api`` -> ``area_edit``
module-level import cycle. ``area_edit`` re-exports these names for backward
compatibility.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from campaign_rpg_engine.session import Session

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.memory_modules.registry import (
    format_memory_module_label,
    is_builtin_module_id,
    is_module_loaded,
    unknown_memory_module_message,
)
from campaign_rpg_engine.object import Object, object_footprint_fits_bounds
from campaign_rpg_engine.reserved_names import (
    agent_name_conflicts_with_commands,
    reserved_agent_name_message,
)

__all__ = [
    "slugify_display_name",
    "generate_object_id",
    "generate_agent_id",
    "agent_name_taken",
    "agent_name_conflicts_with_commands",
    "reserved_agent_name_message",
    "format_memory_module_label",
    "parse_position",
    "parse_move_speed",
    "parse_bool_field",
    "parse_movement_exceptions",
    "_apply_movement_fields",
    "_apply_hidden_fields",
    "_parse_footprint_dims",
    "_validate_object_footprint_in_area",
    "_apply_footprint_dim_fields",
    "_apply_object_content_fields",
    "_apply_object_location_fields",
    "_build_agent_memory",
]


def slugify_display_name(name: str) -> str:
    """Lowercase, spaces to underscores, strip non-alphanumeric."""
    slug = name.lower().replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "new"


def generate_object_id(
    area: Area,
    display_name: str,
    *,
    reserved_ids: frozenset[str] | None = None,
) -> str:
    """Auto-generate a unique object id from a display name."""
    slug = slugify_display_name(display_name)
    existing = {obj.id for obj in area.objects}
    if reserved_ids:
        existing |= set(reserved_ids)
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


def agent_name_taken(area: Area, name: str, exclude_agent_id: str | None = None) -> bool:
    """Return True if another agent already has this name (case-insensitive)."""
    name_lower = name.lower()
    for agent in area.agents:
        if exclude_agent_id and agent.id == exclude_agent_id:
            continue
        if agent.name.lower() == name_lower:
            return True
    return False


def parse_position(value: str) -> tuple[tuple[int, int] | None, str | None]:
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


def parse_move_speed(value: str) -> tuple[int | None, str | None]:
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


def parse_bool_field(value: str, *, field_name: str) -> tuple[bool | None, str | None]:
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
) -> str | None:
    if "blocks-movement" in fields:
        blocks, err = parse_bool_field(fields["blocks-movement"], field_name="blocks-movement")
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
) -> str | None:
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


def _apply_object_content_fields(
    area: Area,
    obj: Object,
    object_id: str,
    fields: dict[str, str],
    changes: list[str],
) -> str | None:
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
) -> str | None:
    dest_area_id = (
        fields.get("area", located_area_id).strip() if "area" in fields else located_area_id
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


def _build_agent_memory(fields: dict[str, str]) -> tuple[Memory | None, str | None]:
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
    ) and memory_module_id not in (None, "rolling_summary", "affinity"):
        if memory_module_id is None or is_builtin_module_id(memory_module_id):
            return (
                None,
                "memory-summary-interval, memory-summary-max, and memory-summary-tail "
                "are only valid with memory rolling_summary or affinity.",
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
        elif (
            summary_interval_raw is not None
            or summary_max_raw is not None
            or summary_tail_raw is not None
        ):
            resolved_id = "rolling_summary"
        else:
            resolved_id = "recent_turns"
    if not is_module_loaded(resolved_id):
        return None, unknown_memory_module_message(resolved_id)
    try:
        return Memory(module_id=resolved_id, **module_config), None
    except ValueError as exc:
        return None, str(exc)
