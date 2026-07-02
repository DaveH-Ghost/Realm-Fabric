"""
AgentActionTurn — HISTORICAL (V0.2 two-phase turns)

!!! SUPERSEDED by AgentCompoundTurn (V0.2.5+) !!!

Authoritative current schema: [AgentCompoundTurn.py](AgentCompoundTurn.py) /
`src/llm/schemas.py`.

This file documented the **action phase** (look / speak / interact) of the
two-call turn model. `turn_action: "speak"` and separate `content` field are
obsolete — use `say` and `action: "interact" | "emote" | "none"` on
`AgentCompoundTurn`.

See [schemas/README.md](README.md).

Last synced: 2026-06-05 (historical)
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
