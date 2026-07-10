"""JSON-friendly serialization for memory module state (V0.4.5)."""

from __future__ import annotations

from typing import Any

from campaign_rpg_engine.memory_modules.base import WitnessedEvent
from campaign_rpg_engine.turn_record import TurnRecord, TurnStep


def serialize_turn_step(step: TurnStep) -> dict[str, Any]:
    data: dict[str, Any] = {
        "kind": step.kind,
        "reasoning": step.reasoning,
        "result": step.result,
        "passive_result": step.passive_result,
    }
    if step.target is not None:
        data["target"] = step.target
    if step.content is not None:
        data["content"] = step.content
    return data


def deserialize_turn_step(data: dict[str, Any]) -> TurnStep:
    return TurnStep(
        kind=data["kind"],
        reasoning=data.get("reasoning", ""),
        target=data.get("target"),
        content=data.get("content"),
        result=data.get("result", ""),
        passive_result=data.get("passive_result", ""),
    )


def serialize_turn_record(record: TurnRecord) -> dict[str, Any]:
    return {
        "turn_number": record.turn_number,
        "steps": [serialize_turn_step(step) for step in record.steps],
        "result": record.result,
        "reasoning": record.reasoning,
    }


def deserialize_turn_record(data: dict[str, Any]) -> TurnRecord:
    return TurnRecord(
        turn_number=int(data["turn_number"]),
        steps=[deserialize_turn_step(step) for step in data.get("steps", [])],
        result=data.get("result", ""),
        reasoning=data.get("reasoning", ""),
    )


def serialize_witnessed_event(event: WitnessedEvent) -> dict[str, Any]:
    x, y = event.actor_position
    return {
        "session_turn": event.session_turn,
        "actor_id": event.actor_id,
        "actor_name": event.actor_name,
        "text": event.text,
        "actor_position": [x, y],
    }


def deserialize_witnessed_event(data: dict[str, Any]) -> WitnessedEvent:
    pos = data["actor_position"]
    return WitnessedEvent(
        session_turn=int(data["session_turn"]),
        actor_id=data["actor_id"],
        actor_name=data["actor_name"],
        text=data["text"],
        actor_position=(int(pos[0]), int(pos[1])),
    )


def serialize_turn_list(turns: list[TurnRecord]) -> list[dict[str, Any]]:
    return [serialize_turn_record(record) for record in turns]


def deserialize_turn_list(items: list[dict[str, Any]]) -> list[TurnRecord]:
    return [deserialize_turn_record(item) for item in items]


def serialize_witness_list(events: list[WitnessedEvent]) -> list[dict[str, Any]]:
    return [serialize_witnessed_event(event) for event in events]


def deserialize_witness_list(items: list[dict[str, Any]]) -> list[WitnessedEvent]:
    return [deserialize_witnessed_event(item) for item in items]


def serialize_witnessed_before(
    batches: list[list[WitnessedEvent]],
) -> list[list[dict[str, Any]]]:
    return [serialize_witness_list(batch) for batch in batches]


def deserialize_witnessed_before(
    items: list[list[dict[str, Any]]],
) -> list[list[WitnessedEvent]]:
    return [deserialize_witness_list(batch) for batch in items]
