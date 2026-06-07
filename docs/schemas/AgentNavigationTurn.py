"""
AgentNavigationTurn Schema - V0.2 (Design Reference)

Authoritative runtime: `src/llm/schemas.py`

This file mirrors the navigation-phase schema for planning review.
See docs/v0.2-implementation-readiness-checklist.md (Section 2).

Navigation phase output — always the first LLM call per agent turn.
Post-move action phase uses AgentActionTurn.

V0.2 rules:
- move_target: canonical "x,y" (parser also accepts "(x,y)" silently)
- null move_target = stay in place
- reasoning max 400 chars; confidence/emotion 1-3 words
- Cardinal directions are not valid

Last synced: 2026-06-05 (v0.2 prep)
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

    confidence: Optional[str] = Field(
        default=None,
        description="1-3 words (e.g. 'certain', 'hesitant').",
    )

    emotion: Optional[str] = Field(
        default=None,
        description="1-3 words (e.g. 'curious', 'uneasy').",
    )
