"""Process-wide turn verb registry (1.2.0)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from campaign_rpg_engine.action_outcome import ActionOutcome

if TYPE_CHECKING:
    from campaign_rpg_engine.agent import Agent
    from campaign_rpg_engine.area import Area
    from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
    from campaign_rpg_engine.session import Session

TurnVerbExecutor = Callable[
    ["Session", "Agent", "Area", "AgentCompoundTurn"],
    ActionOutcome | str | None,
]
ValidateTurnVerb = Callable[["AgentCompoundTurn"], str | None]
VerbPathTarget = Callable[["AgentCompoundTurn"], str | None]


@dataclass(frozen=True)
class TurnVerbRegistration:
    executor: TurnVerbExecutor
    description: str = ""
    validate_turn: ValidateTurnVerb | None = None
    path_range: int | None = None
    """When set, path toward :attr:`path_target_from_turn` before running the verb."""
    path_target_from_turn: VerbPathTarget | None = None
    """Return an in-area ``agent_*`` id to approach, or None to skip pathing."""


_REGISTRY: dict[str, TurnVerbRegistration] = {}


def register_turn_verb(
    verb_id: str,
    executor: TurnVerbExecutor,
    *,
    description: str = "",
    validate_turn: ValidateTurnVerb | None = None,
    path_range: int | None = None,
    path_target_from_turn: VerbPathTarget | None = None,
) -> None:
    cleaned = verb_id.strip()
    if not cleaned:
        raise ValueError("verb_id must not be empty")
    if (path_range is None) != (path_target_from_turn is None):
        raise ValueError("path_range and path_target_from_turn must both be set or both omitted")
    if path_range is not None and path_range < 0:
        raise ValueError("path_range must be non-negative")
    _REGISTRY[cleaned] = TurnVerbRegistration(
        executor=executor,
        description=description,
        validate_turn=validate_turn,
        path_range=path_range,
        path_target_from_turn=path_target_from_turn,
    )


def list_registered_turn_verbs() -> list[str]:
    return sorted(_REGISTRY)


def get_turn_verb_registration(verb_id: str) -> TurnVerbRegistration | None:
    return _REGISTRY.get(verb_id)


def run_turn_verb(
    session: Session | None,
    agent: Agent,
    area: Area,
    turn: AgentCompoundTurn,
) -> ActionOutcome | str:
    """Dispatch a registered turn verb. Returns ActionOutcome or error message."""
    verb_id = (turn.verb or "").strip()
    if not verb_id:
        return "ERR:INVALID_TARGET: verb action requires verb id"
    reg = _REGISTRY.get(verb_id)
    if reg is None:
        known = ", ".join(list_registered_turn_verbs()) or "(none)"
        return f"Unknown turn verb '{verb_id}'. Known verbs: {known}."
    if reg.validate_turn is not None:
        err = reg.validate_turn(turn)
        if err:
            return err
    result = reg.executor(session, agent, area, turn)
    if isinstance(result, str):
        return result
    if result is None:
        return ActionOutcome(result="You completed the action.", passive_result="")
    return result


def format_turn_verbs_list() -> str:
    lines = ["Registered turn verbs:"]
    if not _REGISTRY:
        lines.append("  (none)")
    else:
        for verb_id in sorted(_REGISTRY):
            reg = _REGISTRY[verb_id]
            suffix = f": {reg.description}" if reg.description else ""
            lines.append(f"  - {verb_id}{suffix}")
    return "\n".join(lines)


def clear_turn_verbs_for_tests() -> None:
    _REGISTRY.clear()
