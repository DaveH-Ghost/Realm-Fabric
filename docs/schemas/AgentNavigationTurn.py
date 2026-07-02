"""
AgentNavigationTurn — HISTORICAL (V0.2 two-phase turns)

!!! SUPERSEDED by AgentCompoundTurn (V0.2.5+) !!!

Authoritative current schema: [AgentCompoundTurn.py](AgentCompoundTurn.py) /
`src/llm/schemas.py`.

This file documented the **navigation phase** of the short-lived two-call
turn model (navigation LLM call, then action LLM call). Not used since V0.2.5.

See [schemas/README.md](README.md) and [v0.2.5 changelog](../changelog/v0.2.5-changelog.md).

Last synced: 2026-06-05 (historical)
"""

from pydantic import BaseModel, Field
from typing import Optional


class AgentNavigationTurn(BaseModel):
    """
    Structured output for the navigation phase of a compound agent turn.

    The orchestrator executes move_target (if non-null) before building
    the action-phase prompt with post-move passive vision.
    """

    reasoning: str = Field(
        description=(
            "Private internal thoughts for the navigation decision. "
            "Not visible to other agents. Max 400 characters."
        )
    )

    move_target: Optional[str] = Field(
        default=None,
        description=(
            "In-bounds grid coordinate as 'x,y' (e.g. '2,3'), or null to stay. "
            "Teleport within the 5x5 room (0-4 inclusive per axis). "
            "Parser may accept '(x,y)' variants without advertising them in prompts."
        ),
    )
