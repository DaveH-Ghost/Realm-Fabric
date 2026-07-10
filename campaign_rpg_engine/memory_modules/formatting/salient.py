"""Salience scoring helpers for the salient_turns memory module."""

from __future__ import annotations

from campaign_rpg_engine.turn_record import StepKind, TurnStep

STEP_SALIENCE: dict[StepKind, int] = {
    "speak": 10,
    "emote": 10,
    "interact": 7,
    "look": 3,
    "move": 1,
}

WITNESS_SALIENCE = STEP_SALIENCE["speak"]


def step_salience(kind: StepKind) -> int:
    return STEP_SALIENCE.get(kind, 0)


def select_salient_steps(steps: list[TurnStep], *, in_recency_floor: bool) -> list[TurnStep]:
    """
    Pick which step results to include in a salient turn's Result line.

    Recency-floor turns keep all steps; older turns keep speak/interact only.
    """
    if in_recency_floor:
        return [step for step in steps if step.result.strip()]
    return [
        step
        for step in steps
        if step.result.strip() and step.kind in ("speak", "emote", "interact")
    ]
