"""Emote turn action — gesture at an entity or free-text target (V0.4.2)."""

from __future__ import annotations

from campaign_rpg_engine.action_outcome import ActionOutcome
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.emote_phrasing import (
    emote_target_phrase_for_actor,
    emote_target_phrase_neutral,
    format_emote_line,
)


def emote(agent: Agent, area: Area, target: str, action_name: str) -> ActionOutcome:
    """Perform a past-tense emote directed at *target*."""
    verb = action_name.strip()
    target_id = target.strip()
    actor_phrase = emote_target_phrase_for_actor(area, agent, target_id)
    neutral_phrase = emote_target_phrase_neutral(area, target_id)
    return ActionOutcome(
        result=f"You {verb} at {actor_phrase}.",
        passive_result=format_emote_line(agent.name, verb, neutral_phrase),
    )
