"""Tests for the stable ``realm_fabric`` public export surface (V0.7.0a)."""

from __future__ import annotations

import realm_fabric


def test_public_api_exports_match_all():
    """Every name in ``realm_fabric.__all__`` must be importable."""
    for name in realm_fabric.__all__:
        assert hasattr(realm_fabric, name), f"missing export: {name}"


def test_documented_public_surface_is_subset_of_all():
    """Documented app-facing names must remain in ``__all__``."""
    documented = {
        "__version__",
        "Agent",
        "AgentCompoundTurn",
        "Area",
        "CommandResult",
        "DEFAULT_AREA_ID",
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
        "TurnResult",
        "WorldMutationResult",
        "build_save_snapshot",
        "create_area",
        "default_compound_profile",
        "default_prompt_blocks",
        "load_lorebook_from_path",
        "load_profile",
        "load_session_from_snapshot",
        "register_interaction_handler",
        "register_memory_module_from_path",
        "run_compound_turn",
    }
    missing = documented - set(realm_fabric.__all__)
    assert not missing, f"documented exports missing from __all__: {sorted(missing)}"
