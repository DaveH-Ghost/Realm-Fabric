from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StepKind = Literal["move", "look", "speak", "interact", "emote", "verb"]


@dataclass
class TurnStep:
    """One sub-step inside a compound agent turn (V0.2.5 ingestion hook)."""

    kind: StepKind
    reasoning: str
    target: str | None
    content: str | None
    result: str
    passive_result: str = ""
    passive_witness_exclude_agent_ids: tuple[str, ...] = ()


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
