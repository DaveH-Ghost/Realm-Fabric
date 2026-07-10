"""Lorebook data models (V0.5.0)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from campaign_rpg_engine.lorebook.st_defaults import with_st_entry_defaults

DEFAULT_LOREBOOK_CHAR_BUDGET = 4000


@dataclass
class LoreEntry:
    uid: int
    enabled: bool = True
    constant: bool = False
    keys: list[str] = field(default_factory=list)
    keys_secondary: list[str] = field(default_factory=list)
    selective: bool = False
    selective_logic: int = 0
    content: str = ""
    comment: str = ""
    order: int = 0
    ignore_budget: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize one entry for ST export and session snapshots."""
        data = dict(self.raw)
        data.pop("enabled", None)
        data.update(
            {
                "uid": self.uid,
                "disable": not self.enabled,
                "constant": self.constant,
                "key": list(self.keys),
                "keysecondary": list(self.keys_secondary),
                "selective": self.selective,
                "selectiveLogic": self.selective_logic,
                "content": self.content,
                "comment": self.comment,
                "order": self.order,
                "ignoreBudget": self.ignore_budget,
            }
        )
        if "displayIndex" not in data:
            data["displayIndex"] = self.uid
        return with_st_entry_defaults(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoreEntry:
        raw = dict(data)
        raw.pop("enabled", None)
        keys = data.get("key") or data.get("keys") or []
        keys_secondary = data.get("keysecondary") or data.get("keys_secondary") or []
        if not isinstance(keys, list):
            keys = [str(keys)]
        if not isinstance(keys_secondary, list):
            keys_secondary = [str(keys_secondary)]
        disable = bool(data.get("disable", False))
        return cls(
            uid=int(data.get("uid", 0)),
            enabled=not disable,
            constant=bool(data.get("constant", False)),
            keys=[str(k) for k in keys],
            keys_secondary=[str(k) for k in keys_secondary],
            selective=bool(data.get("selective", False)),
            selective_logic=int(data.get("selectiveLogic", data.get("selective_logic", 0))),
            content=str(data.get("content", "")),
            comment=str(data.get("comment", "")),
            order=int(data.get("order", 0)),
            ignore_budget=bool(data.get("ignoreBudget", data.get("ignore_budget", False))),
            raw=raw,
        )


@dataclass
class Lorebook:
    id: str
    name: str
    source_filename: str = ""
    entries: list[LoreEntry] = field(default_factory=list)

    def sorted_entries(self) -> list[LoreEntry]:
        return sorted(self.entries, key=lambda entry: (entry.order, entry.uid))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source_filename": self.source_filename,
            "entries": [entry.to_dict() for entry in self.sorted_entries()],
        }

    def to_st_export_dict(self) -> dict[str, Any]:
        """SillyTavern load format: ``entries`` map keyed by uid string."""
        return {
            "entries": {
                str(entry.uid): entry.to_dict() for entry in self.sorted_entries()
            }
        }

    def export_filename(self) -> str:
        if self.source_filename:
            return self.source_filename
        return f"{self.id}.lorebook.json"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Lorebook:
        entries_raw = data.get("entries")
        if isinstance(entries_raw, dict):
            entries = [LoreEntry.from_dict(item) for item in entries_raw.values()]
        elif isinstance(entries_raw, list):
            entries = [LoreEntry.from_dict(item) for item in entries_raw]
        else:
            entries = []
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            source_filename=str(data.get("source_filename", "")),
            entries=entries,
        )
