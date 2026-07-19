"""Declarative object interaction definitions for V0.2 / V0.6.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ActionKind = Literal["interact", "trigger"]


def migrate_legacy_effects_to_handler(
    effects: list[dict[str, Any]],
) -> tuple[str | None, dict[str, str]]:
    """Convert v3 ``effects`` array to handler fields (first effect only)."""
    if not effects:
        return None, {}
    first = effects[0]
    handler_id = str(first.get("name", "")).strip() or None
    params = {str(k): str(v) for k, v in dict(first.get("params", {})).items()}
    return handler_id, params


@dataclass
class ObjectAction:
    """One named interaction or trigger on an object."""

    name: str
    range: int
    result: str
    passive_result: str
    handler_id: str | None = None
    handler_params: dict[str, str] = field(default_factory=dict)
    kind: ActionKind = "interact"
    """``interact`` — LLM compound-turn action; ``trigger`` — engine path step."""

    halt_movement: bool = False
    """When ``kind`` is ``trigger``, stop the mover on the firing tile."""

    delete_after_trigger: bool = True
    """When ``kind`` is ``trigger``, remove the object after it fires."""

    trigger_exceptions: list[str] = field(default_factory=list)
    """Agent ids that do not fire this trigger."""

    enabled: bool = True
    """When False, the action is hidden from vision and cannot be used or fire."""
