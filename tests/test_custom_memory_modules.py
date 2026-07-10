"""Custom memory module registration (V0.4.6)."""

from pathlib import Path

import pytest

from campaign_rpg_engine.memory_modules.registry import (
    create_module,
    export_module_state,
    is_module_loaded,
    loaded_module_ids,
    register_memory_module_from_path,
    restore_module_state,
)

_EXAMPLE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "custom_memory"
    / "rolling_summary_custom.py"
)


@pytest.fixture(autouse=True)
def _clear_custom_registry():
    from campaign_rpg_engine.memory_modules import registry

    registry._CUSTOM_REGISTRY.clear()
    registry._CUSTOM_METADATA.clear()
    yield
    registry._CUSTOM_REGISTRY.clear()
    registry._CUSTOM_METADATA.clear()


def test_register_example_module_from_path():
    module_id = register_memory_module_from_path(_EXAMPLE)
    assert module_id == "rolling_summary_custom"
    assert is_module_loaded("rolling_summary_custom")
    assert "rolling_summary_custom" in loaded_module_ids()


def test_register_rejects_builtin_id_collision(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_text(
        'MODULE_ID = "recent_turns"\n'
        "def create_module(**config):\n"
        "    raise RuntimeError('nope')\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="conflicts with a built-in"):
        register_memory_module_from_path(bad)


def test_register_overwrites_same_module_id():
    register_memory_module_from_path(_EXAMPLE)
    module_id = register_memory_module_from_path(_EXAMPLE)
    assert module_id == "rolling_summary_custom"


def test_custom_module_create_and_export_round_trip():
    register_memory_module_from_path(_EXAMPLE)
    module = create_module("rolling_summary_custom", summary_tail=1)
    state = export_module_state(module)
    fresh = create_module("rolling_summary_custom")
    restore_module_state(fresh, state)
    assert fresh.module_id == "rolling_summary_custom"


def test_create_agent_memory_with_custom_module():
    from campaign_rpg_engine.area import Area
    from campaign_rpg_engine.area_edit import create_agent_from_args

    register_memory_module_from_path(_EXAMPLE)
    area = Area()
    agent, msg = create_agent_from_args(
        area,
        'name "Tester" personality "x" memory rolling_summary_custom at 1,1',
    )
    assert agent is not None, msg
    assert agent.memory.module_id == "rolling_summary_custom"


def test_create_agent_rejects_unloaded_custom_module():
    from campaign_rpg_engine.area import Area
    from campaign_rpg_engine.area_edit import create_agent_from_args

    area = Area()
    agent, msg = create_agent_from_args(
        area,
        'name "Tester" personality "x" memory rolling_summary_custom at 1,1',
    )
    assert agent is None
    assert "not loaded" in msg.lower()
