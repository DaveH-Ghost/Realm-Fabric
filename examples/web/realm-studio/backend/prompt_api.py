"""Prompt block API helpers for realm-studio (V0.4.1b)."""

from __future__ import annotations

from src.prompt_blocks import (
    default_prompt_blocks,
    prompt_blocks_from_dicts,
    prompt_slot_catalog,
)
from src.session import Session


def get_prompt_blocks(session: Session) -> dict[str, object]:
    blocks = session.get_prompt_blocks()
    return {
        "ok": True,
        "blocks": [block.to_dict() for block in blocks],
        "uses_default": session.prompt_blocks_use_default(),
    }


def put_prompt_blocks(session: Session, items: list[dict[str, object]]) -> dict[str, object]:
    blocks, err = prompt_blocks_from_dicts(items)
    if err:
        return {"ok": False, "message": err}
    set_err = session.set_prompt_blocks(blocks)
    if set_err:
        return {"ok": False, "message": set_err}
    return get_prompt_blocks(session)


def reset_prompt_blocks(session: Session) -> dict[str, object]:
    session.reset_prompt_blocks()
    return get_prompt_blocks(session)


def get_prompt_slots(session: Session, agent_id: str | None = None) -> dict[str, object]:
    if agent_id is not None and session.get_agent(agent_id) is None:
        return {"ok": False, "message": f"Agent {agent_id!r} not found."}
    ctx = session.build_prompt_context_for_agent(agent_id)
    return {
        "ok": True,
        "slots": prompt_slot_catalog(ctx),
        "editable_sections": sorted({"compound_rules", "output_format"}),
        "default_block_count": len(default_prompt_blocks()),
    }
