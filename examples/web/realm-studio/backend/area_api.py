"""Area CRUD helpers for realm-studio (V0.4.0c2)."""

from __future__ import annotations

import shlex

from src.session import Session
from src.session_area_edit import (
    AreaMutationResult,
    create_area_from_args,
    delete_area_by_id,
    edit_area_from_args,
)

from backend.snapshot_compat import normalize_state_snapshot


def area_mutation_response(session: Session, result: AreaMutationResult) -> dict[str, object]:
    payload: dict[str, object] = {"ok": result.ok, "message": result.message}
    if result.ok:
        payload["snapshot"] = normalize_state_snapshot(
            session.snapshot(include_private=True)
        )
    return payload


def create_area(
    session: Session, *, area_id: str, description: str, width: int, height: int
) -> dict[str, object]:
    arg = (
        f"id {area_id} desc {shlex.quote(description)} "
        f"width {width} height {height}"
    )
    return area_mutation_response(session, create_area_from_args(session, arg))


def edit_area(
    session: Session,
    *,
    area_id: str,
    description: str | None,
    width: int | None,
    height: int | None,
) -> dict[str, object]:
    parts: list[str] = [area_id]
    if description is not None:
        parts.append(f"desc {shlex.quote(description)}")
    if width is not None:
        parts.append(f"width {width}")
    if height is not None:
        parts.append(f"height {height}")
    if len(parts) == 1:
        return {
            "ok": False,
            "message": "edit-area requires at least one field to change.",
        }
    return area_mutation_response(session, edit_area_from_args(session, " ".join(parts)))


def delete_area(session: Session, *, area_id: str) -> dict[str, object]:
    return area_mutation_response(session, delete_area_by_id(session, area_id))


def dispatch_area_cli_command(
    session: Session, cmd: str, arg: str
) -> dict[str, object]:
    """Fallback for POST /api/command with CLI-style area lines."""
    if cmd == "create_area":
        result = create_area_from_args(session, arg)
    elif cmd == "edit_area":
        result = edit_area_from_args(session, arg)
    elif cmd == "delete_area":
        result = delete_area_by_id(session, arg.strip())
    else:
        raise ValueError(f"Not an area command: {cmd!r}")
    return area_mutation_response(session, result)
