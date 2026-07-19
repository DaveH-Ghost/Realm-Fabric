"""Configurable area grid, room description, and prompt context strings."""

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area, GridBounds, create_area
from campaign_rpg_engine.llm.prompt import assemble_default_compound_prompt, build_compound_prompt
from campaign_rpg_engine.llm.prompt_context import PromptContext, build_prompt_context
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.session import Session


def test_create_area_custom_grid_and_room():
    area = create_area(
        width=10,
        height=8,
        area_description="A misty forest clearing surrounded by pines.",
    )
    assert area.WIDTH == 10
    assert area.HEIGHT == 8
    assert area.is_valid_position((9, 7)) is True
    assert area.is_valid_position((10, 7)) is False
    assert "forest clearing" in area.get_area_description()


def test_area_rectangular_bounds():
    area = Area(bounds=GridBounds(min_x=0, min_y=0, max_x=9, max_y=4))
    assert area.is_valid_position((9, 4)) is True
    assert area.is_valid_position((9, 5)) is False
    assert "x is 0-9" in area.format_grid_bounds_message()


def test_custom_world_prompt_uses_bounds_and_room():
    area = create_area(
        width=10,
        height=10,
        area_description="An ancient battlefield.",
    )
    area.add_agent(
        Agent(
            id="agent_knight_01",
            name="Knight",
            personality="You scout the field.",
            position=(5, 5),
            memory=Memory(),
        )
    )
    prompt = build_compound_prompt(area.get_agent(), area)
    assert "10x10 grid" in prompt
    assert "0 to 9" in prompt
    assert "An ancient battlefield." in prompt


def test_build_prompt_context_exposes_string_blocks():
    area = create_area(area_description="A tavern common room.")
    area.add_agent(
        Agent(
            id="agent_bard_01",
            name="Bard",
            personality="You tell stories.",
            position=(1, 1),
            memory=Memory(),
        )
    )
    agent = area.get_agent()
    ctx = build_prompt_context(agent, area)

    assert isinstance(ctx, PromptContext)
    assert "Bard" in ctx.character
    assert "You are at" in ctx.passive_vision
    assert ctx.memory == "No memories yet."
    assert ctx.area_description == "A tavern common room."
    assert ctx.look_and_interact == ""


def test_application_can_compose_custom_prompt_from_context():
    area = create_area(area_description="Space station deck 7.")
    area.add_agent(
        Agent(
            id="agent_tech_01",
            name="Tech",
            personality="You maintain the ship.",
            position=(0, 0),
            memory=Memory(),
        )
    )
    ctx = build_prompt_context(area.get_agent(), area)
    custom = (
        f"ROOM:\n{ctx.area_description}\n\n"
        f"SEEING:\n{ctx.passive_vision}\n\n"
        f"REMEMBER:\n{ctx.memory}\n\n"
        f"RULES:\n{ctx.move_instructions}"
    )
    assert "Space station deck 7." in custom
    assert "SEEING:" in custom
    assert custom != assemble_default_compound_prompt(ctx)


def test_session_with_custom_area():
    area = create_area(
        width=3,
        height=3,
        area_description="A tiny closet.",
    )
    area.add_agent(
        Agent(
            id="agent_rat_01",
            name="Rat",
            personality="You hide.",
            position=(1, 1),
            memory=Memory(),
        )
    )
    session = Session(area)
    result = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="edge",
            move="2,2",
            action="none",
        ),
    )
    assert result.ok
    assert session.get_active_agent().position == (2, 2)

    off_grid = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="oops",
            move="5,5",
            action="none",
        ),
    )
    assert off_grid.ok
    assert "outside the room" in off_grid.message
    assert session.get_active_agent().position == (2, 2)
