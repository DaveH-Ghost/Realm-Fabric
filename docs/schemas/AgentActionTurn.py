"""
AgentActionTurn Schema - V0.2 (Design Reference)

Authoritative runtime: `src/llm/schemas.py`

This file mirrors the action-phase schema for planning review.
See docs/v0.2-implementation-readiness-checklist.md (Sections 2–3).

Action phase output — always the second LLM call per agent turn.
Prompt uses post-move passive vision + available interact list.

V0.2 rules:
- At most one look_target per turn
- turn_action: speak | interact | none (not both speak and interact)
- speak: content required; max 5 sentences, 500 characters
- interact: target (object id) + action_name required
- look visibility and interact range validated at runtime, not in Pydantic

Last synced: 2026-06-05 (v0.2 prep)
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional


TurnActionType = Literal["speak", "interact", "none"]


class AgentActionTurn(BaseModel):
    """
    Structured output for the action phase of a compound agent turn.

    Executed after navigation phase and optional move. Pipeline:
    optional look -> optional turn action (speak or interact).
    """

    reasoning: str = Field(
        description=(
            "Private internal thoughts for look/speak/interact decisions. "
            "Not visible to other agents. Max 400 characters."
        )
    )

    look_target: Optional[str] = Field(
        default=None,
        description=(
            "Entity id to examine (e.g. 'obj_ball_01', 'agent_goblin_01'), "
            "or null to skip look. At most one look per action phase in V0.2."
        ),
    )

    turn_action: TurnActionType = Field(
        description=(
            "The turn-ending action: 'speak', 'interact' with an object action, "
            "or 'none' to end after optional look."
        )
    )

    target: Optional[str] = Field(
        default=None,
        description="Object id when turn_action is 'interact'.",
    )

    action_name: Optional[str] = Field(
        default=None,
        description="Named object action when turn_action is 'interact' (e.g. 'eat').",
    )

    content: Optional[str] = Field(
        default=None,
        description=(
            "Speak dialogue when turn_action is 'speak'. "
            "Max 5 sentences and 500 characters in V0.2."
        ),
    )

    confidence: Optional[str] = Field(
        default=None,
        description="1-3 words; appended to passive_result mood suffix when applicable.",
    )

    emotion: Optional[str] = Field(
        default=None,
        description="1-3 words; appended to passive_result mood suffix when applicable.",
    )
