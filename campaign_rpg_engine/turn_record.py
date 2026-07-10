from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


StepKind = Literal["move", "look", "speak", "interact", "emote"]


@dataclass
class TurnStep:
    """One sub-step inside a compound agent turn (V0.2.5 ingestion hook)."""

    kind: StepKind
    reasoning: str
    target: Optional[str]
    content: Optional[str]
    result: str
    passive_result: str = ""


@dataclass
class TurnRecord:
    """
    A record of one compound agent turn in the agent's history.

    One TurnRecord per agent turn (move + optional look + optional turn action).
    """

    turn_number: int
    steps: list[TurnStep]
    result: str
    reasoning: str
