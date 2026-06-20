"""Witness broadcast for multi-step compound turns (V0.4.3c)."""

from src.area import create_initial_area
from src.area_edit import create_agent_from_args
from src.llm.schemas import AgentCompoundTurn
from src.observations import observable_witness_steps
from src.simulation import run_compound_turn
from src.turn_record import TurnStep


def _step(kind: str, passive: str = "", **kwargs) -> TurnStep:
    return TurnStep(
        kind=kind,
        reasoning="",
        target=kwargs.get("target"),
        content=kwargs.get("content"),
        result="",
        passive_result=passive,
    )


def test_observable_witness_steps_primary_always_included():
    steps = [
        _step("move", "Explorer moves to (2, 3)."),
        _step("look", "Explorer examines the Ball."),
        _step("speak", 'Explorer says: "Hi."'),
        _step("emote", "Explorer smiled at Goblin."),
    ]
    assert [s.kind for s in observable_witness_steps(steps)] == [
        "move",
        "speak",
        "emote",
    ]


def test_observable_witness_steps_look_only_when_idle():
    only_look = [_step("look", "Explorer examines the Ball.")]
    assert [s.kind for s in observable_witness_steps(only_look)] == ["look"]

    with_speak = [
        _step("look", "Explorer examines the Ball."),
        _step("speak", 'Explorer says: "Hi."'),
    ]
    assert [s.kind for s in observable_witness_steps(with_speak)] == ["speak"]


def test_speak_and_emote_both_witnessed():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 1,1',
    )
    goblin = area.get_agent_by_name("Goblin")

    run_compound_turn(
        explorer,
        area,
        AgentCompoundTurn(
            reasoning="Friendly.",
            turn_action="emote",
            target=goblin.id,
            action_name="smiled",
            content="Hello there!",
        ),
        turn_number=1,
        session_turn=1,
    )

    memory_text = goblin.memory.render_prompt_block(goblin, area)
    assert 'Explorer says: "Hello there!"' in memory_text
    assert "Explorer smiled at you." in memory_text


def test_look_witnessed_when_only_action():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 0,3',
    )
    goblin = area.get_agent_by_name("Goblin")

    run_compound_turn(
        goblin,
        area,
        AgentCompoundTurn(
            reasoning="Inspect.",
            look_target="obj_ball_01",
            turn_action="none",
        ),
        turn_number=1,
        session_turn=1,
    )

    memory_text = explorer.memory.render_prompt_block(explorer, area)
    assert "Goblin examines" in memory_text


def test_look_not_witnessed_when_also_speaking():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 0,3',
    )
    goblin = area.get_agent_by_name("Goblin")

    run_compound_turn(
        goblin,
        area,
        AgentCompoundTurn(
            reasoning="Chat.",
            look_target="obj_ball_01",
            turn_action="none",
            content="Hi.",
        ),
        turn_number=1,
        session_turn=1,
    )

    memory_text = explorer.memory.render_prompt_block(explorer, area)
    assert 'Goblin says: "Hi."' in memory_text
    assert "Goblin examines" not in memory_text
