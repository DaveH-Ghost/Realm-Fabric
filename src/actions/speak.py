"""
speak.py

Implementation of the `speak` action for V0.
"""

from src.action_outcome import ActionOutcome
from src.agent import Agent
from src.area import Area


def speak(agent: Agent, area: Area, content: str) -> ActionOutcome:
    """The agent speaks the given content (always observable to others)."""
    text = content or ""
    return ActionOutcome(
        result=f'You said: "{text}"',
        passive_result=f'{agent.name} says: "{text}"',
    )
