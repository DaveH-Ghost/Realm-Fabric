"""Create empty session lorebooks (V0.5.0)."""

from __future__ import annotations

from collections.abc import Iterable

from campaign_rpg_engine.lorebook.import_st import derive_lorebook_id_from_filename
from campaign_rpg_engine.lorebook.models import Lorebook


def allocate_lorebook_id(existing_ids: Iterable[str], base: str) -> str:
    """Return a slug id from *base* that is not already in *existing_ids*."""
    taken = set(existing_ids)
    candidate = derive_lorebook_id_from_filename(f"{base}.lorebook.json")
    if candidate not in taken:
        return candidate
    for index in range(2, 10_000):
        numbered = f"{candidate}-{index}"
        if numbered not in taken:
            return numbered
    raise ValueError(f"Could not allocate a unique lorebook id for {base!r}.")


def create_empty_lorebook(
    *,
    name: str = "New lorebook",
    existing_ids: Iterable[str] = (),
) -> Lorebook:
    """Build an empty lorebook ready for session storage and studio editing."""
    display_name = (name or "New lorebook").strip() or "New lorebook"
    resolved_id = allocate_lorebook_id(existing_ids, display_name)
    return Lorebook(
        id=resolved_id,
        name=display_name,
        source_filename=f"{resolved_id}.lorebook.json",
        entries=[],
    )
