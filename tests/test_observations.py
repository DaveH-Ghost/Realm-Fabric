"""Witness broadcast for multi-step compound turns (V0.4.3c)."""

from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_agent_from_args
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.observations import observable_witness_steps
from campaign_rpg_engine.simulation import run_compound_turn
from campaign_rpg_engine.turn_record import TurnStep


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
            action="emote",
            target=goblin.id,
            verb="smiled",
            say="Hello there!",
        ),
        turn_number=1,
        session_turn=1,
    )

    memory_text = goblin.memory.render_prompt_block(goblin, area)
    assert 'Explorer says: "Hello there!"' in memory_text
    assert "[emote] Explorer smiled at you." in memory_text


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
            look="obj_ball_01",
            action="none",
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
            look="obj_ball_01",
            action="none",
            say="Hi.",
        ),
        turn_number=1,
        session_turn=1,
    )

    memory_text = explorer.memory.render_prompt_block(explorer, area)
    assert 'Goblin says: "Hi."' in memory_text
    assert "Goblin examines" not in memory_text


def test_passive_witness_exclude_agent_ids():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 1,1',
    )
    goblin = area.get_agent_by_name("Goblin")
    create_agent_from_args(
        area,
        'name "Watcher" pdesc "A watcher." desc "x" personality "x" at 2,1',
    )
    watcher = area.get_agent_by_name("Watcher")

    from campaign_rpg_engine.simulation import commit_turn_record
    from campaign_rpg_engine.turn_record import TurnRecord

    record = TurnRecord(
        turn_number=1,
        reasoning="Show.",
        result="You show the ball to Goblin.",
        steps=[
            TurnStep(
                kind="verb",
                reasoning="Show.",
                target="agent_goblin obj_ball_01",
                content="show",
                result="You show the ball to Goblin.",
                passive_result="Explorer shows Ceramic Ball to Goblin.",
                passive_witness_exclude_agent_ids=(goblin.id,),
            )
        ],
    )
    commit_turn_record(
        explorer,
        record,
        AgentCompoundTurn(reasoning="Show.", action="none"),
        area,
        session_turn=1,
    )

    goblin_memory = goblin.memory.render_prompt_block(goblin, area)
    watcher_memory = watcher.memory.render_prompt_block(watcher, area)
    assert "shows Ceramic Ball to Goblin" not in goblin_memory
    assert "shows Ceramic Ball to Goblin" in watcher_memory
