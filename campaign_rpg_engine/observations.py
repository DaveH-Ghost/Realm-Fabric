"""Broadcast observable agent actions to other agents' memory modules."""

from __future__ import annotations

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.area_event import AREA_EVENT_ACTOR_ID, AREA_EVENT_ACTOR_NAME
from campaign_rpg_engine.emote_phrasing import emote_target_phrase_for_witness, format_emote_line
from campaign_rpg_engine.memory_modules.base import WitnessedEvent
from campaign_rpg_engine.perception import get_visible_look_target_ids
from campaign_rpg_engine.turn_record import TurnStep

_PRIMARY_WITNESS_KINDS = frozenset({"move", "speak", "emote", "interact", "verb"})


def observable_witness_steps(steps: list[TurnStep]) -> list[TurnStep]:
    """
    Return turn steps that should be broadcast to observing agents.

    move, speak, emote, and interact are always included when they have
    ``passive_result``. look is included only when no primary action ran —
    so witnesses still see that the actor did something rather than nothing.
    """
    has_primary = any(step.kind in _PRIMARY_WITNESS_KINDS for step in steps)
    witness_steps: list[TurnStep] = []
    for step in steps:
        if step.kind in _PRIMARY_WITNESS_KINDS:
            if step.passive_result:
                witness_steps.append(step)
        elif step.kind == "look" and not has_primary and step.passive_result:
            witness_steps.append(step)
    return witness_steps


def can_observe_agent(observer: Agent, actor: Agent, area: Area) -> bool:
    """Return True if the actor appears in the observer's passive vision."""
    if observer.id == actor.id:
        return False
    return actor.id in get_visible_look_target_ids(observer, area)


def _witness_text_for_emote(
    actor: Agent,
    area: Area,
    emote_step: TurnStep,
    observer: Agent,
) -> str:
    action_name = (emote_step.content or "").strip()
    target = (emote_step.target or "").strip()
    if not target:
        return format_emote_line(actor.name, action_name, "")
    phrase = emote_target_phrase_for_witness(area, target, observer)
    return format_emote_line(actor.name, action_name, phrase)


def _witness_text_for_step(
    actor: Agent,
    area: Area,
    step: TurnStep,
    observer: Agent,
) -> str:
    if step.kind == "emote":
        return _witness_text_for_emote(actor, area, step, observer)
    return step.passive_result or ""


def broadcast_actor_turn(
    area: Area,
    actor: Agent,
    *,
    session_turn: int,
    steps: list[TurnStep],
) -> None:
    """
    Record the actor's observable actions in each observing agent's memory module.

    Emits one witnessed event per observable step (see ``observable_witness_steps``).
    Emote steps use per-observer target phrasing (``you`` for the emote target).
    """
    witness_steps = observable_witness_steps(steps)
    if not witness_steps:
        return

    for observer in area.agents:
        if not can_observe_agent(observer, actor, area):
            continue
        for step in witness_steps:
            if observer.id in step.passive_witness_exclude_agent_ids:
                continue
            text = _witness_text_for_step(actor, area, step, observer)
            if not text:
                continue
            event = WitnessedEvent(
                session_turn=session_turn,
                actor_id=actor.id,
                actor_name=actor.name,
                text=text,
                actor_position=actor.position,
            )
            observer.memory.record_observation(event, observer_id=observer.id)


def broadcast_area_event(
    *,
    session_turn: int,
    text: str,
    agents: list[Agent],
) -> None:
    """
    Record an area event in the given agents' memory modules.

    Uses a pseudo-actor so area events are distinct from agent passive_result.
    """
    if not agents:
        return

    event = WitnessedEvent(
        session_turn=session_turn,
        actor_id=AREA_EVENT_ACTOR_ID,
        actor_name=AREA_EVENT_ACTOR_NAME,
        text=text,
        actor_position=(-1, -1),
    )
    for agent in agents:
        agent.memory.record_observation(event, observer_id=agent.id)
