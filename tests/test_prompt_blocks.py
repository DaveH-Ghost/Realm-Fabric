"""Prompt block model and rendering (V0.4.1b)."""

from campaign_rpg_engine.game_profile import default_compound_profile
from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.llm.prompt_context import build_prompt_context
from campaign_rpg_engine.prompt_blocks import (
    PromptBlock,
    default_prompt_blocks,
    prompt_block_catalog,
    prompt_blocks_from_dicts,
    render_prompt_blocks,
)
from campaign_rpg_engine.prompt_template import PromptTemplate
from campaign_rpg_engine.session import Session


def test_default_blocks_match_template_render():
    profile = default_compound_profile()
    session = Session.from_default()
    agent = session.get_active_agent()
    ctx = build_prompt_context(agent, session.get_area_for_agent(agent))

    from_template = profile.template.render_context(ctx)
    from_blocks = render_prompt_blocks(default_prompt_blocks(), ctx)
    assert from_blocks == from_template


def test_session_build_prompt_uses_blocks():
    session = Session.from_default()
    profile = session.profile
    agent = session.get_active_agent()
    ctx = build_prompt_context(agent, session.get_area_for_agent(agent))

    assert session.build_prompt() == render_prompt_blocks(default_prompt_blocks(), ctx)
    assert session.build_prompt() == profile.template.render_context(ctx)


def test_reorder_blocks_changes_prompt():
    session = Session.from_default()
    blocks = list(default_prompt_blocks())
    blocks.insert(0, PromptBlock(type="text", content="PROMPT START\n"))
    session.set_prompt_blocks(blocks)
    prompt = session.build_prompt()
    assert prompt.startswith("PROMPT START")
    assert "You are Explorer." in prompt


def test_section_override_changes_rules():
    session = Session.from_default()
    blocks = default_prompt_blocks()
    custom = []
    for block in blocks:
        if block.type == "section" and block.name == "compound_rules":
            custom.append(
                PromptBlock(
                    type="section",
                    name="compound_rules",
                    content="CUSTOM RULES ONLY.",
                )
            )
        else:
            custom.append(block)
    session.set_prompt_blocks(custom)
    prompt = session.build_prompt()
    assert "CUSTOM RULES ONLY." in prompt
    assert "Each turn you may plan" not in prompt


def test_set_prompt_blocks_validation():
    session = Session.from_default()
    err = session.set_prompt_blocks(
        [PromptBlock(type="slot", name="not_a_real_slot")]
    )
    assert err is not None
    assert session.prompt_blocks_use_default()


def test_prompt_blocks_from_dicts_round_trip():
    original = default_prompt_blocks()
    payload = [block.to_dict() for block in original]
    parsed, err = prompt_blocks_from_dicts(payload)
    assert err is None
    assert len(parsed) == len(original)


def test_reset_prompt_blocks():
    session = Session.from_default()
    blocks = default_prompt_blocks()
    blocks[0] = PromptBlock(type="text", content="TOP\n")
    session.set_prompt_blocks(blocks)
    assert not session.prompt_blocks_use_default()
    session.reset_prompt_blocks()
    assert session.prompt_blocks_use_default()


def test_put_invalid_blocks_rejected():
    session = Session.from_default()
    _, err = prompt_blocks_from_dicts([{"type": "slot"}])
    assert err is not None


def test_character_slot_options_toggle_fields():
    session = Session.from_default()
    ctx = build_prompt_context(session.get_active_agent(), session.get_area_for_agent(session.get_active_agent()))
    blocks = [
        PromptBlock(
            type="slot",
            name="character",
            options={
                "include_name": True,
                "include_personality": False,
                "include_description": False,
            },
        )
    ]
    rendered = render_prompt_blocks(blocks, ctx)
    assert rendered.startswith("You are ")
    assert "Your personality:" not in rendered
    assert "Your detailed description:" not in rendered


def test_character_slot_requires_one_enabled_option():
    _, err = prompt_blocks_from_dicts(
        [
            {
                "type": "slot",
                "name": "character",
                "options": {
                    "include_name": False,
                    "include_personality": False,
                    "include_description": False,
                },
            }
        ]
    )
    assert err is not None
    assert "at least" in err.lower()


def test_prompt_block_catalog_lists_slot_settings():
    catalog = prompt_block_catalog()
    assert "character" in catalog["slot_settings"]
    assert catalog["slot_settings"]["character"]["fields"]
    assert "passive_vision" in catalog["slot_settings"]


def test_area_format_grid_description_uses_screen_coordinates():
    area = create_initial_area()
    text = area.format_grid_description()
    assert "northwest corner" in text
    assert "southeast" in text
    assert "Y increases southward" in text
    assert "northward" not in text


def test_move_instructions_slot_omits_coordinates():
    session = Session.from_default()
    agent = session.get_active_agent()
    area = session.get_area_for_agent(agent)
    ctx = build_prompt_context(agent, area)
    blocks = [
        PromptBlock(
            type="slot",
            name="move_instructions",
            options={"include_coordinate_moves": False},
        )
    ]
    rendered = render_prompt_blocks(blocks, ctx, agent=agent, area=area)
    assert "You may move to any coordinate" not in rendered
    assert "move may be an entity id" in rendered


def test_move_instructions_move_speed_with_units():
    session = Session.from_default()
    session.set_vision_units("ft", 5)
    session.edit_agent("agent_01", move_speed=2)
    agent = session.get_active_agent()
    area = session.get_area_for_agent(agent)
    ctx = build_prompt_context(agent, area)
    blocks = [PromptBlock(type="slot", name="move_instructions")]
    rendered = render_prompt_blocks(
        blocks,
        ctx,
        agent=agent,
        area=area,
        vision_units=session.vision_units,
        units_per_tile=session.vision_units_per_tile,
    )
    assert "Your move speed this turn is 10 ft." in rendered


def test_passive_vision_slot_lists_interactions_with_units():
    session = Session.from_default()
    session.set_vision_units("ft", 5)
    agent = session.get_active_agent()
    agent.position = (2, 3)
    area = session.get_area_for_agent(agent)
    ctx = build_prompt_context(agent, area)
    blocks = [PromptBlock(type="slot", name="passive_vision")]
    rendered = render_prompt_blocks(
        blocks,
        ctx,
        agent=agent,
        area=area,
        vision_units=session.vision_units,
        units_per_tile=session.vision_units_per_tile,
    )
    assert "  - kick (range 5 ft)" in rendered


def test_look_and_interact_slot_is_empty_alias():
    session = Session.from_default()
    session.set_vision_units("ft", 5)
    agent = session.get_active_agent()
    agent.position = (2, 3)
    area = session.get_area_for_agent(agent)
    ctx = build_prompt_context(agent, area)
    blocks = [PromptBlock(type="slot", name="look_and_interact")]
    rendered = render_prompt_blocks(
        blocks,
        ctx,
        agent=agent,
        area=area,
        vision_units=session.vision_units,
        units_per_tile=session.vision_units_per_tile,
    )
    assert rendered.strip() == ""


def test_passive_vision_slot_relative_bearing():
    session = Session.from_default()
    session.set_vision_units("ft", 5)
    agent = session.get_active_agent()
    area = session.get_area_for_agent(agent)
    ctx = build_prompt_context(agent, area)
    blocks = [
        PromptBlock(
            type="slot",
            name="passive_vision",
            options={"include_relative_bearing": True},
        )
    ]
    rendered = render_prompt_blocks(
        blocks,
        ctx,
        agent=agent,
        area=area,
        vision_units=session.vision_units,
        units_per_tile=session.vision_units_per_tile,
    )
    assert "South of you, 15 ft away" in rendered


def test_passive_vision_slot_options():
    session = Session.from_default()
    agent = session.get_active_agent()
    area = session.get_area_for_agent(agent)
    ctx = build_prompt_context(agent, area)
    blocks = [
        PromptBlock(
            type="slot",
            name="passive_vision",
            options={
                "include_you_are_at": False,
                "include_entity_coordinates": True,
            },
        )
    ]
    rendered = render_prompt_blocks(blocks, ctx, agent=agent, area=area)
    assert "You are at" not in rendered
    assert "Ceramic Ball (obj_ball_01), (2, 2)" in rendered


def test_prompt_block_catalog_lists_all_types():
    catalog = prompt_block_catalog()
    types = {entry["type"] for entry in catalog["block_types"]}
    assert types == {"slot", "text", "section"}
    slot_entry = next(item for item in catalog["block_types"] if item["type"] == "slot")
    slot_names = {opt["name"] for opt in slot_entry["options"]}
    assert "passive_vision" in slot_names
    assert "rules" not in slot_names
    section_entry = next(item for item in catalog["block_types"] if item["type"] == "section")
    section_names = {opt["name"] for opt in section_entry["options"]}
    assert section_names == {"compound_rules", "output_format"}
    compound = next(opt for opt in section_entry["options"] if opt["name"] == "compound_rules")
    assert compound["default_content"]


def test_lorebook_prompt_slot_requires_id():
    blocks, err = prompt_blocks_from_dicts([{"type": "slot", "name": "lorebook"}])
    assert blocks == []
    assert "lorebook_id" in (err or "")


def test_lorebook_prompt_slot_renders_with_session_book():
    from campaign_rpg_engine.lorebook import load_lorebook_from_dict
    from campaign_rpg_engine.prompt_blocks import validate_prompt_blocks

    session = Session.from_default()
    book = load_lorebook_from_dict(
        {
            "entries": {
                "0": {
                    "uid": 0,
                    "key": [],
                    "content": "Shared world fact.",
                    "constant": True,
                    "disable": False,
                    "order": 0,
                }
            }
        },
        book_id="world",
    )
    session.update_lorebook(book)
    blocks = [
        PromptBlock(
            type="slot",
            name="lorebook",
            options={"lorebook_id": "world"},
        )
    ]
    assert validate_prompt_blocks(blocks) is None
    agent = session.get_active_agent()
    area = session.get_area_for_agent(agent)
    ctx = build_prompt_context(agent, area)
    text = render_prompt_blocks(
        blocks,
        ctx,
        agent=agent,
        area=area,
        lorebooks=session._lorebooks,
    )
    assert "World info:" in text
    assert "Shared world fact." in text


def test_prompt_block_catalog_includes_lorebook_slot():
    catalog = prompt_block_catalog()
    slot_type = next(item for item in catalog["block_types"] if item["type"] == "slot")
    names = {opt["name"] for opt in slot_type["options"]}
    assert "lorebook" in names
    assert catalog.get("lorebook_slot") is not None
