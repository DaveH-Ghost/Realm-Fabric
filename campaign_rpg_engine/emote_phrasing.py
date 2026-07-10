"""Target phrasing for emote turn actions (V0.4.2)."""

from __future__ import annotations

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area


def emote_target_phrase_neutral(area: Area, target: str) -> str:
    """Third-person target label for stored passive_result."""
    obj = area.get_object_by_id(target)
    if obj is not None:
        return f"the {obj.name}"
    other = area.get_agent_by_id(target)
    if other is not None:
        return other.name
    return target


def emote_target_phrase_for_actor(area: Area, actor: Agent, target: str) -> str:
    """First-person target label in the actor's result line."""
    if target == actor.id:
        return "yourself"
    return emote_target_phrase_neutral(area, target)


def emote_target_phrase_for_witness(
    area: Area,
    target: str,
    observer: Agent,
) -> str:
    """Target label for a witness (uses ``you`` when they are the emote target)."""
    other = area.get_agent_by_id(target)
    if other is not None and other.id == observer.id:
        return "you"
    return emote_target_phrase_neutral(area, target)


def format_emote_line(actor_name: str, action_name: str, target_phrase: str) -> str:
    return f"{actor_name} {action_name} at {target_phrase}."
