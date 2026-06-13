"""
perception.py

Passive vision and look logic.

Responsibilities:
- Build the "Current Passive Vision" text block shown to the agent each turn.
- Passive vs detailed rendering for objects and other agents (V0.1+).
- Provide look logic: validate targets, return descriptions, update memory.

The viewing agent sees objects and other agents in passive vision (not itself).
Walls/room boundaries are conveyed via the separate room description from Area.
"""

from src.action_outcome import ActionOutcome
from src.agent import Agent
from src.grid import chebyshev_distance
from src.memory import Memory
from src.object import Object
from src.object_action import ObjectAction
from src.area import Area


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


def build_passive_vision(agent: Agent, area: Area) -> str:
    """
    Build the passive vision block for the given agent.

    Format:
    You are at (x, y).
    {name} ({id}), {coordinates} - {description fragment}
    """
    lines = [f"You are at {agent.position}."]
    memory = agent.memory

    for obj in area.get_objects():
        desc = format_object_vision_desc(obj, memory)
        if desc:
            lines.append(f"{obj.name} ({obj.id}), {obj.position} - {desc}")
        else:
            lines.append(f"{obj.name} ({obj.id}), {obj.position}")

    for other in area.agents:
        if other.id == agent.id:
            continue
        desc = format_agent_vision_desc(other, memory)
        if desc:
            lines.append(f"{other.name} ({other.id}), {other.position} - {desc}")
        else:
            lines.append(f"{other.name} ({other.id}), {other.position}")

    return "\n".join(lines)


def get_visible_look_target_ids(agent: Agent, area: Area) -> list[str]:
    """
    Return entity IDs (objects and other agents) visible in passive vision.

    Used to validate look targets, including entries marked with [?].
    """
    ids = [obj.id for obj in area.get_objects()]
    ids.extend(other.id for other in area.agents if other.id != agent.id)
    return ids


def get_visible_object_ids(agent: Agent, area: Area) -> list[str]:
    """Return object IDs visible in passive vision."""
    return [obj.id for obj in area.get_objects()]


def is_object_in_passive_vision(agent: Agent, area: Area, object_id: str) -> bool:
    """Return True if the object appears in the agent's passive vision."""
    return object_id in get_visible_object_ids(agent, area)


def get_available_interactions(
    agent: Agent, area: Area
) -> list[tuple[str, str, Object, ObjectAction]]:
    """
    Return in-range object interactions for the action-phase prompt.

    Each entry is (action_name, object_id, object, action).
    """
    results: list[tuple[str, str, Object, ObjectAction]] = []
    visible = set(get_visible_object_ids(agent, area))
    for obj in area.get_objects():
        if obj.id not in visible:
            continue
        for action_name, action in obj.actions.items():
            if chebyshev_distance(agent.position, obj.position) <= action.range:
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
