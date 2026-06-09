"""
test_perception.py

Tests for V0.1 passive/detailed perception and cross-agent invalidation.
"""

from src.agent import Agent
from src.memory import Memory
from src.perception import build_passive_vision, format_object_vision_desc, perform_look
from src.object import Object
from src.world import create_initial_world


def test_initial_sign_shows_passive_not_pre_marked():
    """Sign shows passive + [?] at startup; agent has not looked at anything."""
    world = create_initial_world()
    agent = world.get_agent()

    assert not agent.memory.has_looked_at("obj_sign_01")
    assert not agent.memory.has_ever_looked_at("obj_sign_01")
    vision = build_passive_vision(agent, world)
    assert (
        "Wooden Sign (obj_sign_01), (2, 4) - [?] A simple wooden sign on the wall."
        in vision
    )


def test_ball_vision_states_never_stale_current():
    """Ball: [?] initially, detailed after look, [?] [changed] after invalidate."""
    world = create_initial_world()
    agent = world.get_agent()

    vision = build_passive_vision(agent, world)
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?]" in vision

    perform_look(agent, world, "obj_ball_01")
    vision = build_passive_vision(agent, world)
    assert "scuffs and feels light" in vision

    world.invalidate_object_knowledge("obj_ball_01")
    vision = build_passive_vision(agent, world)
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?] [changed]" in vision
    assert agent.memory.has_ever_looked_at("obj_ball_01")
    assert not agent.memory.has_looked_at("obj_ball_01")

    perform_look(agent, world, "obj_ball_01")
    vision = build_passive_vision(agent, world)
    assert "scuffs and feels light" in vision


def test_sign_stale_shows_changed_with_passive():
    """After look + desc invalidation, sign shows [?] [changed] {passive}."""
    world = create_initial_world()
    agent = world.get_agent()

    perform_look(agent, world, "obj_sign_01")
    world.invalidate_object_knowledge("obj_sign_01")
    vision = build_passive_vision(agent, world)

    assert (
        "Wooden Sign (obj_sign_01), (2, 4) - [?] [changed] A simple wooden sign on the wall."
        in vision
    )
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?]" in vision


def test_sign_description_update_look_restores_new_text():
    """After sign detailed desc changes and invalidation, look returns new text."""
    world = create_initial_world()
    agent = world.get_agent()
    new_text = "Brand new sign text for testing."

    perform_look(agent, world, "obj_sign_01")
    sign = world.get_object_by_id("obj_sign_01")
    sign.description = new_text
    world.invalidate_object_knowledge("obj_sign_01")

    vision = build_passive_vision(agent, world)
    assert "[?] [changed] A simple wooden sign on the wall." in vision

    outcome = perform_look(agent, world, "obj_sign_01")
    assert new_text in outcome.result
    assert agent.memory.has_looked_at("obj_sign_01")

    vision = build_passive_vision(agent, world)
    assert new_text in vision


def test_invalidate_object_knowledge_affects_all_agents_who_looked():
    """Both agents who looked at the ball see [?] [changed] after invalidation."""
    world = create_initial_world()
    explorer = world.get_agent()
    goblin = Agent(
        id="agent_goblin_01",
        name="Goblin",
        personality="A test goblin.",
        position=(0, 0),
        memory=Memory(),
    )
    world.add_agent(goblin)

    perform_look(explorer, world, "obj_ball_01")
    perform_look(goblin, world, "obj_ball_01")
    world.invalidate_object_knowledge("obj_ball_01")

    changed = "Ceramic Ball (obj_ball_01), (2, 2) - [?] [changed]"
    assert changed in build_passive_vision(explorer, world)
    assert changed in build_passive_vision(goblin, world)


def test_agent_who_never_looked_sees_plain_question_mark():
    """Agent who never looked still sees [?] after another agent's knowledge is invalidated."""
    world = create_initial_world()
    explorer = world.get_agent()
    goblin = Agent(
        id="agent_goblin_01",
        name="Goblin",
        personality="A test goblin.",
        position=(0, 0),
        memory=Memory(),
    )
    world.add_agent(goblin)

    perform_look(explorer, world, "obj_ball_01")
    world.invalidate_object_knowledge("obj_ball_01")

    goblin_vision = build_passive_vision(goblin, world)
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
    world = create_initial_world()
    agent = world.get_agent()
    obj = Object(
        id="obj_husk_01",
        name="Husk",
        description="Was something.",
        passive_description="An empty shell.",
        position=(0, 0),
    )
    world.add_object(obj)
    perform_look(agent, world, "obj_husk_01")
    obj.description = ""
    world.invalidate_object_knowledge("obj_husk_01")
    assert agent.memory.has_ever_looked_at("obj_husk_01")

    outcome = perform_look(agent, world, "obj_husk_01")
    assert "don't notice anything more" in outcome.result
    assert not agent.memory.has_ever_looked_at("obj_husk_01")
    vision = build_passive_vision(agent, world)
    assert "Husk (obj_husk_01), (0, 0) - An empty shell." in vision


def test_look_on_object_without_detailed_does_not_mark_memory():
    """look on passive-only object returns no-detail message without updating memory."""
    world = create_initial_world()
    agent = world.get_agent()
    world.add_object(
        Object(
            id="obj_scenery_01",
            name="Crack",
            description="",
            passive_description="A crack in the floor.",
            position=(1, 1),
        )
    )
    outcome = perform_look(agent, world, "obj_scenery_01")
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
    from src.perception import get_available_look_targets

    world = create_initial_world()
    agent = world.get_agent()

    targets = get_available_look_targets(agent, world)
    assert targets == ["obj_ball_01", "obj_sign_01"]

    perform_look(agent, world, "obj_ball_01")
    assert get_available_look_targets(agent, world) == ["obj_sign_01"]

    perform_look(agent, world, "obj_sign_01")
    assert get_available_look_targets(agent, world) == []

    world.invalidate_object_knowledge("obj_ball_01")
    assert get_available_look_targets(agent, world) == ["obj_ball_01"]


def test_get_available_look_targets_excludes_passive_only_objects():
    """Objects without hidden detail ([?]) are omitted from the look list."""
    from src.perception import get_available_look_targets

    world = create_initial_world()
    agent = world.get_agent()
    world.add_object(
        Object(
            id="obj_scenery_01",
            name="Crack",
            description="",
            passive_description="A crack in the floor.",
            position=(1, 1),
        )
    )

    targets = get_available_look_targets(agent, world)
    assert "obj_scenery_01" not in targets
    assert "obj_ball_01" in targets


def test_build_compound_prompt_look_rule_and_filtered_targets():
    from src.llm.prompt import build_compound_prompt

    world = create_initial_world()
    agent = world.get_agent()
    prompt = build_compound_prompt(agent, world)

    assert (
        "look: optional; a list of objects you can look at will be provided."
        in prompt
    )
    assert "You can look at: obj_ball_01, obj_sign_01" in prompt

    perform_look(agent, world, "obj_ball_01")
    perform_look(agent, world, "obj_sign_01")
    prompt = build_compound_prompt(agent, world)
    assert "You can look at: (nothing visible to examine)" in prompt


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
    world = create_initial_world()
    agent = world.get_agent()
    assert not agent.memory.has_looked_at("obj_ball_01")

    world.invalidate_object_knowledge("obj_ball_01")

    assert not agent.memory.has_ever_looked_at("obj_ball_01")
    vision = build_passive_vision(agent, world)
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?]" in vision
