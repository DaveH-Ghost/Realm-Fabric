"""Merged passive vision + interactions (V0.6.0c)."""

from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_agent_from_args, create_object_from_args
from campaign_rpg_engine.llm.prompt import build_compound_prompt
from campaign_rpg_engine.llm.prompt_context import build_prompt_context
from campaign_rpg_engine.perception import (
    PASSIVE_VISION_FAR_RULE,
    PASSIVE_VISION_LOOK_RULE,
    PASSIVE_VISION_NO_LOOK_TARGETS,
    build_passive_vision,
    get_object_interactions_reachable_after_move,
    perform_look,
)
from campaign_rpg_engine.prompt_blocks import (
    PromptBlock,
    default_prompt_blocks,
    render_prompt_blocks,
)
from campaign_rpg_engine.session import Session


def test_passive_vision_includes_look_rule():
    area = create_initial_area()
    agent = area.get_agent()
    vision = build_passive_vision(agent, area)
    assert PASSIVE_VISION_LOOK_RULE in vision
    assert PASSIVE_VISION_FAR_RULE in vision


def test_passive_vision_lists_interactions_under_object():
    area = create_initial_area()
    agent = area.get_agent()
    agent.position = (2, 3)

    vision = build_passive_vision(agent, area)

    assert "Ceramic Ball (obj_ball_01)" in vision
    assert "  - kick (range 1)" in vision
    assert "Object interactions available this turn:" not in vision


def test_passive_vision_no_look_targets_message_after_examining_all():
    area = create_initial_area()
    agent = area.get_agent()

    perform_look(agent, area, "obj_ball_01")
    perform_look(agent, area, "obj_sign_01")

    vision = build_passive_vision(agent, area)

    assert PASSIVE_VISION_NO_LOOK_TARGETS in vision


def test_agents_have_no_interaction_lines():
    area = create_initial_area()
    create_agent_from_args(
        area,
        'name "Goblin" personality "x" at 0,3',
    )
    agent = area.get_agent()

    vision = build_passive_vision(agent, area)

    assert "Goblin (agent_" in vision
    goblin_section = vision.split("Goblin (agent_")[1].split("\n")[0]
    assert "  - " not in goblin_section


def test_interactions_reachable_after_move_budget():
    area = create_initial_area()
    obj, _ = create_object_from_args(
        area,
        'name "Cookie" pdesc "A cookie." desc "Tasty." at 4,4 '
        "action eat range 1 handler delete_self "
        'result "Yum." passive "{actor} ate it."',
    )
    goblin, _ = create_agent_from_args(
        area,
        'name "Goblin" personality "x" move-speed 4 at 0,0',
    )

    assert goblin is not None
    assert obj is not None

    reachable = get_object_interactions_reachable_after_move(goblin, area, obj)
    assert ("eat", obj.actions["eat"]) in reachable

    goblin.move_speed = 1
    assert get_object_interactions_reachable_after_move(goblin, area, obj) == []
    vision = build_passive_vision(goblin, area)
    assert "[far] eat (range 1)" in vision


def test_look_and_interact_slot_renders_empty():
    session = Session.from_default()
    agent = session.get_active_agent()
    area = session.get_area_for_agent(agent)
    ctx = build_prompt_context(agent, area)
    rendered = render_prompt_blocks(
        [PromptBlock(type="slot", name="look_and_interact")],
        ctx,
        agent=agent,
        area=area,
    )
    assert rendered.strip() == ""


def test_default_prompt_blocks_omit_look_and_interact():
    names = [block.name for block in default_prompt_blocks() if block.type == "slot"]
    assert "look_and_interact" not in names


def test_compound_prompt_shows_interactions_in_passive_vision():
    area = create_initial_area()
    agent = area.get_agent()
    agent.position = (2, 3)

    prompt = build_compound_prompt(agent, area)

    assert PASSIVE_VISION_LOOK_RULE in prompt
    assert "  - kick (range 1)" in prompt
    assert "You can look at:" not in prompt
