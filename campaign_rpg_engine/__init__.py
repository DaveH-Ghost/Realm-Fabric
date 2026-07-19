"""
campaign_rpg_engine — public engine API for CampAIgn-RPG-Engine (1.6.0).

Import from this package in application code.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area, GridBounds, create_area, create_initial_area
from campaign_rpg_engine.decoration import Decoration
from campaign_rpg_engine.edit.area_edit import (
    delete_agent_by_id,
    format_agents_list,
    format_full_list,
    format_objects_list,
    parse_position,
)
from campaign_rpg_engine.edit.decoration_edit import DecorationMutationResult
from campaign_rpg_engine.edit.session_area_edit import (
    AreaMutationResult,
    delete_area_by_id,
)
from campaign_rpg_engine.edit.world_edit_api import WorldMutationResult
from campaign_rpg_engine.events import (
    clear_event_listeners_for_tests,
    emit_session_event,
    list_registered_events,
    register_event_listener,
    unregister_event_listeners,
)
from campaign_rpg_engine.game_profile import GameProfile, default_compound_profile, load_profile
from campaign_rpg_engine.interaction_handlers import (
    collect_prefixed_params,
    format_handlers_list,
    get_handler_registration,
    handler_catalog_entry,
    is_handler_registered,
    list_registered_handlers,
    register_interaction_handler,
    run_interaction_handler,
    run_named_handler,
)
from campaign_rpg_engine.llm.client import (
    LLMParseError,
    PromptTooLargeError,
    get_compound_turn,
    get_llm_provider,
)
from campaign_rpg_engine.llm.prompt_context import PromptContext, build_prompt_context
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.llm.token_estimate import (
    DEFAULT_INPUT_WARNING_PERCENT,
    DEFAULT_MAX_INPUT_TOKENS,
    estimate_prompt_tokens,
    get_input_warning_percent,
    get_max_input_tokens,
    prompt_exceeds_max_input,
    prompt_token_budget_status,
)
from campaign_rpg_engine.llm.types import LLMResponse
from campaign_rpg_engine.lorebook import (
    DEFAULT_LOREBOOK_CHAR_BUDGET,
    ST_ENTRY_DEFAULTS,
    Lorebook,
    LorebookScanConfig,
    LoreEntry,
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
from campaign_rpg_engine.memory_modules.affinity import AffinityModule
from campaign_rpg_engine.memory_modules.affinity_ladder import (
    AFFINITY_MAX,
    AFFINITY_MIN,
    DEFAULT_RELATIONSHIP_SUMMARY_MAX_CHARS,
)
from campaign_rpg_engine.memory_modules.base import MemoryModule
from campaign_rpg_engine.memory_modules.recent_turns import DEFAULT_WINDOW, MAX_WINDOW, MIN_WINDOW
from campaign_rpg_engine.memory_modules.registry import (
    default_module_id,
    format_memory_modules_list,
    loaded_module_ids,
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
from campaign_rpg_engine.prompt_slots import (
    clear_prompt_slots_for_tests,
    is_prompt_slot_registered,
    list_registered_prompt_slots,
    register_prompt_slot,
    render_registered_prompt_slot,
)
from campaign_rpg_engine.session import Session, SessionResult, TurnResult
from campaign_rpg_engine.session_persistence import build_save_snapshot, load_session_from_snapshot
from campaign_rpg_engine.simulation import run_compound_turn
from campaign_rpg_engine.snapshot import (
    DEFAULT_AREA_ID,
    build_area_snapshot,
    build_session_snapshot,
)
from campaign_rpg_engine.templates.area_templates import (
    AreaTemplateMutationResult,
    export_area_template,
    export_decoration_template,
    spawn_area_from_template,
    validate_area_template,
)
from campaign_rpg_engine.templates.entity_templates import (
    TEMPLATE_VERSION,
    export_agent_template,
    export_object_template,
    spawn_agent_from_template,
    spawn_object_from_template,
    validate_template,
)
from campaign_rpg_engine.templates.interact_templates import interact_template_var_help
from campaign_rpg_engine.turn_verbs import (
    clear_turn_verbs_for_tests,
    format_turn_verbs_list,
    list_registered_turn_verbs,
    register_turn_verb,
    run_turn_verb,
)

__all__ = [
    "__version__",
    "ActionKind",
    "Agent",
    "AgentCompoundTurn",
    "Area",
    "AreaMutationResult",
    "AreaTemplateMutationResult",
    "DEFAULT_AREA_ID",
    "DEFAULT_CHAR_BUDGET",
    "DEFAULT_INPUT_WARNING_PERCENT",
    "DEFAULT_LOREBOOK_CHAR_BUDGET",
    "DEFAULT_MAX_INPUT_TOKENS",
    "DEFAULT_MAX_SUMMARY_CHARS",
    "DEFAULT_SUMMARY_INTERVAL",
    "DEFAULT_SUMMARY_TAIL",
    "DEFAULT_WINDOW",
    "Decoration",
    "DecorationMutationResult",
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
    "PromptTooLargeError",
    "MIN_WINDOW",
    "Object",
    "ObjectAction",
    "PromptBlock",
    "PromptContext",
    "AFFINITY_MAX",
    "AFFINITY_MIN",
    "AffinityModule",
    "DEFAULT_RELATIONSHIP_SUMMARY_MAX_CHARS",
    "RollingSummaryModule",
    "Session",
    "SessionResult",
    "spawn_agent_from_template",
    "spawn_area_from_template",
    "spawn_object_from_template",
    "ST_ENTRY_DEFAULTS",
    "TEMPLATE_VERSION",
    "TurnRecord",
    "TurnResult",
    "WorldMutationResult",
    "build_area_snapshot",
    "build_passive_vision",
    "build_prompt_context",
    "build_save_snapshot",
    "build_scan_corpus",
    "build_session_snapshot",
    "clear_event_listeners_for_tests",
    "clear_prompt_slots_for_tests",
    "clear_turn_verbs_for_tests",
    "collect_prefixed_params",
    "create_area",
    "create_empty_lorebook",
    "create_initial_area",
    "default_compound_profile",
    "default_module_id",
    "default_prompt_blocks",
    "delete_area_by_id",
    "derive_lorebook_id_from_filename",
    "describe_scan_sources",
    "emit_session_event",
    "export_agent_template",
    "export_area_template",
    "export_decoration_template",
    "export_object_template",
    "enrich_blocks_with_previews",
    "estimate_prompt_tokens",
    "format_agents_list",
    "format_full_list",
    "format_handlers_list",
    "format_memory_modules_list",
    "format_objects_list",
    "format_turn_verbs_list",
    "get_compound_turn",
    "get_handler_registration",
    "get_input_warning_percent",
    "get_llm_provider",
    "get_max_input_tokens",
    "handler_catalog_entry",
    "interact_template_var_help",
    "is_handler_registered",
    "is_prompt_slot_registered",
    "list_registered_events",
    "list_registered_handlers",
    "list_registered_prompt_slots",
    "list_registered_turn_verbs",
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
    "prompt_exceeds_max_input",
    "prompt_slot_catalog",
    "prompt_token_budget_status",
    "register_interaction_handler",
    "register_event_listener",
    "register_prompt_slot",
    "register_turn_verb",
    "render_registered_prompt_slot",
    "render_lorebook",
    "run_compound_turn",
    "run_interaction_handler",
    "run_named_handler",
    "run_turn_verb",
    "unregister_event_listeners",
    "validate_area_template",
    "validate_prompt_blocks",
    "validate_template",
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
