"""Process-wide prompt slot contributor registry (1.2.0)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from campaign_rpg_engine.agent import Agent
    from campaign_rpg_engine.area import Area
    from campaign_rpg_engine.llm.prompt_context import PromptContext
    from campaign_rpg_engine.session import Session

PromptSlotRenderer = Callable[
    ["Session", "Agent", "Area", "PromptContext", dict[str, Any]],
    str,
]


@dataclass(frozen=True)
class PromptSlotRegistration:
    renderer: PromptSlotRenderer
    description: str = ""


_REGISTRY: dict[str, PromptSlotRegistration] = {}


def register_prompt_slot(
    name: str,
    renderer: PromptSlotRenderer,
    *,
    description: str = "",
) -> None:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("prompt slot name must not be empty")
    _REGISTRY[cleaned] = PromptSlotRegistration(
        renderer=renderer,
        description=description,
    )


def is_prompt_slot_registered(name: str) -> bool:
    return name in _REGISTRY


def get_prompt_slot_registration(name: str) -> PromptSlotRegistration | None:
    return _REGISTRY.get(name)


def list_registered_prompt_slots() -> list[str]:
    return sorted(_REGISTRY)


def render_registered_prompt_slot(
    name: str,
    *,
    session: Session,
    agent: Agent,
    area: Area,
    ctx: PromptContext,
    options: dict[str, Any] | None = None,
) -> str:
    reg = _REGISTRY.get(name)
    if reg is None:
        return ""
    return reg.renderer(session, agent, area, ctx, dict(options or {}))


def clear_prompt_slots_for_tests() -> None:
    _REGISTRY.clear()
