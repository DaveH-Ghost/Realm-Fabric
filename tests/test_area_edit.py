"""
test_world_edit.py

Tests for V0.1 area editing commands (Section 2).
"""

from src.object import Object
from src.perception import build_passive_vision, perform_look
from src.area import create_initial_area
from src.area_edit import (
    create_agent_from_args,
    create_object_from_args,
    delete_agent_by_id,
    delete_object_by_id,
    edit_agent_from_args,
    edit_object_from_args,
    format_agents_list,
    format_full_list,
    format_objects_list,
    generate_object_id,
    slugify_display_name,
)


def test_slugify_display_name():
    assert slugify_display_name("Ceramic Ball") == "ceramic_ball"
    assert slugify_display_name("!!!") == "new"


def test_generate_object_id_increments():
    area = create_initial_area()
    assert generate_object_id(area, "Ceramic Ball") == "obj_ceramic_ball_01"
    area.add_object(
        Object(
            id="obj_ceramic_ball_01",
            name="Ceramic Ball",
            description="",
            position=(0, 0),
        )
    )
    assert generate_object_id(area, "Ceramic Ball") == "obj_ceramic_ball_02"


def test_format_objects_list_initial_world():
    area = create_initial_area()
    text = format_objects_list(area)
    assert "Objects in area:" in text
    assert "Ceramic Ball (obj_ball_01) at (2, 2)" in text
    assert "Wooden Sign (obj_sign_01) at (2, 4)" in text


def test_format_agents_list_initial_world():
    area = create_initial_area()
    agent = area.get_agent()
    text = format_agents_list(area, agent)
    assert "Agents in area:" in text
    assert "Explorer (agent_01) at (1, 1) memory=recent_turns (active)" in text


def test_format_full_list_initial_world():
    area = create_initial_area()
    agent = area.get_agent()
    text = format_full_list(area, agent)
    assert "Agents in area:" in text
    assert "Objects in area:" in text
    assert text.index("Agents in area:") < text.index("Objects in area:")


def test_create_object_with_pdesc_shows_passive_and_question_mark():
    area = create_initial_area()
    agent = area.get_agent()
    obj, _ = create_object_from_args(
        area, 'name "Lantern" pdesc "A dim lantern." desc "It flickers." at 1,0'
    )
    assert obj.passive_description == "A dim lantern."
    vision = build_passive_vision(agent, area)
    assert "Lantern (obj_lantern_01), (1, 0) - [?] A dim lantern." in vision


def test_edit_pdesc_does_not_invalidate():
    area = create_initial_area()
    agent = area.get_agent()
    perform_look(agent, area, "obj_ball_01")
    edit_object_from_args(area, 'obj_ball_01 pdesc "A round object."')
    assert agent.memory.has_looked_at("obj_ball_01")
    vision = build_passive_vision(agent, area)
    assert "scuffs and feels light" in vision


def test_create_object_appears_in_vision_as_unknown():
    area = create_initial_area()
    agent = area.get_agent()
    obj, msg = create_object_from_args(
        area, 'name "Crate" desc "A wooden crate." at 0,0'
    )
    assert obj is not None
    assert obj.id == "obj_crate_01"
    assert "obj_crate_01" in msg
    vision = build_passive_vision(agent, area)
    assert "Crate (obj_crate_01), (0, 0) - [?]" in vision


def test_create_object_invalid_position_rejected():
    area = create_initial_area()
    before = len(area.get_objects())
    obj, msg = create_object_from_args(area, 'name "Crate" desc "x" at 9,9')
    assert obj is None
    assert "Invalid position" in msg
    assert len(area.get_objects()) == before


def test_edit_object_desc_invalidates_knowledge():
    area = create_initial_area()
    agent = area.get_agent()
    perform_look(agent, area, "obj_ball_01")
    msg = edit_object_from_args(area, 'obj_ball_01 desc "A shiny ball."')
    assert "Updated object obj_ball_01" in msg
    vision = build_passive_vision(agent, area)
    assert "[?] [changed]" in vision


def test_edit_object_pos_does_not_invalidate():
    area = create_initial_area()
    agent = area.get_agent()
    perform_look(agent, area, "obj_ball_01")
    msg = edit_object_from_args(area, "obj_ball_01 pos 3,3")
    assert "Updated object obj_ball_01" in msg
    assert agent.memory.has_looked_at("obj_ball_01")
    ball = area.get_object_by_id("obj_ball_01")
    assert ball.position == (3, 3)


def test_edit_object_sign_replaces_sign_workflow():
    area = create_initial_area()
    agent = area.get_agent()
    new_text = "Updated sign text for testing."
    perform_look(agent, area, "obj_sign_01")
    msg = edit_object_from_args(area, f'obj_sign_01 desc "{new_text}"')
    assert "Updated object obj_sign_01" in msg
    vision = build_passive_vision(agent, area)
    assert "[?] [changed] A simple wooden sign on the wall." in vision
    outcome = perform_look(agent, area, "obj_sign_01")
    assert new_text in outcome.result


def test_edit_object_rejects_display_name():
    area = create_initial_area()
    msg = edit_object_from_args(area, 'Ceramic Ball desc "nope"')
    assert "require object id" in msg


def test_delete_object_removes_from_world():
    area = create_initial_area()
    agent = area.get_agent()
    msg = delete_object_by_id(area, "obj_ball_01")
    assert "Deleted object obj_ball_01" in msg
    assert area.get_object_by_id("obj_ball_01") is None
    vision = build_passive_vision(agent, area)
    assert "obj_ball_01" not in vision


def test_two_objects_same_display_name_allowed():
    area = create_initial_area()
    obj1, _ = create_object_from_args(area, 'name "Box" desc "One" at 0,0')
    obj2, _ = create_object_from_args(area, 'name "Box" desc "Two" at 0,1')
    assert obj1 is not None and obj2 is not None
    assert obj1.id != obj2.id
    text = format_objects_list(area)
    assert "Box (obj_box_01)" in text
    assert "Box (obj_box_02)" in text


def test_create_agent_and_list():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Goblin" pdesc "A grumpy goblin." desc "Sharp-eyed goblin." '
        'personality "Grumpy inside." at 0,3',
    )
    assert agent is not None
    assert agent.id == "agent_goblin_01"
    assert "agent_goblin_01" in msg
    text = format_agents_list(area, area.get_agent())
    assert "Goblin (agent_goblin_01) at (0, 3)" in text
    assert "Explorer (agent_01)" in text
    assert "(active)" in text


def test_edit_agent_rename():
    area = create_initial_area()
    msg = edit_agent_from_args(area, 'agent_01 name "Scout"')
    assert msg.ok
    agent = area.get_agent_by_id("agent_01")
    assert agent.name == "Scout"


def test_edit_agent_rejects_display_name():
    area = create_initial_area()
    result = edit_agent_from_args(area, 'Explorer personality "nope"')
    assert not result.ok
    assert "require agent id" in result.message


def test_delete_agent_rejects_last_agent():
    area = create_initial_area()
    result = delete_agent_by_id(area, "agent_01")
    assert not result.ok
    assert "last agent" in result.message


def test_stepper_parses_hyphenated_commands():
    """cmd.Cmd must treat '-' as part of the command name, not as an argument."""
    from src.main import ManualStepper

    stepper = ManualStepper()
    cmd, arg, _ = stepper.parseline(
        'create-object name "Crate" desc "A wooden crate." at 0,0'
    )
    assert cmd == "create-object"
    assert 'name "Crate"' in arg


def test_create_agent_duplicate_name_rejected():
    area = create_initial_area()
    agent, msg = create_agent_from_args(area, 'name "Explorer" personality "x" at 0,0')
    assert agent is None
    assert "already in use" in msg


def test_create_object_case_insensitive_keywords():
    area = create_initial_area()
    obj, msg = create_object_from_args(
        area, 'NAME "Box" PDESC "A box." DESC "Inside." AT 1,1'
    )
    assert obj is not None
    assert obj.passive_description == "A box."
    assert obj.description == "Inside."


def test_parse_duplicate_field_rejected():
    area = create_initial_area()
    obj, msg = create_object_from_args(
        area, 'name "A" name "B" desc "x" at 0,0'
    )
    assert obj is None
    assert "Duplicate field" in msg


def test_edit_object_clear_desc_clears_examination_history():
    area = create_initial_area()
    agent = area.get_agent()
    perform_look(agent, area, "obj_ball_01")
    edit_object_from_args(area, 'obj_ball_01 desc ""')
    assert not agent.memory.has_looked_at("obj_ball_01")
    assert not agent.memory.has_ever_looked_at("obj_ball_01")
    vision = build_passive_vision(agent, area)
    assert "[changed]" not in vision
    assert "Ceramic Ball (obj_ball_01), (2, 2)" in vision
    assert "Ceramic Ball (obj_ball_01), (2, 2) -" not in vision


def test_empty_object_vision_line_omits_trailing_dash():
    area = create_initial_area()
    agent = area.get_agent()
    area.add_object(
        Object(
            id="obj_empty_01",
            name="Void",
            description="",
            passive_description="",
            position=(0, 0),
        )
    )
    vision = build_passive_vision(agent, area)
    assert "Void (obj_empty_01), (0, 0)" in vision
    assert "Void (obj_empty_01), (0, 0) -" not in vision


def test_stepper_sign_command_removed(capsys):
    from src.main import ManualStepper

    stepper = ManualStepper()
    assert not hasattr(stepper, "do_sign")
    stepper.onecmd("sign hello")
    assert "Unknown syntax" in capsys.readouterr().out


def test_stepper_edit_agent_rename_updates_dispatch_dict():
    from src.main import ManualStepper

    stepper = ManualStepper()
    stepper.onecmd('edit-agent agent_01 name "Scout"')
    assert "explorer" not in stepper.agents
    assert "scout" in stepper.agents
    assert stepper.agents["scout"].name == "Scout"


def test_stepper_delete_active_agent_reassigns(capsys):
    from src.main import ManualStepper

    stepper = ManualStepper()
    stepper.onecmd('create-agent name "Goblin" personality "x" at 0,0')
    goblin = stepper.area.get_agent_by_id("agent_goblin_01")
    stepper.agent = goblin
    stepper.onecmd("delete-agent agent_goblin_01")
    assert stepper.agent.id == "agent_01"
    assert "goblin" not in stepper.agents
    assert "Active agent: Explorer (agent_01)" in capsys.readouterr().out


def test_delete_non_active_agent():
    area = create_initial_area()
    create_agent_from_args(area, 'name "Goblin" personality "x" at 0,0')
    active = area.get_agent()
    result = delete_agent_by_id(area, "agent_goblin_01")
    assert result.ok
    assert area.get_agent_by_id("agent_goblin_01") is None
    assert active is area.get_agent()
