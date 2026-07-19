"""Import SillyTavern-style lorebook JSON (V0.5.0)."""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import Any

from campaign_rpg_engine.lorebook.models import Lorebook, LoreEntry

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def derive_lorebook_id_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    for suffix in (".lorebook", "_lorebook", "-lorebook"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    slug = _SLUG_RE.sub("-", stem.lower()).strip("-")
    return slug or "lorebook"


def _parse_st_entries(data: dict[str, Any]) -> list[LoreEntry]:
    entries_raw = data.get("entries")
    if not isinstance(entries_raw, dict):
        raise ValueError("SillyTavern lorebook must have an 'entries' object.")
    entries: list[LoreEntry] = []
    for key, item in entries_raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"Entry {key!r} must be an object.")
        entry = LoreEntry.from_dict(item)
        if "uid" not in item:
            with contextlib.suppress(ValueError):
                entry.uid = int(key)
        entries.append(entry)
    return entries


def load_lorebook_from_dict(
    data: dict[str, Any],
    *,
    filename: str = "",
    book_id: str | None = None,
) -> Lorebook:
    entries = _parse_st_entries(data)
    resolved_id = book_id or derive_lorebook_id_from_filename(filename or "lorebook.json")
    display_name = Path(filename).stem if filename else resolved_id.replace("-", " ").title()
    return Lorebook(
        id=resolved_id,
        name=display_name,
        source_filename=filename,
        entries=entries,
    )


def load_lorebook_from_path(path: str | Path) -> Lorebook:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"Lorebook path is not a file: {resolved}")
    text = resolved.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid lorebook JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Lorebook JSON root must be an object.")
    return load_lorebook_from_dict(data, filename=resolved.name)
