"""
test_perception.py

Tests for V0.1 passive/detailed perception and cross-agent invalidation.
"""

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.perception import (
    PASSIVE_VISION_LOOK_RULE,
    PASSIVE_VISION_NO_LOOK_TARGETS,
    build_passive_vision,
    format_object_vision_desc,
    perform_look,
)
from campaign_rpg_engine.object import Object
from campaign_rpg_engine.area import create_initial_area


def test_initial_sign_shows_passive_not_pre_marked():
    """Sign shows passive + [?] at startup; agent has not looked at anything."""
    area = create_initial_area()
    agent = area.get_agent()

    assert not agent.memory.has_looked_at("obj_sign_01")
    assert not agent.memory.has_ever_looked_at("obj_sign_01")
    vision = build_passive_vision(agent, area)
    assert (
        "Wooden Sign (obj_sign_01), (2, 4) - [?] A simple wooden sign on the wall."
        in vision
    )


def test_passive_vision_can_omit_you_are_at():
    area = create_initial_area()
    agent = area.get_agent()
    vision = build_passive_vision(agent, area, include_you_are_at=False)
    assert "You are at" not in vision
    assert "Ceramic Ball (obj_ball_01)" in vision


def test_passive_vision_can_omit_entity_coordinates():
    area = create_initial_area()
    agent = area.get_agent()
    vision = build_passive_vision(agent, area, include_entity_coordinates=False)
    assert "You are at (1, 1)." in vision
    assert "Ceramic Ball (obj_ball_01), (2, 2)" not in vision
    assert "Ceramic Ball (obj_ball_01) - [?]" in vision


def test_passive_vision_relative_bearing():
    area = create_initial_area()
    agent = area.get_agent()
    vision = build_passive_vision(
        agent,
        area,
        include_relative_bearing=True,
        vision_units="ft",
        units_per_tile=5,
    )
    assert "South of you, 15 ft away" in vision
    assert "Wooden Sign (obj_sign_01)" in vision


def test_ball_vision_states_never_stale_current():
    """Ball: [?] initially, detailed after look, [?] [changed] after invalidate."""
    area = create_initial_area()
    agent = area.get_agent()

    vision = build_passive_vision(agent, area)
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?]" in vision

    perform_look(agent, area, "obj_ball_01")
    vision = build_passive_vision(agent, area)
    assert "scuffs and feels light" in vision

    area.invalidate_object_knowledge("obj_ball_01")
    vision = build_passive_vision(agent, area)
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?] [changed]" in vision
    assert agent.memory.has_ever_looked_at("obj_ball_01")
    assert not agent.memory.has_looked_at("obj_ball_01")

    perform_look(agent, area, "obj_ball_01")
    vision = build_passive_vision(agent, area)
    assert "scuffs and feels light" in vision


def test_sign_stale_shows_changed_with_passive():
    """After look + desc invalidation, sign shows [?] [changed] {passive}."""
    area = create_initial_area()
    agent = area.get_agent()

    perform_look(agent, area, "obj_sign_01")
    area.invalidate_object_knowledge("obj_sign_01")
    vision = build_passive_vision(agent, area)

    assert (
        "Wooden Sign (obj_sign_01), (2, 4) - [?] [changed] A simple wooden sign on the wall."
        in vision
    )
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?]" in vision


def test_sign_description_update_look_restores_new_text():
    """After sign detailed desc changes and invalidation, look returns new text."""
    area = create_initial_area()
    agent = area.get_agent()
    new_text = "Brand new sign text for testing."

    perform_look(agent, area, "obj_sign_01")
    sign = area.get_object_by_id("obj_sign_01")
    sign.description = new_text
    area.invalidate_object_knowledge("obj_sign_01")

    vision = build_passive_vision(agent, area)
    assert "[?] [changed] A simple wooden sign on the wall." in vision

    outcome = perform_look(agent, area, "obj_sign_01")
    assert new_text in outcome.result
    assert agent.memory.has_looked_at("obj_sign_01")

    vision = build_passive_vision(agent, area)
    assert new_text in vision


def test_invalidate_object_knowledge_affects_all_agents_who_looked():
    """Both agents who looked at the ball see [?] [changed] after invalidation."""
    area = create_initial_area()
    explorer = area.get_agent()
    goblin = Agent(
        id="agent_goblin_01",
        name="Goblin",
        personality="A test goblin.",
        position=(0, 0),
        memory=Memory(),
    )
    area.add_agent(goblin)

    perform_look(explorer, area, "obj_ball_01")
    perform_look(goblin, area, "obj_ball_01")
    area.invalidate_object_knowledge("obj_ball_01")

    changed = "Ceramic Ball (obj_ball_01), (2, 2) - [?] [changed]"
    assert changed in build_passive_vision(explorer, area)
    assert changed in build_passive_vision(goblin, area)


def test_agent_who_never_looked_sees_plain_question_mark():
    """Agent who never looked still sees [?] after another agent's knowledge is invalidated."""
    area = create_initial_area()
    explorer = area.get_agent()
    goblin = Agent(
        id="agent_goblin_01",
        name="Goblin",
        personality="A test goblin.",
        position=(0, 0),
        memory=Memory(),
    )
    area.add_agent(goblin)

    perform_look(explorer, area, "obj_ball_01")
    area.invalidate_object_knowledge("obj_ball_01")

    goblin_vision = build_passive_vision(goblin, area)
    ball_line = next(
        line for line in goblin_vision.split("\n") if "obj_ball_01" in line
    )
    assert ball_line == "Ceramic Ball (obj_ball_01), (2, 2) - [?]"


def test_passive_only_object_has_no_question_mark():
    """Object with passive but no detailed description never shows [?]."""
    obj = Object(
        id="obj_scenery_01",
        name="Crack",
        description="",
        passive_description="A crack in the floor.",
        position=(0, 0),
    )
    memory = Memory()
    assert format_object_vision_desc(obj, memory) == "A crack in the floor."
    memory.mark_looked_at("obj_scenery_01")
    assert format_object_vision_desc(obj, memory) == "A crack in the floor."


def test_look_on_empty_detailed_clears_stale_examination():
    """look on object with no detailed text clears stale ever_looked state."""
    area = create_initial_area()
    agent = area.get_agent()
    obj = Object(
        id="obj_husk_01",
        name="Husk",
        description="Was something.",
        passive_description="An empty shell.",
        position=(0, 0),
    )
    area.add_object(obj)
    perform_look(agent, area, "obj_husk_01")
    obj.description = ""
    area.invalidate_object_knowledge("obj_husk_01")
    assert agent.memory.has_ever_looked_at("obj_husk_01")

    outcome = perform_look(agent, area, "obj_husk_01")
    assert "don't notice anything more" in outcome.result
    assert not agent.memory.has_ever_looked_at("obj_husk_01")
    vision = build_passive_vision(agent, area)
    assert "Husk (obj_husk_01), (0, 0) - An empty shell." in vision


def test_look_on_object_without_detailed_does_not_mark_memory():
    """look on passive-only object returns no-detail message without updating memory."""
    area = create_initial_area()
    agent = area.get_agent()
    area.add_object(
        Object(
            id="obj_scenery_01",
            name="Crack",
            description="",
            passive_description="A crack in the floor.",
            position=(1, 1),
        )
    )
    outcome = perform_look(agent, area, "obj_scenery_01")
    assert "don't notice anything more" in outcome.result
    assert not agent.memory.has_looked_at("obj_scenery_01")


def test_format_object_vision_desc_all_states():
    """format_object_vision_desc covers never, current, and stale states."""
    obj = Object(
        id="obj_test_01",
        name="Test Object",
        description="Full description here.",
        passive_description="A vague shape.",
        position=(0, 0),
    )
    memory = Memory()

    assert format_object_vision_desc(obj, memory) == "[?] A vague shape."

    memory.mark_looked_at("obj_test_01")
    assert format_object_vision_desc(obj, memory) == "Full description here."

    memory.invalidate_look("obj_test_01")
    assert (
        format_object_vision_desc(obj, memory) == "[?] [changed] A vague shape."
    )


def test_get_available_look_targets_only_question_mark_entities():
    """Look list includes only entities whose vision line shows [?]."""
    from campaign_rpg_engine.perception import get_available_look_targets

    area = create_initial_area()
    agent = area.get_agent()

    targets = get_available_look_targets(agent, area)
    assert targets == ["obj_ball_01", "obj_sign_01"]

    perform_look(agent, area, "obj_ball_01")
    assert get_available_look_targets(agent, area) == ["obj_sign_01"]

    perform_look(agent, area, "obj_sign_01")
    assert get_available_look_targets(agent, area) == []

    area.invalidate_object_knowledge("obj_ball_01")
    assert get_available_look_targets(agent, area) == ["obj_ball_01"]


def test_get_available_look_targets_excludes_passive_only_objects():
    """Objects without hidden detail ([?]) are omitted from the look list."""
    from campaign_rpg_engine.perception import get_available_look_targets

    area = create_initial_area()
    agent = area.get_agent()
    area.add_object(
        Object(
            id="obj_scenery_01",
            name="Crack",
            description="",
            passive_description="A crack in the floor.",
            position=(1, 1),
        )
    )

    targets = get_available_look_targets(agent, area)
    assert "obj_scenery_01" not in targets
    assert "obj_ball_01" in targets


def test_build_compound_prompt_look_rule_and_filtered_targets():
    from campaign_rpg_engine.llm.prompt import build_compound_prompt

    area = create_initial_area()
    agent = area.get_agent()
    prompt = build_compound_prompt(agent, area)

    assert "look: entity id with [?] in passive vision" in prompt
    assert "Passive Vision:" in prompt
    assert "interact: action" in prompt
    assert PASSIVE_VISION_LOOK_RULE in prompt
    assert "Ceramic Ball (obj_ball_01)" in prompt
    assert "  - kick (range 1)" in prompt

    perform_look(agent, area, "obj_ball_01")
    perform_look(agent, area, "obj_sign_01")
    prompt = build_compound_prompt(agent, area)
    assert PASSIVE_VISION_NO_LOOK_TARGETS in prompt


def test_reset_looked_at_clears_both_sets():
    """reset_looked_at clears both looked_at and ever_looked."""
    memory = Memory()
    memory.mark_looked_at("obj_ball_01")
    memory.mark_looked_at("obj_sign_01")

    memory.reset_looked_at()

    assert not memory.has_looked_at("obj_ball_01")
    assert not memory.has_ever_looked_at("obj_ball_01")


def test_invalidate_skips_agents_without_looked_at():
    """invalidate_object_knowledge only affects agents with current knowledge."""
    area = create_initial_area()
    agent = area.get_agent()
    assert not agent.memory.has_looked_at("obj_ball_01")

    area.invalidate_object_knowledge("obj_ball_01")

    assert not agent.memory.has_ever_looked_at("obj_ball_01")
    vision = build_passive_vision(agent, area)
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?]" in vision
