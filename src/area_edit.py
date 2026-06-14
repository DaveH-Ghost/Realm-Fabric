"""
area_edit.py

Parsing, validation, and area mutations for V0.1 editing commands.
Used by the manual stepper in main.py.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Optional

from src.agent import Agent
from src.memory import Memory
from src.memory_modules.registry import format_memory_module_label
from src.object import Object
from src.object_action import ObjectAction
from src.object_effects import validate_effect_name
from src.stepper_commands import (
    agent_name_conflicts_with_commands,
    reserved_agent_name_message,
)
from src.area import Area


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


def tokenize_args(arg: str) -> tuple[Optional[list[str]], Optional[str]]:
    """Split arguments with shlex. Returns (tokens, error_message)."""
    try:
        return shlex.split(arg), None
    except ValueError as e:
        return None, f"Invalid quoting in arguments: {e}"


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


def parse_field_tokens(
    tokens: list[str], allowed: set[str]
) -> tuple[dict[str, str], Optional[str]]:
    """Parse keyword/value pairs (case-insensitive keys)."""
    fields: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        key = tokens[i].lower()
        if key not in allowed:
            return {}, f"Unknown or unexpected token: '{tokens[i]}'"
        if i + 1 >= len(tokens):
            return {}, f"Missing value for '{key}'"
        if key in fields:
            return {}, f"Duplicate field '{key}' in arguments."
        fields[key] = tokens[i + 1]
        i += 2
    return fields, None


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
            lines.append(
                f"  - {obj.name} ({obj.id}) at {obj.position}{action_suffix}"
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
            lines.append(
                f"  - {agent.name} ({agent.id}) at {agent.position}"
                f" {format_memory_module_label(agent.memory.module)}{marker}"
            )
    return "\n".join(lines)


def format_full_list(area: Area, active_agent: Optional[Agent]) -> str:
    """Format agents then objects (same as running agents + objects)."""
    return f"{format_agents_list(area, active_agent)}\n\n{format_objects_list(area)}"


def parse_object_action_fields(
    fields: dict[str, str],
) -> tuple[dict[str, ObjectAction] | None, Optional[str]]:
    """
    Build actions dict from optional action/range/effect/result/passive fields.

    When ``action`` is absent, returns an empty dict. When present, requires
    result and passive; range defaults to 0; effect is optional.
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

    effects: list[str] = []
    effect_name = fields.get("effect")
    if effect_name:
        err = validate_effect_name(effect_name)
        if err:
            return None, err
        effects = [effect_name]

    action = ObjectAction(
        name=name,
        range=action_range,
        result=result,
        passive_result=passive,
        effects=effects,
    )
    return {name: action}, None


def create_object_from_args(area: Area, arg: str) -> tuple[Optional[Object], str]:
    """
    Parse and create an object from command arguments.

    Usage: name "..." [pdesc "..."] [desc "..."] [appearance "..."] at x,y
           [action NAME range N [effect EFFECT] result "..." passive "..."]
    """
    tokens, err = tokenize_args(arg)
    if err:
        return None, err
    if not tokens:
        return None, (
            'Usage: create-object name "..." [pdesc "..."] [desc "..."] [appearance "..."] at x,y '
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
            "effect",
            "result",
            "passive",
        },
    )
    if err:
        return None, err
    if "name" not in fields:
        return None, "Missing required field: name"
    if "at" not in fields:
        return None, "Missing required field: at"

    position, err = parse_position(fields["at"])
    if err:
        return None, err
    assert position is not None

    if not area.is_valid_position(position):
        return None, f"Invalid position {position}. {area.format_grid_bounds_message()}"

    actions, err = parse_object_action_fields(fields)
    if err:
        return None, err
    assert actions is not None

    desc = fields.get("desc", "")
    pdesc = fields.get("pdesc", "")
    appearance = fields.get("appearance", "")
    obj_id = generate_object_id(area, fields["name"])
    obj = Object(
        id=obj_id,
        name=fields["name"],
        description=desc,
        position=position,
        passive_description=pdesc,
        actions=actions,
        appearance=appearance,
    )
    area.add_object(obj)
    action_note = ""
    if actions:
        action_note = f" Action(s): {', '.join(sorted(actions))}."
    return obj, (
        f'Created object {obj_id} "{fields["name"]}" at {position}.{action_note} '
        f"Use 'objects' or 'list' to see all object ids."
    )


def _edit_object_add_action(obj: Object, tokens: list[str]) -> str:
    """Parse add-action subcommand on edit-object."""
    if len(tokens) < 3:
        return (
            'Usage: edit-object <id> add-action <name> range N '
            '[effect E] result "..." passive "..."'
        )

    action_name = tokens[2]
    fields, err = parse_field_tokens(
        tokens[3:], {"range", "effect", "result", "passive"}
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

    fields, err = parse_field_tokens(tokens[1:], {"name", "desc", "pdesc", "appearance", "pos"})
    if err:
        return err
    if not fields:
        return "At least one field to change is required (name, pdesc, desc, appearance, or pos)."

    changes: list[str] = []

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

    if "pos" in fields:
        position, err = parse_position(fields["pos"])
        if err:
            return err
        assert position is not None
        if not area.is_valid_position(position):
            return f"Invalid position {position}. {area.format_grid_bounds_message()}"
        if position != obj.position:
            obj.position = position
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
    memory_budget_raw = fields.get("memory-budget")
    summary_interval_raw = fields.get("memory-summary-interval")
    summary_max_raw = fields.get("memory-summary-max")
    summary_tail_raw = fields.get("memory-summary-tail")

    if memory_budget_raw is not None and memory_module_id not in (None, "salient_turns"):
        return None, "memory-budget is only valid with memory salient_turns."

    if (
        summary_interval_raw is not None
        or summary_max_raw is not None
        or summary_tail_raw is not None
    ):
        if memory_module_id not in (None, "rolling_summary"):
            return (
                None,
                "memory-summary-interval, memory-summary-max, and memory-summary-tail "
                "are only valid with memory rolling_summary.",
            )

    module_config: dict[str, int] = {}
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
    try:
        return Memory(module_id=resolved_id, **module_config), None
    except ValueError as exc:
        return None, str(exc)


def create_agent_from_args(area: Area, arg: str) -> tuple[Optional[Agent], str]:
    """
    Parse and create an agent.

    Usage: name "..." [pdesc "..."] [desc "..."] [appearance "..."] [personality "..."] [memory MODULE_ID] [memory-budget N] [memory-summary-interval N] [memory-summary-max N] [memory-summary-tail N] at x,y
    """
    tokens, err = tokenize_args(arg)
    if err:
        return None, err
    if not tokens:
        return None, (
            'Usage: create-agent name "..." [pdesc "..."] [desc "..."] [appearance "..."] '
            '[personality "..."] [move-speed N] [memory MODULE_ID] [memory-budget N] '
            '[memory-summary-interval N] [memory-summary-max N] [memory-summary-tail N] at x,y'
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
            "memory-budget",
            "memory-summary-interval",
            "memory-summary-max",
            "memory-summary-tail",
            "at",
        },
    )
    if err:
        return None, err
    if "name" not in fields:
        return None, "Missing required field: name"
    if "at" not in fields:
        return None, "Missing required field: at"

    if agent_name_conflicts_with_commands(fields["name"]):
        return None, reserved_agent_name_message(fields["name"])

    if agent_name_taken(area, fields["name"]):
        return None, f"Agent name '{fields['name']}' is already in use."

    position, err = parse_position(fields["at"])
    if err:
        return None, err
    assert position is not None

    if not area.is_valid_position(position):
        return None, f"Invalid position {position}. {area.format_grid_bounds_message()}"

    pdesc = fields.get("pdesc", "")
    desc = fields.get("desc", "")
    appearance = fields.get("appearance", "")
    personality = fields.get("personality", "")
    move_speed: Optional[int] = None
    if "move-speed" in fields:
        move_speed, speed_err = parse_move_speed(fields["move-speed"])
        if speed_err:
            return None, speed_err
    memory, mem_err = _build_agent_memory(fields)
    if mem_err:
        return None, mem_err
    assert memory is not None

    agent_id = generate_agent_id(area, fields["name"])
    agent = Agent(
        id=agent_id,
        name=fields["name"],
        personality=personality,
        position=position,
        passive_description=pdesc,
        description=desc,
        appearance=appearance,
        move_speed=move_speed,
        memory=memory,
        last_action=None,
    )
    area.add_agent(agent)
    module_note = f" {format_memory_module_label(memory.module)}"
    return agent, (
        f'Created agent {agent_id} "{fields["name"]}" at {position}.{module_note}'
        f" Use 'agents' or 'list' to see all agent ids."
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
        tokens[1:], {"name", "pdesc", "desc", "appearance", "personality", "move-speed", "pos"}
    )
    if err:
        return EditAgentResult(ok=False, message=err)
    if not fields:
        return EditAgentResult(
            ok=False,
            message=(
                "At least one field to change is required "
                "(name, pdesc, desc, appearance, personality, move-speed, or pos)."
            ),
        )

    old_name_lower = agent.name.lower()
    changes: list[str] = []

    if "name" in fields and fields["name"] != agent.name:
        if agent_name_conflicts_with_commands(fields["name"]):
            return EditAgentResult(
                ok=False,
                message=reserved_agent_name_message(fields["name"]),
            )
        if agent_name_taken(area, fields["name"], exclude_agent_id=agent_id):
            return EditAgentResult(
                ok=False,
                message=f"Agent name '{fields['name']}' is already in use.",
            )
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
            return EditAgentResult(ok=False, message=speed_err)
        if move_speed != agent.move_speed:
            agent.move_speed = move_speed
            changes.append("move-speed")

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
