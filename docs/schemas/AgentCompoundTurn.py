"""
AgentCompoundTurn — current LLM turn schema (V0.2.5+)

AUTHORITATIVE RUNTIME:
    src/llm/schemas.py

APP IMPORT:
    from realm_fabric import AgentCompoundTurn

This file is a readable design reference for documentation and review.
Validators here are simplified; runtime adds move-target parsing, truncation,
and legacy key normalization.

One compound turn per agent: optional move → optional look → optional say →
turn-ending action (interact | emote | none).

Last synced: 2026-06-21 (V0.7.0 docs pass)
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

TurnActionType = Literal["interact", "emote", "none"]

# Runtime uses sentence-boundary truncation (V0.4.1a), not hard limits in all cases.
REASONING_MAX_CHARS = 400
SPEAK_MAX_CHARS = 500

_LEGACY_KEY_MAP = {
    "move_target": "move",
    "look_target": "look",
    "content": "say",
    "turn_action": "action",
    "action_name": "verb",
}


def normalize_compound_turn_payload(data: Any) -> Any:
    """Map legacy 0.4.3 JSON keys to compact keys (runtime: src/llm/schemas.py)."""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    for legacy, compact in _LEGACY_KEY_MAP.items():
        if legacy in out and compact not in out:
            out[compact] = out.pop(legacy)
        elif legacy in out:
            out.pop(legacy)
    return out


class AgentCompoundTurn(BaseModel):
    """Structured output for one compound agent turn."""

    reasoning: str = Field(
        description="Private thoughts for the full turn (~400 chars max).",
    )
    move: Optional[str] = Field(
        default=None,
        description='Grid coordinate "x,y", entity id (obj_* / agent_*), or null to stay.',
    )
    look: Optional[str] = Field(
        default=None,
        description="Entity id to examine after moving, or null to skip look.",
    )
    action: TurnActionType = Field(
        description='Turn-ending action: "interact", "emote", or "none".',
    )
    target: Optional[str] = Field(
        default=None,
        description="Object or agent id (or free text) when action is interact or emote.",
    )
    verb: Optional[str] = Field(
        default=None,
        description='Object action name (interact) or past-tense emote verb (emote).',
    )
    say: Optional[str] = Field(
        default=None,
        description="Optional speak dialogue (~500 chars max). Witnessed by nearby agents.",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keys(cls, data: Any) -> Any:
        data = normalize_compound_turn_payload(data)
        if isinstance(data, dict) and data.get("action") == "speak":
            raise ValueError(
                'ERR:INVALID_JSON: action "speak" is removed; use say for dialogue'
            )
        return data

    @field_validator("reasoning")
    @classmethod
    def validate_reasoning(cls, v: str) -> str:
        if len(v) > REASONING_MAX_CHARS:
            # Runtime truncates at sentence boundary instead of raising.
            pass
        return v

    @field_validator("say")
    @classmethod
    def validate_say(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > SPEAK_MAX_CHARS:
            # Runtime truncates at sentence boundary instead of raising.
            pass
        return v

    @model_validator(mode="after")
    def validate_action_fields(self) -> AgentCompoundTurn:
        if self.action == "interact":
            if not self.target or not str(self.target).strip():
                raise ValueError("ERR:INVALID_TARGET: interact requires target")
            if not self.verb or not str(self.verb).strip():
                raise ValueError("ERR:INVALID_TARGET: interact requires verb")
        elif self.action == "emote":
            if not self.target or not str(self.target).strip():
                raise ValueError("ERR:INVALID_TARGET: emote requires target")
            if not self.verb or not str(self.verb).strip():
                raise ValueError("ERR:INVALID_TARGET: emote requires verb")
        elif self.action == "none":
            if self.target or self.verb:
                raise ValueError(
                    "ERR:INVALID_TARGET: target and verb must be empty for none"
                )
        return self
