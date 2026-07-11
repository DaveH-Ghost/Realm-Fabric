"""Tests for session coordinate_mode and relative prompt rendering."""

from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.coordinate_mode import COORDINATE_MODE_RELATIVE
from campaign_rpg_engine.llm.prompt_context import (
    compound_output_format,
    compound_output_format_relative,
    compound_turn_rules_relative,
)
from campaign_rpg_engine.prompt_blocks import (
    PromptBlock,
    default_prompt_blocks,
    render_prompt_blocks,
)
from campaign_rpg_engine.session import Session


def test_relative_grid_description_mentions_tile_size():
    area = create_initial_area()
    text = area.format_grid_description(
        coordinate_mode=COORDINATE_MODE_RELATIVE,
        vision_units="ft",
        units_per_tile=5,
    )
    assert "grid-based world" in text
    assert "Each tile is 5 ft" in text
    assert "northwest" not in text
    assert "(0," not in text


def test_relative_grid_description_without_units():
    area = create_initial_area()
    text = area.format_grid_description(coordinate_mode=COORDINATE_MODE_RELATIVE)
    assert "grid-based world" in text
    assert "Each tile" not in text


def test_relative_mode_prompt_omits_coordinates():
    session = Session.from_default()
    session.set_coordinate_mode(COORDINATE_MODE_RELATIVE)
    session.set_vision_units("ft", 5)

    agent = session.get_active_agent()
    area = session.get_area_for_agent(agent)
    agent.position = (0, 0)
    ball = area.get_object_by_id("obj_ball_01")
    assert ball is not None
    ball.position = (2, 2)

    prompt = session.build_prompt()
    assert "You are at" not in prompt
    assert "(2, 2)" not in prompt.split("Passive Vision")[1].split("Memory")[0]
    assert "South" in prompt or "East" in prompt or "away" in prompt
    assert "x,y" not in prompt
    assert '"2,3"' not in prompt
    assert "northwest" not in prompt
    assert "You may move to any coordinate" not in prompt
    assert 'move may be an entity id' in prompt


def test_relative_mode_uses_entity_id_output_example():
    blocks = default_prompt_blocks()
    session = Session.from_default()
    session.set_coordinate_mode(COORDINATE_MODE_RELATIVE)
    ctx = session.build_prompt_context_for_agent()
    rendered = render_prompt_blocks(
        blocks,
        ctx,
        agent=session.get_active_agent(),
        area=session.get_area_for_agent(session.get_active_agent()),
        vision_units=session.vision_units,
        units_per_tile=session.vision_units_per_tile,
        coordinate_mode=session.coordinate_mode,
    )
    assert compound_output_format_relative() in rendered
    assert compound_turn_rules_relative() in rendered
    assert compound_output_format() not in rendered


def test_coordinate_mode_round_trip_in_save():
    session = Session.from_default()
    session.set_coordinate_mode(COORDINATE_MODE_RELATIVE)
    session.set_vision_units("ft", 5)

    from campaign_rpg_engine.session_persistence import (
        build_save_snapshot,
        load_session_from_snapshot,
    )

    restored = load_session_from_snapshot(build_save_snapshot(session))
    assert restored.coordinate_mode == COORDINATE_MODE_RELATIVE
    assert restored.vision_units == "ft"
    assert restored.vision_units_per_tile == 5


def test_render_section_block_relative_overrides_custom_content():
    from campaign_rpg_engine.prompt_blocks import render_section_block

    block = PromptBlock(
        type="section",
        name="compound_rules",
        content="Custom rules with x,y still here.",
    )
    text = render_section_block(block, COORDINATE_MODE_RELATIVE)
    assert "x,y" not in text
    assert "entity id" in text
