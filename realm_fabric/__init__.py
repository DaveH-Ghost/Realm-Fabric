"""
realm_fabric — public engine API for Realm-Fabric (V0.7.0).

Downstream projects should import from this package. Modules under ``src.*``
remain importable for the CLI and tests but are not guaranteed stable.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from src.agent import Agent
from src.area import Area, GridBounds, create_area, create_initial_area
from src.game_profile import GameProfile, default_compound_profile, load_profile
from src.llm.prompt_context import PromptContext, build_prompt_context
from src.llm.schemas import AgentCompoundTurn
from src.lorebook import (
    DEFAULT_LOREBOOK_CHAR_BUDGET,
    Lorebook,
    LoreEntry,
    LorebookScanConfig,
    ST_ENTRY_DEFAULTS,
    build_scan_corpus,
    derive_lorebook_id_from_filename,
    describe_scan_sources,
    load_lorebook_from_dict,
    load_lorebook_from_path,
    match_lorebook_entries,
    new_st_entry_dict,
    render_lorebook,
    with_st_entry_defaults,
)
from src.memory_modules.base import MemoryModule
from src.memory_modules.registry import register_memory_module_from_path
from src.object import Object
from src.object_action import ActionKind, ObjectAction
from src.prompt_blocks import (
    PromptBlock,
    default_prompt_blocks,
    prompt_block_catalog,
    prompt_blocks_from_dicts,
    validate_prompt_blocks,
)
from src.session import CommandResult, Session, SessionResult, TurnResult
from src.simulation import run_compound_turn
from src.session_persistence import build_save_snapshot, load_session_from_snapshot
from src.interaction_handlers import (
    format_handlers_list,
    is_handler_registered,
    list_registered_handlers,
    register_interaction_handler,
    run_interaction_handler,
)
from src.snapshot import DEFAULT_AREA_ID, build_area_snapshot, build_session_snapshot
from src.world_edit_api import WorldMutationResult

__all__ = [
    "__version__",
    "ActionKind",
    "Agent",
    "AgentCompoundTurn",
    "Area",
    "CommandResult",
    "DEFAULT_AREA_ID",
    "DEFAULT_LOREBOOK_CHAR_BUDGET",
    "GameProfile",
    "GridBounds",
    "Lorebook",
    "LoreEntry",
    "LorebookScanConfig",
    "MemoryModule",
    "Object",
    "ObjectAction",
    "PromptBlock",
    "PromptContext",
    "Session",
    "SessionResult",
    "ST_ENTRY_DEFAULTS",
    "TurnResult",
    "WorldMutationResult",
    "build_area_snapshot",
    "build_prompt_context",
    "build_save_snapshot",
    "build_scan_corpus",
    "build_session_snapshot",
    "create_area",
    "create_initial_area",
    "default_compound_profile",
    "default_prompt_blocks",
    "derive_lorebook_id_from_filename",
    "describe_scan_sources",
    "format_handlers_list",
    "is_handler_registered",
    "list_registered_handlers",
    "load_lorebook_from_dict",
    "load_lorebook_from_path",
    "load_profile",
    "load_session_from_snapshot",
    "match_lorebook_entries",
    "new_st_entry_dict",
    "prompt_block_catalog",
    "prompt_blocks_from_dicts",
    "register_interaction_handler",
    "register_memory_module_from_path",
    "render_lorebook",
    "run_compound_turn",
    "run_interaction_handler",
    "validate_prompt_blocks",
    "with_st_entry_defaults",
]

_ROOT = Path(__file__).resolve().parent.parent


def _read_version() -> str:
    pyproject_version = tomllib.loads(
        (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    try:
        from importlib.metadata import version as _pkg_version

        installed = _pkg_version("realm-fabric")
        if installed == pyproject_version:
            return installed
    except Exception:
        pass
    return pyproject_version


__version__ = _read_version()
