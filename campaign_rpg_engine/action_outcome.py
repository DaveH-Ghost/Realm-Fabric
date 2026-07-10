"""Action result types — first-person result for the actor, passive for observers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionOutcome:
    """Result of executing one action."""

    result: str
    """First-person feedback for the acting agent (stored in TurnRecord)."""

    passive_result: str = ""
    """
    Third-person summary for other agents' passive vision.

    Empty when the action did not succeed or has nothing observable.
    """
