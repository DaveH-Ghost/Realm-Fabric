"""
speak.py

Implementation of the `speak` action for V0.
"""

from __future__ import annotations

from campaign_rpg_engine.action_outcome import ActionOutcome
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area


def speak(agent: Agent, area: Area, content: str) -> ActionOutcome:
    """The agent speaks the given content (always observable to others)."""
    text = content or ""
    return ActionOutcome(
        result=f'You said: "{text}"',
        passive_result=f'{agent.name} says: "{text}"',
    )
