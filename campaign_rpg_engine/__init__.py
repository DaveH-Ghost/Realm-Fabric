"""
campaign_rpg_engine — public engine API for CampAIgn-RPG-Engine (1.0.0).

Import from this package in application code.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area, GridBounds, create_area, create_initial_area
from campaign_rpg_engine.area_edit import (
    delete_agent_by_id,
    format_agents_list,
    format_full_list,
    format_objects_list,
    parse_position,
)
from campaign_rpg_engine.game_profile import GameProfile, default_compound_profile, load_profile
from campaign_rpg_engine.interact_templates import interact_template_var_help
from campaign_rpg_engine.llm.client import LLMParseError, get_compound_turn
from campaign_rpg_engine.llm.prompt_context import PromptContext, build_prompt_context
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.llm.token_estimate import estimate_prompt_tokens
from campaign_rpg_engine.llm.types import LLMResponse
from campaign_rpg_engine.lorebook import (
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
from campaign_rpg_engine.lorebook.factory import create_empty_lorebook
from campaign_rpg_engine.memory import TurnRecord
from campaign_rpg_engine.memory_modules.base import MemoryModule
from campaign_rpg_engine.memory_modules.recent_turns import DEFAULT_WINDOW, MAX_WINDOW, MIN_WINDOW
from campaign_rpg_engine.memory_modules.registry import (
    clear_custom_memory_registrations,
    default_module_id,
    format_memory_modules_list,
    get_custom_module_metadata,
    loaded_module_ids,
    register_memory_module_from_path,
    register_memory_module_from_source,
)
from campaign_rpg_engine.memory_modules.rolling_summary import (
    DEFAULT_MAX_SUMMARY_CHARS,
    DEFAULT_SUMMARY_INTERVAL,
    DEFAULT_SUMMARY_TAIL,
    MAX_MAX_SUMMARY_CHARS,
    MIN_MAX_SUMMARY_CHARS,
    MIN_SUMMARY_INTERVAL,
    MIN_SUMMARY_TAIL,
    RollingSummaryModule,
)
from campaign_rpg_engine.memory_modules.salient_turns import (
    DEFAULT_CHAR_BUDGET,
    MAX_CHAR_BUDGET,
    MIN_CHAR_BUDGET,
)
from campaign_rpg_engine.object import Object, object_footprint_tiles
from campaign_rpg_engine.object_action import ActionKind, ObjectAction
from campaign_rpg_engine.perception import build_passive_vision
from campaign_rpg_engine.prompt_blocks import (
    PromptBlock,
    default_prompt_blocks,
    enrich_blocks_with_previews,
    prompt_block_catalog,
    prompt_blocks_from_dicts,
    prompt_slot_catalog,
    validate_prompt_blocks,
)
from campaign_rpg_engine.session import Session, SessionResult, TurnResult
from campaign_rpg_engine.session_area_edit import (
    AreaMutationResult,
    delete_area_by_id,
)
from campaign_rpg_engine.simulation import run_compound_turn
from campaign_rpg_engine.session_persistence import build_save_snapshot, load_session_from_snapshot
from campaign_rpg_engine.interaction_handlers import (
    format_handlers_list,
    get_handler_registration,
    is_handler_registered,
    list_registered_handlers,
    register_interaction_handler,
    run_interaction_handler,
)
from campaign_rpg_engine.snapshot import DEFAULT_AREA_ID, build_area_snapshot, build_session_snapshot
from campaign_rpg_engine.world_edit_api import WorldMutationResult

__all__ = [
    "__version__",
    "ActionKind",
    "Agent",
    "AgentCompoundTurn",
    "Area",
    "AreaMutationResult",
    "DEFAULT_AREA_ID",
    "DEFAULT_CHAR_BUDGET",
    "DEFAULT_LOREBOOK_CHAR_BUDGET",
    "DEFAULT_MAX_SUMMARY_CHARS",
    "DEFAULT_SUMMARY_INTERVAL",
    "DEFAULT_SUMMARY_TAIL",
    "DEFAULT_WINDOW",
    "GameProfile",
    "GridBounds",
    "LLMParseError",
    "LLMResponse",
    "Lorebook",
    "LoreEntry",
    "LorebookScanConfig",
    "MAX_CHAR_BUDGET",
    "MAX_MAX_SUMMARY_CHARS",
    "MAX_WINDOW",
    "MemoryModule",
    "MIN_CHAR_BUDGET",
    "MIN_MAX_SUMMARY_CHARS",
    "MIN_SUMMARY_INTERVAL",
    "MIN_SUMMARY_TAIL",
    "MIN_WINDOW",
    "Object",
    "ObjectAction",
    "PromptBlock",
    "PromptContext",
    "RollingSummaryModule",
    "Session",
    "SessionResult",
    "ST_ENTRY_DEFAULTS",
    "TurnRecord",
    "TurnResult",
    "WorldMutationResult",
    "build_area_snapshot",
    "build_passive_vision",
    "build_prompt_context",
    "build_save_snapshot",
    "build_scan_corpus",
    "build_session_snapshot",
    "clear_custom_memory_registrations",
    "create_area",
    "create_empty_lorebook",
    "create_initial_area",
    "default_compound_profile",
    "default_module_id",
    "default_prompt_blocks",
    "delete_area_by_id",
    "derive_lorebook_id_from_filename",
    "describe_scan_sources",
    "enrich_blocks_with_previews",
    "estimate_prompt_tokens",
    "format_agents_list",
    "format_full_list",
    "format_handlers_list",
    "format_memory_modules_list",
    "format_objects_list",
    "get_compound_turn",
    "get_custom_module_metadata",
    "get_handler_registration",
    "interact_template_var_help",
    "is_handler_registered",
    "list_registered_handlers",
    "load_lorebook_from_dict",
    "load_lorebook_from_path",
    "load_profile",
    "load_session_from_snapshot",
    "loaded_module_ids",
    "match_lorebook_entries",
    "new_st_entry_dict",
    "object_footprint_tiles",
    "parse_position",
    "prompt_block_catalog",
    "prompt_blocks_from_dicts",
    "prompt_slot_catalog",
    "register_interaction_handler",
    "register_memory_module_from_path",
    "register_memory_module_from_source",
    "render_lorebook",
    "run_compound_turn",
    "run_interaction_handler",
    "validate_prompt_blocks",
    "with_st_entry_defaults",
]

_ROOT = Path(__file__).resolve().parent.parent


def _read_version() -> str:
    try:
        from importlib.metadata import version as _pkg_version

        return _pkg_version("campaign-rpg-engine")
    except Exception:
        pass
    pyproject_path = _ROOT / "pyproject.toml"
    if pyproject_path.is_file():
        return tomllib.loads(pyproject_path.read_text(encoding="utf-8"))["project"]["version"]
    return "0.0.0"


__version__ = _read_version()
