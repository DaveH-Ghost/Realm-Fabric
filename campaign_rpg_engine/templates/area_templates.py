"""Area templates — portable whole-area blueprints with layout (1.3.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from campaign_rpg_engine.area import GridBounds
from campaign_rpg_engine.decoration import DECORATION_KIND_BACKGROUND, DECORATION_KIND_SPRITE
from campaign_rpg_engine.edit.decoration_edit import add_decoration_to_area
from campaign_rpg_engine.edit.session_area_edit import (
    create_area_in_session,
    edit_area_in_session,
    validate_area_id,
)
from campaign_rpg_engine.edit.world_edit_api import delete_object_in_session
from campaign_rpg_engine.snapshot import serialize_decoration
from campaign_rpg_engine.templates.entity_templates import (
    TEMPLATE_VERSION,
    export_object_template,
    spawn_object_from_template,
    validate_template,
    validate_template_handlers,
)

if TYPE_CHECKING:
    from campaign_rpg_engine.session import Session


@dataclass(frozen=True)
class AreaTemplateMutationResult:
    """Outcome of ``spawn_area_from_template``."""

    ok: bool
    message: str
    area_id: str | None = None


def export_decoration_template(decoration: Any) -> dict[str, Any]:
    """Export a portable decoration entry (no id)."""
    data = serialize_decoration(decoration)
    data.pop("id", None)
    return data


def export_area_template(
    session: Session,
    area_id: str,
    *,
    name: str | None = None,
    include_hidden_objects: bool = True,
) -> dict[str, Any]:
    """Export a portable area template from a live area (objects and decorations only)."""
    cleaned = area_id.strip()
    area = session.areas.get(cleaned)
    if area is None:
        raise ValueError(f"Unknown area {cleaned!r}.")

    display_name = (name or cleaned).strip() or cleaned
    objects: list[dict[str, Any]] = []
    for obj in area.get_objects():
        if not include_hidden_objects and obj.hidden:
            continue
        entry = export_object_template(obj)
        entry["position"] = [obj.position[0], obj.position[1]]
        objects.append(entry)

    return {
        "template_version": TEMPLATE_VERSION,
        "kind": "area",
        "name": display_name,
        "area_description": area.area_description,
        "grid": {
            "min_x": area.bounds.min_x,
            "min_y": area.bounds.min_y,
            "max_x": area.bounds.max_x,
            "max_y": area.bounds.max_y,
        },
        "include_hidden_objects": include_hidden_objects,
        "decorations": [export_decoration_template(d) for d in area.decorations],
        "objects": objects,
    }


def validate_area_template(data: dict[str, Any]) -> str | None:
    """Return an error message if *data* is not a valid area template document."""
    if not isinstance(data, dict):
        return "Template must be a JSON object."
    version = data.get("template_version")
    if version != TEMPLATE_VERSION:
        return f"Unsupported template_version {version!r} (expected {TEMPLATE_VERSION})."
    if data.get("kind") != "area":
        return "Template kind must be 'area'."
    if not str(data.get("name", "")).strip():
        return "Template name is required."

    grid = data.get("grid")
    if not isinstance(grid, dict):
        return "Area template requires a grid object."
    try:
        _grid_bounds_from_template(data)
    except (KeyError, TypeError, ValueError) as exc:
        return str(exc)

    decorations = data.get("decorations")
    if decorations is not None and not isinstance(decorations, list):
        return "decorations must be a list."

    for index, decoration in enumerate(decorations or []):
        err = _validate_decoration_entry(decoration, index=index)
        if err:
            return err

    objects = data.get("objects")
    if objects is not None and not isinstance(objects, list):
        return "objects must be a list."
    for index, entry in enumerate(objects or []):
        err = _validate_placed_entity_entry(entry, expected_kind="object", index=index)
        if err:
            return err

    return None


def _grid_bounds_from_template(template: dict[str, Any]) -> GridBounds:
    grid = template["grid"]
    return GridBounds(
        min_x=int(grid["min_x"]),
        min_y=int(grid["min_y"]),
        max_x=int(grid["max_x"]),
        max_y=int(grid["max_y"]),
    )


def _validate_decoration_entry(data: Any, *, index: int) -> str | None:
    if not isinstance(data, dict):
        return f"decorations[{index}] must be an object."
    kind = data.get("kind")
    if kind not in (DECORATION_KIND_SPRITE, DECORATION_KIND_BACKGROUND):
        return (
            f"decorations[{index}] kind must be "
            f"{DECORATION_KIND_SPRITE!r} or {DECORATION_KIND_BACKGROUND!r}."
        )
    if not str(data.get("image", "")).strip():
        return f"decorations[{index}] image is required."
    if kind == DECORATION_KIND_SPRITE:
        width = data.get("width")
        height = data.get("height")
        if not isinstance(width, int) or width < 1:
            return f"decorations[{index}] sprite width must be at least 1."
        if not isinstance(height, int) or height < 1:
            return f"decorations[{index}] sprite height must be at least 1."
    return None


def _validate_placed_entity_entry(
    data: Any,
    *,
    expected_kind: str,
    index: int,
) -> str | None:
    if not isinstance(data, dict):
        return f"{expected_kind}s[{index}] must be an object."
    err = validate_template(data)
    if err:
        return f"{expected_kind}s[{index}]: {err}"
    if data.get("kind") != expected_kind:
        return f"{expected_kind}s[{index}] kind must be {expected_kind!r}."
    position = data.get("position")
    if not isinstance(position, (list, tuple)) or len(position) != 2:
        return f"{expected_kind}s[{index}] position must be [x, y]."
    try:
        int(position[0])
        int(position[1])
    except (TypeError, ValueError):
        return f"{expected_kind}s[{index}] position must contain integers."
    return None


def _clear_area_for_replace(session: Session, area_id: str) -> str | None:
    """Remove objects and decorations from an area; agents are left unchanged."""
    area = session.areas.get(area_id)
    if area is None:
        return f"Unknown area {area_id!r}."

    for obj in list(area.get_objects()):
        ok, message = delete_object_in_session(session, obj.id)
        if not ok:
            return message

    area.decorations.clear()
    area.recent_events.clear()
    return None


def _apply_area_metadata(
    session: Session,
    area_id: str,
    template: dict[str, Any],
) -> str | None:
    bounds = _grid_bounds_from_template(template)
    edited = edit_area_in_session(
        session,
        area_id,
        description=str(template.get("area_description", "")),
        min_x=bounds.min_x,
        min_y=bounds.min_y,
        max_x=bounds.max_x,
        max_y=bounds.max_y,
    )
    if not edited.ok:
        return edited.message
    return None


def _spawn_decorations_from_template(
    session: Session,
    area_id: str,
    template: dict[str, Any],
) -> str | None:
    area = session.areas.get(area_id)
    if area is None:
        return f"Unknown area {area_id!r}."

    backgrounds = [
        d
        for d in template.get("decorations", [])
        if isinstance(d, dict) and d.get("kind") == DECORATION_KIND_BACKGROUND
    ]
    sprites = [
        d
        for d in template.get("decorations", [])
        if isinstance(d, dict) and d.get("kind") == DECORATION_KIND_SPRITE
    ]

    for entry in backgrounds:
        decoration, message = add_decoration_to_area(
            area,
            kind=DECORATION_KIND_BACKGROUND,
            image=str(entry["image"]),
            width=int(entry.get("width", 0)),
            height=int(entry.get("height", 0)),
            z_index=int(entry["z_index"]) if entry.get("z_index") is not None else None,
            repeat=str(entry.get("repeat", "repeat")),
        )
        if decoration is None:
            return message

    for entry in sorted(
        sprites,
        key=lambda item: (int(item.get("z_index", 0)), str(item.get("image", ""))),
    ):
        decoration, message = add_decoration_to_area(
            area,
            kind=DECORATION_KIND_SPRITE,
            image=str(entry["image"]),
            x=int(entry.get("x", 0)),
            y=int(entry.get("y", 0)),
            width=int(entry["width"]),
            height=int(entry["height"]),
            z_index=int(entry["z_index"]) if entry.get("z_index") is not None else None,
        )
        if decoration is None:
            return message

    session.active_area_id = area_id
    return None


def _spawn_objects_from_template(
    session: Session,
    area_id: str,
    template: dict[str, Any],
) -> str | None:
    for index, entry in enumerate(template.get("objects", [])):
        if not isinstance(entry, dict):
            return f"objects[{index}] must be an object."
        position = entry.get("position")
        assert isinstance(position, (list, tuple))
        pos = (int(position[0]), int(position[1]))
        result = spawn_object_from_template(session, entry, pos, area_id=area_id)
        if not result.ok:
            return result.message

    session.active_area_id = area_id
    return None


def spawn_area_from_template(
    session: Session,
    template: dict[str, Any],
    *,
    area_id: str,
    mode: Literal["new", "replace"] = "new",
) -> AreaTemplateMutationResult:
    """Create or replace an area from a portable area template."""
    err = validate_area_template(template)
    if err:
        return AreaTemplateMutationResult(ok=False, message=err)

    cleaned = area_id.strip()
    id_err = validate_area_id(cleaned)
    if id_err:
        return AreaTemplateMutationResult(ok=False, message=id_err)

    normalized_mode = (mode or "new").strip().lower()
    if normalized_mode not in ("new", "replace"):
        return AreaTemplateMutationResult(
            ok=False,
            message="mode must be 'new' or 'replace'.",
        )

    if normalized_mode == "new":
        if cleaned in session.areas:
            return AreaTemplateMutationResult(
                ok=False,
                message=f"Area {cleaned!r} already exists.",
            )
        bounds = _grid_bounds_from_template(template)
        created = create_area_in_session(
            session,
            cleaned,
            description=str(template.get("area_description", "")),
            bounds=bounds,
        )
        if not created.ok:
            return AreaTemplateMutationResult(ok=False, message=created.message)
    else:
        if cleaned not in session.areas:
            return AreaTemplateMutationResult(
                ok=False,
                message=f"Unknown area {cleaned!r}.",
            )
        clear_err = _clear_area_for_replace(session, cleaned)
        if clear_err:
            return AreaTemplateMutationResult(ok=False, message=clear_err)
        meta_err = _apply_area_metadata(session, cleaned, template)
        if meta_err:
            return AreaTemplateMutationResult(ok=False, message=meta_err, area_id=cleaned)

    decor_err = _spawn_decorations_from_template(session, cleaned, template)
    if decor_err:
        return AreaTemplateMutationResult(ok=False, message=decor_err, area_id=cleaned)

    object_err = _spawn_objects_from_template(session, cleaned, template)
    if object_err:
        return AreaTemplateMutationResult(ok=False, message=object_err, area_id=cleaned)

    return AreaTemplateMutationResult(
        ok=True,
        message=f"Loaded area template into {cleaned!r} ({normalized_mode}).",
        area_id=cleaned,
    )


def validate_area_template_handlers(data: dict[str, Any]) -> None:
    """Ensure handlers referenced by nested object templates are registered."""
    if data.get("kind") != "area":
        return
    for entry in data.get("objects", []):
        if isinstance(entry, dict):
            validate_template_handlers(entry)
