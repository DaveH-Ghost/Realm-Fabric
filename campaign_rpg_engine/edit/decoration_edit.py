"""Typed decoration CRUD helpers for area editing (V1.3.0)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from campaign_rpg_engine.decoration import (
    DECORATION_KIND_BACKGROUND,
    DECORATION_KIND_SPRITE,
    DEFAULT_BACKGROUND_Z_INDEX,
    VALID_DECORATION_KINDS,
    VALID_REPEAT_VALUES,
    Decoration,
)
from campaign_rpg_engine.edit.field_appliers import slugify_display_name

if TYPE_CHECKING:
    from campaign_rpg_engine.area import Area


@dataclass(frozen=True)
class DecorationMutationResult:
    """Outcome of typed decoration methods on ``Session``."""

    ok: bool
    message: str
    decoration: Decoration | None = None
    area_id: str | None = None


def generate_decoration_id(area: Area, display_name: str = "decor") -> str:
    """Auto-generate a unique decoration id."""
    slug = slugify_display_name(display_name)
    existing = {dec.id for dec in area.decorations}
    counter = 1
    while True:
        candidate = f"decor_{slug}_{counter:02d}"
        if candidate not in existing:
            return candidate
        counter += 1


def label_from_image_path(image: str) -> str:
    """Filename stem from an image path (no directory or extension)."""
    cleaned = image.strip().replace("\\", "/")
    stem = Path(cleaned).name
    stem = Path(stem).stem
    slug = slugify_display_name(stem)
    return slug or "decor"


def _decoration_id_label(image: str, label: str) -> str:
    custom = label.strip()
    if custom and custom.lower() != "decor":
        return custom
    return label_from_image_path(image)


def _validate_image(image: str) -> str | None:
    cleaned = image.strip()
    if not cleaned:
        return "Decoration image path cannot be empty."
    return None


def _validate_kind(kind: str) -> str | None:
    cleaned = kind.strip().lower()
    if cleaned not in VALID_DECORATION_KINDS:
        return (
            f"Invalid decoration kind {kind!r}. "
            f"Use {DECORATION_KIND_SPRITE!r} or {DECORATION_KIND_BACKGROUND!r}."
        )
    return None


def _next_sprite_z_index(area: Area) -> int:
    sprites = [d for d in area.decorations if d.kind == DECORATION_KIND_SPRITE]
    if not sprites:
        return 0
    return max(d.z_index for d in sprites) + 1


def _remove_background_decorations(area: Area) -> None:
    area.decorations[:] = [d for d in area.decorations if d.kind != DECORATION_KIND_BACKGROUND]


def add_decoration_to_area(
    area: Area,
    *,
    kind: str,
    image: str,
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
    z_index: int | None = None,
    repeat: str = "repeat",
    decoration_id: str | None = None,
    label: str = "decor",
) -> tuple[Decoration | None, str]:
    """Add a decoration to an area. Replaces any existing background decoration."""
    kind_err = _validate_kind(kind)
    if kind_err:
        return None, kind_err
    normalized_kind = kind.strip().lower()

    image_err = _validate_image(image)
    if image_err:
        return None, image_err

    repeat_clean = repeat.strip().lower() or "repeat"
    if repeat_clean not in VALID_REPEAT_VALUES:
        return (
            None,
            f"Invalid repeat {repeat!r}. Use one of: {', '.join(sorted(VALID_REPEAT_VALUES))}.",
        )

    if normalized_kind == DECORATION_KIND_BACKGROUND:
        _remove_background_decorations(area)
        dec_id = decoration_id or generate_decoration_id(area, _decoration_id_label(image, label))
        decoration = Decoration(
            id=dec_id,
            kind=normalized_kind,
            image=image.strip(),
            width=max(0, width),
            height=max(0, height),
            z_index=z_index if z_index is not None else DEFAULT_BACKGROUND_Z_INDEX,
            repeat=repeat_clean,
        )
        area.decorations.append(decoration)
        return decoration, f"Added background decoration {dec_id}."

    if width < 1 or height < 1:
        return None, "Sprite decorations require width and height of at least 1."

    dec_id = decoration_id or generate_decoration_id(area, _decoration_id_label(image, label))
    if area.get_decoration_by_id(dec_id) is not None:
        return None, f"Decoration id {dec_id!r} already exists in this area."

    resolved_z = z_index if z_index is not None else _next_sprite_z_index(area)
    decoration = Decoration(
        id=dec_id,
        kind=normalized_kind,
        image=image.strip(),
        x=x,
        y=y,
        width=width,
        height=height,
        z_index=resolved_z,
    )
    area.decorations.append(decoration)
    return decoration, f"Added sprite decoration {dec_id}."


def update_decoration_in_area(
    area: Area,
    decoration_id: str,
    *,
    image: str | None = None,
    x: int | None = None,
    y: int | None = None,
    width: int | None = None,
    height: int | None = None,
    z_index: int | None = None,
    repeat: str | None = None,
) -> tuple[Decoration | None, str]:
    """Update fields on an existing decoration."""
    decoration = area.get_decoration_by_id(decoration_id)
    if decoration is None:
        return None, f"Decoration {decoration_id!r} not found."

    changes: list[str] = []

    if image is not None:
        image_err = _validate_image(image)
        if image_err:
            return None, image_err
        decoration.image = image.strip()
        changes.append("image")

    if decoration.kind == DECORATION_KIND_SPRITE:
        if x is not None:
            decoration.x = x
            changes.append("x")
        if y is not None:
            decoration.y = y
            changes.append("y")
        if width is not None:
            if width < 1:
                return None, "Sprite width must be at least 1."
            decoration.width = width
            changes.append("width")
        if height is not None:
            if height < 1:
                return None, "Sprite height must be at least 1."
            decoration.height = height
            changes.append("height")
        if z_index is not None:
            decoration.z_index = z_index
            changes.append("z_index")
    else:
        if repeat is not None:
            repeat_clean = repeat.strip().lower() or "repeat"
            if repeat_clean not in VALID_REPEAT_VALUES:
                return (
                    None,
                    f"Invalid repeat {repeat!r}. "
                    f"Use one of: {', '.join(sorted(VALID_REPEAT_VALUES))}.",
                )
            decoration.repeat = repeat_clean
            changes.append("repeat")
        if width is not None:
            if width < 0:
                return None, "Background tile width cannot be negative."
            decoration.width = width
            changes.append("width")
        if height is not None:
            if height < 0:
                return None, "Background tile height cannot be negative."
            decoration.height = height
            changes.append("height")
        if z_index is not None:
            decoration.z_index = z_index
            changes.append("z_index")

    if not changes:
        return None, f"No changes applied to {decoration_id}."

    return decoration, f"Updated decoration {decoration_id} ({', '.join(changes)})."


def remove_decoration_from_area(area: Area, decoration_id: str) -> tuple[bool, str]:
    removed = area.remove_decoration_by_id(decoration_id)
    if removed is None:
        return False, f"Decoration {decoration_id!r} not found."
    return True, f"Removed decoration {decoration_id}."


def reorder_decoration_in_area(
    area: Area,
    decoration_id: str,
    direction: Literal["up", "down"],
) -> tuple[bool, str]:
    """Move a sprite decoration up or down in the z-order."""
    decoration = area.get_decoration_by_id(decoration_id)
    if decoration is None:
        return False, f"Decoration {decoration_id!r} not found."
    if decoration.kind == DECORATION_KIND_BACKGROUND:
        return False, "Background decorations are always rendered behind the grid."

    sprites = sorted(
        [d for d in area.decorations if d.kind == DECORATION_KIND_SPRITE],
        key=lambda d: (d.z_index, d.id),
    )
    index = next((i for i, d in enumerate(sprites) if d.id == decoration_id), None)
    if index is None:
        return False, f"Decoration {decoration_id!r} not found."

    if direction == "up":
        if index >= len(sprites) - 1:
            return False, f"{decoration_id} is already at the top."
        other = sprites[index + 1]
        decoration.z_index, other.z_index = other.z_index, decoration.z_index
        if decoration.z_index == other.z_index:
            decoration.z_index += 1
    elif direction == "down":
        if index <= 0:
            return False, f"{decoration_id} is already at the bottom."
        other = sprites[index - 1]
        decoration.z_index, other.z_index = other.z_index, decoration.z_index
        if decoration.z_index == other.z_index:
            decoration.z_index -= 1
    else:
        return False, f"Invalid direction {direction!r}."

    return True, f"Moved {decoration_id} {direction}."
