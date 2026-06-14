"""D&D 5e pathing and move_speed (V0.4.0b)."""

from src.actions.move import move as do_move
from src.area import create_initial_area
from src.area_edit import create_agent_from_args, edit_agent_from_args
from src.llm.prompt import build_compound_prompt
from src.pathing import chebyshev_distance, path_step_towards, walk_towards
from src.session import Session


def test_path_step_diagonal_first():
    assert path_step_towards((0, 0), (3, 1)) == (1, 1)
    assert path_step_towards((1, 1), (3, 1)) == (2, 1)


def test_walk_towards_example_from_changelog():
    final, reached = walk_towards((0, 0), (3, 1), 2)
    assert final == (2, 1)
    assert reached is False

    final, reached = walk_towards((0, 0), (3, 1), 3)
    assert final == (3, 1)
    assert reached is True


def test_chebyshev_distance():
    assert chebyshev_distance((0, 0), (3, 1)) == 3
    assert chebyshev_distance((1, 1), (2, 2)) == 1


def test_move_speed_none_still_teleports():
    area = create_initial_area()
    agent = area.get_agent()
    assert agent.move_speed is None

    outcome = do_move(agent, area, "3,1")

    assert agent.position == (3, 1)
    assert outcome.result == "You moved to (3, 1)."
    assert "towards" not in outcome.result.lower()


def test_partial_move_towards_coordinate():
    area = create_initial_area()
    agent = area.get_agent()
    agent.move_speed = 2
    agent.position = (0, 0)

    outcome = do_move(agent, area, "3,1")

    assert agent.position == (2, 1)
    assert outcome.result == "You moved towards (3, 1)."
    assert outcome.passive_result == "Explorer moves towards (3, 1), stopping at (2, 1)."


def test_partial_move_towards_entity_reaches_in_one_diagonal():
    area = create_initial_area()
    agent = area.get_agent()
    agent.move_speed = 1
    agent.position = (1, 1)

    outcome = do_move(agent, area, "obj_ball_01")

    assert agent.position == (2, 2)
    assert outcome.result == "You moved to Ceramic Ball at (2, 2)."
    assert "towards" not in outcome.result.lower()


def test_speed_one_stops_short_of_ball_from_origin():
    area = create_initial_area()
    agent = area.get_agent()
    agent.move_speed = 1
    agent.position = (0, 0)

    outcome = do_move(agent, area, "obj_ball_01")

    assert agent.position == (1, 1)
    assert outcome.result == "You moved towards Ceramic Ball."
    assert "stopping at (1, 1)" in outcome.passive_result


def test_create_agent_with_move_speed():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Scout" personality "x" move-speed 3 at 0,0',
    )
    assert agent is not None
    assert agent.move_speed == 3
    assert "Scout" in msg


def test_edit_agent_move_speed_and_clear():
    area = create_initial_area()
    agent = area.get_agent()

    result = edit_agent_from_args(area, "agent_01 move-speed 2")
    assert result.ok
    assert agent.move_speed == 2

    result = edit_agent_from_args(area, 'agent_01 move-speed ""')
    assert result.ok
    assert agent.move_speed is None


def test_edit_agent_invalid_move_speed():
    area = create_initial_area()
    result = edit_agent_from_args(area, "agent_01 move-speed 0")
    assert not result.ok
    assert "at least 1" in result.message


def test_snapshot_includes_move_speed():
    session = Session.from_default()
    session.run_command("edit-agent agent_01 move-speed 2")
    agent = session.snapshot()["agents"][0]
    assert agent["move_speed"] == 2

    session.run_command('edit-agent agent_01 move-speed ""')
    agent = session.snapshot()["agents"][0]
    assert agent["move_speed"] is None


def test_prompt_mentions_move_speed_when_limited():
    area = create_initial_area()
    agent = area.get_agent()
    agent.move_speed = 2
    prompt = build_compound_prompt(agent, area)
    assert "move speed this turn is 2" in prompt
