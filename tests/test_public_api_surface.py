"""Tests for the stable ``campaign_rpg_engine`` public export surface (1.3.1)."""

from __future__ import annotations

import campaign_rpg_engine


def test_public_api_exports_match_all():
    """Every name in ``campaign_rpg_engine.__all__`` must be importable."""
    for name in campaign_rpg_engine.__all__:
        assert hasattr(campaign_rpg_engine, name), f"missing export: {name}"


def test_documented_public_surface_is_subset_of_all():
    """Documented app-facing names must remain in ``__all__``."""
    documented = {
        "__version__",
        "Agent",
        "AgentCompoundTurn",
        "Area",
        "AreaMutationResult",
        "DEFAULT_AREA_ID",
        "GameProfile",
        "GridBounds",
        "LLMParseError",
        "LLMResponse",
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
        "TurnRecord",
        "TurnResult",
        "WorldMutationResult",
        "build_save_snapshot",
        "build_session_snapshot",
        "create_area",
        "default_compound_profile",
        "default_prompt_blocks",
        "estimate_prompt_tokens",
        "get_compound_turn",
        "load_lorebook_from_path",
        "load_profile",
        "load_session_from_snapshot",
        "export_agent_template",
        "export_area_template",
        "export_object_template",
        "spawn_agent_from_template",
        "spawn_area_from_template",
        "spawn_object_from_template",
        "validate_area_template",
        "validate_template",
        "TEMPLATE_VERSION",
        "register_memory_module_from_path",
        "run_compound_turn",
    }
    missing = documented - set(campaign_rpg_engine.__all__)
    assert not missing, f"documented exports missing from __all__: {sorted(missing)}"


def test_removed_cli_exports_stay_private():
    """1.0 removed CLI / string-command surface from the public package."""
    removed = {
        "CommandResult",
        "create_area_from_args",
        "edit_area_from_args",
        "edit_agent_for_session",
        "edit_object_for_session",
        "parse_area_event_arg",
    }
    for name in removed:
        assert name not in campaign_rpg_engine.__all__
        assert not hasattr(campaign_rpg_engine, name), f"{name} should not be a top-level export"


def test_session_has_no_run_command():
    assert not hasattr(campaign_rpg_engine.Session, "run_command")
