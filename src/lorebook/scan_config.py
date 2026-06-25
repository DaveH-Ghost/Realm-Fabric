"""Configurable lorebook keyword scan sources (V0.5.0)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

from src.agent import Agent
from src.area import Area


@dataclass
class LorebookScanConfig:
    """Which text sources are included when matching lorebook keywords."""

    agent_name: bool = True
    agent_personality: bool = True
    agent_description: bool = True
    area_description: bool = True
    memory: bool = True
    passive_vision: bool = True
    recent_events: bool = True

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> LorebookScanConfig:
        if not data:
            return cls()
        kwargs: dict[str, bool] = {}
        for field in fields(cls):
            if field.name in data:
                kwargs[field.name] = bool(data[field.name])
        return cls(**kwargs)


SCAN_SOURCE_META: tuple[dict[str, str], ...] = (
    {"id": "agent_name", "label": "Agent name"},
    {"id": "agent_personality", "label": "Agent personality"},
    {"id": "agent_description", "label": "Agent description"},
    {"id": "area_description", "label": "Area description"},
    {"id": "memory", "label": "Memory module text"},
    {"id": "passive_vision", "label": "Passive vision"},
    {"id": "recent_events", "label": "Recent area events"},
)


def _preview_text(text: str, *, limit: int = 220) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "(empty)"
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def describe_scan_sources(
    *,
    agent: Agent,
    area: Area,
    memory_text: str = "",
    passive_vision: str = "",
    scan_config: LorebookScanConfig | None = None,
) -> list[dict[str, Any]]:
    """Return catalog rows with enabled flag and preview for realm-studio."""
    cfg = scan_config or LorebookScanConfig()
    previews = {
        "agent_name": _preview_text(agent.name),
        "agent_personality": _preview_text(agent.personality),
        "agent_description": _preview_text(agent.description),
        "area_description": _preview_text(area.area_description),
        "memory": _preview_text(memory_text),
        "passive_vision": _preview_text(passive_vision),
        "recent_events": _preview_text(
            "\n".join(event.text for event in area.recent_events if event.text)
        ),
    }
    rows: list[dict[str, Any]] = []
    for meta in SCAN_SOURCE_META:
        source_id = meta["id"]
        rows.append(
            {
                "id": source_id,
                "label": meta["label"],
                "enabled": bool(getattr(cfg, source_id)),
                "preview": previews[source_id],
            }
        )
    return rows
