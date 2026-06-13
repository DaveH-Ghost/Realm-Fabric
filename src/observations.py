"""Broadcast observable agent actions to other agents' memory modules."""

from src.agent import Agent
from src.area_event import AREA_EVENT_ACTOR_ID, AREA_EVENT_ACTOR_NAME
from src.memory_modules.base import WitnessedEvent
from src.perception import get_visible_look_target_ids
from src.area import Area


def can_observe_agent(observer: Agent, actor: Agent, area: Area) -> bool:
    """Return True if the actor appears in the observer's passive vision."""
    if observer.id == actor.id:
        return False
    return actor.id in get_visible_look_target_ids(observer, area)


def broadcast_actor_turn(
    area: Area,
    actor: Agent,
    *,
    session_turn: int,
) -> None:
    """
    Record the actor's passive_result in each observing agent's memory module.

    Call after the actor's passive_result is set for the turn.
    """
    if not actor.passive_result:
        return

    event = WitnessedEvent(
        session_turn=session_turn,
        actor_id=actor.id,
        actor_name=actor.name,
        text=actor.passive_result,
        actor_position=actor.position,
    )

    for observer in area.agents:
        if not can_observe_agent(observer, actor, area):
            continue
        observer.memory.record_observation(event, observer_id=observer.id)


def broadcast_area_event(
    area: Area,
    *,
    session_turn: int,
    text: str,
) -> None:
    """
    Record a room-wide event in every agent's memory module.

    Uses a pseudo-actor so area events are distinct from agent passive_result.
    """
    event = WitnessedEvent(
        session_turn=session_turn,
        actor_id=AREA_EVENT_ACTOR_ID,
        actor_name=AREA_EVENT_ACTOR_NAME,
        text=text,
        actor_position=(-1, -1),
    )
    for agent in area.agents:
        agent.memory.record_observation(event, observer_id=agent.id)
