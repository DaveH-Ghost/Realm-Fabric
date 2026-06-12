"""
object_effects.py

Central registry for declarative object interaction effects (V0.2 Section 3).
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.agent import Agent
    from src.object import Object
    from src.area import Area

EffectHandler = Callable[["Area", "Agent", "Object"], None]


def _delete_self(area: Area, _agent: Agent, obj: Object) -> None:
    area.remove_object(obj.id)


def _random_move_self(area: Area, _agent: Agent, obj: Object) -> None:
    positions = [
        (x, y)
        for x in range(area.min_x, area.max_x + 1)
        for y in range(area.min_y, area.max_y + 1)
        if (x, y) != obj.position
    ]
    if not positions:
        return
    obj.position = random.choice(positions)


_REGISTRY: dict[str, tuple[str, EffectHandler]] = {
    "delete_self": (
        "Remove the interacted object from the area",
        _delete_self,
    ),
    "random_move_self": (
        "Move the interacted object to a different random in-bounds grid position",
        _random_move_self,
    ),
}

EFFECT_DESCRIPTIONS: dict[str, str] = {
    name: description for name, (description, _handler) in _REGISTRY.items()
}

_EFFECT_HANDLERS: dict[str, EffectHandler] = {
    name: handler for name, (_description, handler) in _REGISTRY.items()
}


def known_effect_names() -> frozenset[str]:
    """Return all registered effect keys."""
    return frozenset(_REGISTRY)


def validate_effect_name(name: str) -> str | None:
    """Return an error message if the effect name is unknown."""
    if name not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY))
        return f"Unknown effect '{name}'. Known effects: {known}."
    return None


def apply_effects(
    area: Area, agent: Agent, obj: Object, effect_names: list[str]
) -> None:
    """Run registered effects in order."""
    for name in effect_names:
        handler = _EFFECT_HANDLERS[name]
        handler(area, agent, obj)


def format_effects_list() -> str:
    """Format the read-only effects listing for the stepper."""
    lines = ["Registered object effects:"]
    if not _REGISTRY:
        lines.append("  (none)")
    else:
        for name in sorted(_REGISTRY):
            lines.append(f"  - {name}: {EFFECT_DESCRIPTIONS[name]}")
    return "\n".join(lines)
