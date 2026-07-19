"""
LLM structured output schemas — V0.2.5 single-call compound turns.

One AgentCompoundTurn per agent turn: optional move, then optional look, then turn action.
V0.4.1a: reasoning and speak content are truncated at sentence boundaries.
V0.4.4c: compact JSON keys (move, look, say, action, verb); legacy 0.4.3 keys normalized.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from campaign_rpg_engine.coordinates import CoordinateParseError
from campaign_rpg_engine.llm.text_truncation import (
    REASONING_MAX_CHARS,
    SPEAK_MAX_CHARS,
    count_sentences,
    truncate_at_sentence_boundary,
)
from campaign_rpg_engine.move_target import validate_move_target_syntax

TurnActionType = Literal["interact", "emote", "verb", "none"]

MAX_SPEAK_CHARACTERS = SPEAK_MAX_CHARS
MAX_REASONING_CHARACTERS = REASONING_MAX_CHARS

_LEGACY_KEY_MAP = {
    "move_target": "move",
    "look_target": "look",
    "content": "say",
    "turn_action": "action",
    "action_name": "verb",
}


def count_speak_sentences(text: str) -> int:
    """Count sentences; ellipsis runs are not sentence boundaries."""
    return count_sentences(text)


def _truncate_reasoning(v: str) -> str:
    return truncate_at_sentence_boundary(v, REASONING_MAX_CHARS)


def _truncate_say(v: str | None) -> str | None:
    if v is None:
        return v
    text = v.strip()
    if not text:
        return v
    return truncate_at_sentence_boundary(text, SPEAK_MAX_CHARS)


def normalize_compound_turn_payload(data: Any) -> Any:
    """Map legacy 0.4.3 JSON keys to V0.4.4 compact keys."""
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
    """Structured output for one compound agent turn (move → look → speak → action)."""

    reasoning: str = Field(
        description="Private thoughts for the full turn (~400 chars max).",
    )
    move: str | None = Field(
        default=None,
        description='Grid coordinate "x,y", entity id (obj_* / agent_*), or null to stay.',
    )
    look: str | None = Field(
        default=None,
        description="Entity id to examine after moving, or null to skip look.",
    )
    action: TurnActionType = Field(
        description='Turn-ending action: "interact", "emote", "verb", or "none".',
    )
    target: str | None = Field(
        default=None,
        description=(
            "Object or agent id (or free text) for interact; optional for emote "
            "(omit for undirected gestures) and verb."
        ),
    )
    verb: str | None = Field(
        default=None,
        description="Object action name (interact), past-tense emote verb (emote), or registered verb id (verb).",
    )
    say: str | None = Field(
        default=None,
        description="Optional speak dialogue (~500 chars max).",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keys(cls, data: Any) -> Any:
        data = normalize_compound_turn_payload(data)
        if isinstance(data, dict):
            action = data.get("action")
            if action == "speak":
                raise ValueError(
                    'ERR:INVALID_JSON: turn_action "speak" is removed; use say for dialogue'
                )
        return data

    @field_validator("reasoning")
    @classmethod
    def validate_reasoning(cls, v: str) -> str:
        return _truncate_reasoning(v)

    @field_validator("move")
    @classmethod
    def validate_move(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not str(v).strip():
            return None
        try:
            return validate_move_target_syntax(v)
        except CoordinateParseError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("say")
    @classmethod
    def validate_say(cls, v: str | None) -> str | None:
        return _truncate_say(v)

    @model_validator(mode="after")
    def validate_action_fields(self) -> AgentCompoundTurn:
        if self.action == "interact":
            if not self.target or not str(self.target).strip():
                raise ValueError("ERR:INVALID_TARGET: interact requires target object id")
            if not self.verb or not str(self.verb).strip():
                raise ValueError("ERR:INVALID_TARGET: interact requires verb")
        elif self.action == "emote":
            if not self.verb or not str(self.verb).strip():
                raise ValueError("ERR:INVALID_TARGET: emote requires verb")
            # target is optional — undirected emotes (nod, smile) omit it
        elif self.action == "verb":
            if not self.verb or not str(self.verb).strip():
                raise ValueError("ERR:INVALID_TARGET: verb action requires verb id")
            from campaign_rpg_engine.turn_verbs.registry import get_turn_verb_registration

            reg = get_turn_verb_registration(str(self.verb).strip())
            if reg is None:
                from campaign_rpg_engine.turn_verbs.registry import list_registered_turn_verbs

                known = ", ".join(list_registered_turn_verbs()) or "(none)"
                raise ValueError(
                    f"ERR:INVALID_TARGET: unknown turn verb {self.verb!r}. Known: {known}."
                )
            if reg.validate_turn is not None:
                err = reg.validate_turn(self)
                if err:
                    raise ValueError(err)
        elif self.action == "none":
            if self.target or self.verb:
                raise ValueError("ERR:INVALID_TARGET: target and verb must be empty for none")
        return self
