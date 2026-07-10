"""
perception.py

Passive vision and look logic.

Responsibilities:
- Build the "Current Passive Vision" text block shown to the agent each turn.
- Passive vs detailed rendering for objects and other agents (V0.1+).
- Provide look logic: validate targets, return descriptions, update memory.

Passive vision lists one line per object using the footprint tile nearest the
viewer for coordinates and bearing; multi-tile objects also show footprint
size (e.g. ``3×2 tiles``). Interaction range uses nearest-footprint Chebyshev distance.
"""
from __future__ import annotations

from campaign_rpg_engine.action_outcome import ActionOutcome
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.grid import chebyshev_distance
from campaign_rpg_engine.vision_bearing import format_action_range_label, format_relative_bearing_phrase
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.object import Object, chebyshev_distance_to_object, format_object_footprint_size, nearest_footprint_tile_to
from campaign_rpg_engine.object_action import ObjectAction
from campaign_rpg_engine.occupancy import is_tile_enterable, resolve_standable_goal
from campaign_rpg_engine.pathfinding import walk_with_pathfinding
from campaign_rpg_engine.area import Area


PASSIVE_VISION_LOOK_RULE = (
    "Detail marked [?] can be examined with look."
)
PASSIVE_VISION_NO_LOOK_TARGETS = (
    "There are currently no objects you have not looked at and "
    "cannot gain any new information from looking."
)


def format_vision_desc(
    memory: Memory,
    entity_id: str,
    passive: str,
    detailed: str,
) -> str:
    """
    Return the description fragment for one entity in passive vision.

    Shared rules for objects and other agents:
    - Detailed empty: no [?] tag; show passive only (if any).
    - Never examined + detailed present: [?], or [?] {passive} if passive set.
    - Current knowledge (looked_at): detailed if present, else passive.
    - Stale (ever_looked, invalidated): [?] [changed] {passive} (passive omitted if empty).
    """
    if memory.has_looked_at(entity_id):
        return detailed if detailed else passive

    if memory.has_ever_looked_at(entity_id) and detailed:
        if passive:
            return f"[?] [changed] {passive}"
        return "[?] [changed]"

    if not detailed:
        return passive

    if passive:
        return f"[?] {passive}"
    return "[?]"


def format_object_vision_desc(obj: Object, memory: Memory) -> str:
    """Return the description fragment for one object in passive vision."""
    return format_vision_desc(
        memory, obj.id, obj.passive_description, obj.description
    )


def format_agent_vision_desc(other: Agent, memory: Memory) -> str:
    """
    Return the description fragment for another agent in passive vision.

    Static pdesc/desc only ([?] rules). Observable actions (``passive_result``)
    are ingested into memory modules, not repeated here.
    """
    return format_vision_desc(
        memory, other.id, other.passive_description, other.description
    )


def build_passive_vision(
    agent: Agent,
    area: Area,
    *,
    include_you_are_at: bool = True,
    include_entity_coordinates: bool = True,
    include_relative_bearing: bool = False,
    vision_units: str = "",
    units_per_tile: int | None = None,
) -> str:
    """
    Build the passive vision block for the given agent.

    Includes look guidance, per-object interaction hints (indented), and agents.
    Interactions list actions reachable after spending full ``move_speed`` toward
    the object (same rules as interact pathing in 0.6.0b).
    """
    bearing_ready = (
        include_relative_bearing
        and units_per_tile is not None
        and units_per_tile > 0
    )
    lines: list[str] = []
    if include_you_are_at:
        lines.append(f"You are at {agent.position}.")
    lines.append(PASSIVE_VISION_LOOK_RULE)

    memory = agent.memory

    for obj in area.get_objects():
        if obj.hidden:
            continue
        desc = format_object_vision_desc(obj, memory)
        vision_position = nearest_footprint_tile_to(agent.position, obj)
        footprint_size = format_object_footprint_size(obj)
        lines.append(
            _format_passive_vision_entity_line(
                obj.name,
                obj.id,
                vision_position,
                desc,
                observer=agent.position,
                include_coordinates=include_entity_coordinates,
                include_relative_bearing=bearing_ready,
                vision_units=vision_units,
                units_per_tile=units_per_tile,
                footprint_size=footprint_size,
            )
        )
        lines.extend(
            _format_object_interaction_lines(
                agent,
                area,
                obj,
                vision_units=vision_units,
                units_per_tile=units_per_tile,
            )
        )

    for other in area.agents:
        if other.id == agent.id:
            continue
        desc = format_agent_vision_desc(other, memory)
        lines.append(
            _format_passive_vision_entity_line(
                other.name,
                other.id,
                other.position,
                desc,
                observer=agent.position,
                include_coordinates=include_entity_coordinates,
                include_relative_bearing=bearing_ready,
                vision_units=vision_units,
                units_per_tile=units_per_tile,
            )
        )

    if not get_available_look_targets(agent, area):
        lines.append(PASSIVE_VISION_NO_LOOK_TARGETS)

    return "\n".join(lines)


def _format_passive_vision_entity_line(
    name: str,
    entity_id: str,
    position: tuple[int, int],
    desc: str,
    *,
    observer: tuple[int, int],
    include_coordinates: bool,
    include_relative_bearing: bool = False,
    vision_units: str = "",
    units_per_tile: int | None = None,
    footprint_size: str = "",
) -> str:
    parts = [f"{name} ({entity_id})"]
    if include_coordinates:
        coord_parts = [f"{position}"]
        if footprint_size:
            coord_parts.append(footprint_size)
        parts.append(", ".join(coord_parts))
    if include_relative_bearing and units_per_tile is not None:
        bearing = format_relative_bearing_phrase(
            observer,
            position,
            units=vision_units,
            units_per_tile=units_per_tile,
        )
        if bearing:
            parts.append(bearing)
    prefix = ", ".join(parts)
    if desc:
        return f"{prefix} - {desc}"
    return prefix


def nearest_standable_in_interact_range(
    agent: Agent,
    area: Area,
    obj: Object,
    action: ObjectAction,
) -> tuple[int, int] | None:
    """Return the closest enterable tile from which *action* can be used on *obj*."""
    best: tuple[int, int] | None = None
    best_dist = 10**9
    for x in range(area.min_x, area.max_x + 1):
        for y in range(area.min_y, area.max_y + 1):
            pos = (x, y)
            if chebyshev_distance_to_object(pos, obj) > action.range:
                continue
            if not is_tile_enterable(area, pos, agent.id):
                continue
            dist = chebyshev_distance(agent.position, pos)
            if dist < best_dist:
                best_dist = dist
                best = pos
    return best


def position_after_move_budget(
    start: tuple[int, int],
    goal: tuple[int, int],
    move_speed: int | None,
    area: Area,
    mover_id: str,
) -> tuple[int, int]:
    """Simulate movement toward *goal* using the same budget rules as move/interact."""
    if start == goal:
        return start
    if move_speed is None:
        if is_tile_enterable(area, goal, mover_id):
            return goal
        standable = resolve_standable_goal(area, goal, mover_id)
        return standable if standable is not None else start
    final, _, _ = walk_with_pathfinding(start, goal, move_speed, area, mover_id)
    return final


def get_object_interactions_reachable_after_move(
    agent: Agent,
    area: Area,
    obj: Object,
) -> list[tuple[str, ObjectAction]]:
    """
    Return object actions reachable after spending full move budget toward *obj*.

    Each entry is ``(action_name, action)``. Sorted by action name.
    """
    results: list[tuple[str, ObjectAction]] = []
    for action_name, action in sorted(obj.actions.items()):
        if action.kind == "trigger":
            continue
        if chebyshev_distance_to_object(agent.position, obj) <= action.range:
            results.append((action_name, action))
            continue
        goal = nearest_standable_in_interact_range(agent, area, obj, action)
        if goal is None:
            continue
        simulated = position_after_move_budget(
            agent.position,
            goal,
            agent.move_speed,
            area,
            agent.id,
        )
        if chebyshev_distance_to_object(simulated, obj) <= action.range:
            results.append((action_name, action))
    return results


def _format_object_interaction_lines(
    agent: Agent,
    area: Area,
    obj: Object,
    *,
    vision_units: str = "",
    units_per_tile: int | None = None,
) -> list[str]:
    interactions = get_object_interactions_reachable_after_move(agent, area, obj)
    lines: list[str] = []
    for action_name, action in interactions:
        range_label = format_action_range_label(
            action.range,
            vision_units=vision_units,
            units_per_tile=units_per_tile,
        )
        lines.append(f"  - {action_name} ({range_label})")
    return lines


DEFAULT_PASSIVE_VISION_OPTIONS: dict[str, bool] = {
    "include_you_are_at": True,
    "include_entity_coordinates": True,
    "include_relative_bearing": False,
}


def normalize_passive_vision_options(
    options: dict[str, object] | None,
) -> dict[str, bool]:
    """Merge *options* with defaults for passive vision slot rendering."""
    merged = dict(DEFAULT_PASSIVE_VISION_OPTIONS)
    if options:
        for key in DEFAULT_PASSIVE_VISION_OPTIONS:
            if key in options:
                merged[key] = bool(options[key])
    return merged


def get_visible_look_target_ids(agent: Agent, area: Area) -> list[str]:
    """
    Return entity IDs (objects and other agents) visible in passive vision.

    Used to validate look targets, including entries marked with [?].
    """
    ids = [obj.id for obj in area.get_objects() if not obj.hidden]
    ids.extend(other.id for other in area.agents if other.id != agent.id)
    return ids


def get_visible_object_ids(agent: Agent, area: Area) -> list[str]:
    """Return object IDs visible in passive vision."""
    return [obj.id for obj in area.get_objects() if not obj.hidden]


def is_object_in_passive_vision(agent: Agent, area: Area, object_id: str) -> bool:
    """Return True if the object appears in the agent's passive vision."""
    return object_id in get_visible_object_ids(agent, area)


def get_available_interactions(
    agent: Agent, area: Area
) -> list[tuple[str, str, Object, ObjectAction]]:
    """
    Return in-range object interactions for the action-phase prompt.

    Each entry is (action_name, object_id, object, action).
    Deprecated for prompts — interactions are listed in passive vision (0.6.0c).
    """
    results: list[tuple[str, str, Object, ObjectAction]] = []
    visible = set(get_visible_object_ids(agent, area))
    for obj in area.get_objects():
        if obj.id not in visible:
            continue
        for action_name, action in obj.actions.items():
            if action.kind == "trigger":
                continue
            if chebyshev_distance_to_object(agent.position, obj) <= action.range:
                results.append((action_name, obj.id, obj, action))
    results.sort(key=lambda item: (item[2].name.lower(), item[0], item[1]))
    return results


def perform_look(agent: Agent, area: Area, target_id: str) -> ActionOutcome:
    """
    Execute the "look" action on an object or another agent.

    Returns first-person result for the actor and third-person passive_result
    when the target is visible (even if there is no detailed text to learn).
    """
    visible_ids = get_visible_look_target_ids(agent, area)
    if target_id not in visible_ids:
        return ActionOutcome(result="You don't see anything like that to look at.")

    if target_id.startswith("obj_"):
        obj = area.get_object_by_id(target_id)
        if obj is None:
            return ActionOutcome(result="You don't see anything like that to look at.")
        name = obj.name
        detailed = obj.description
    elif target_id.startswith("agent_"):
        other = area.get_agent_by_id(target_id)
        if other is None or other.id == agent.id:
            return ActionOutcome(result="You don't see anything like that to look at.")
        name = other.name
        detailed = other.description
    else:
        return ActionOutcome(result="You don't see anything like that to look at.")

    passive_result = f"{agent.name} examines {name}."

    if not detailed:
        if agent.memory.has_ever_looked_at(target_id):
            agent.memory.clear_examination(target_id)
        return ActionOutcome(
            result=f"You don't notice anything more about the {name.lower()}.",
            passive_result=passive_result,
        )

    agent.memory.mark_looked_at(target_id)
    return ActionOutcome(
        result=f"You looked at the {name.lower()}. {detailed}",
        passive_result=passive_result,
    )


def _vision_desc_shows_question_mark(
    memory: Memory, entity_id: str, passive: str, detailed: str
) -> bool:
    """True when passive vision would prefix the entity with [?]."""
    return format_vision_desc(memory, entity_id, passive, detailed).startswith(
        "[?]"
    )


def get_available_look_targets(agent: Agent, area: Area) -> list[str]:
    """Return entity IDs marked [?] in passive vision (hidden detail to examine)."""
    memory = agent.memory
    targets: list[str] = []
    for obj in area.get_objects():
        if _vision_desc_shows_question_mark(
            memory, obj.id, obj.passive_description, obj.description
        ):
            targets.append(obj.id)
    for other in area.agents:
        if other.id == agent.id:
            continue
        if _vision_desc_shows_question_mark(
            memory, other.id, other.passive_description, other.description
        ):
            targets.append(other.id)
    targets.sort()
    return targets
