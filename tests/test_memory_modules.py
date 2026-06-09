"""Tests for pluggable memory modules (recent_turns default)."""

from src.llm.prompt import build_compound_prompt
from src.llm.schemas import AgentCompoundTurn
from src.memory import Memory, TurnRecord, TurnStep
from src.memory_modules.base import WitnessedEvent
from src.memory_modules.recent_turns import RecentTurnsModule
from src.simulation import next_turn_number_for_agent, run_compound_turn
from src.world import create_initial_world
from src.world_edit import create_agent_from_args


def _turn(turn_number: int, *, reasoning: str = "thoughts") -> TurnRecord:
    return TurnRecord(
        turn_number=turn_number,
        steps=[
            TurnStep(
                kind="speak",
                reasoning=reasoning,
                target=None,
                content="Hi.",
                result='You said: "Hi."',
            )
        ],
        result='You said: "Hi."',
        reasoning=reasoning,
    )


def test_recent_turns_renders_empty_as_blank():
    module = RecentTurnsModule()
    assert module.render(_render_ctx()) == ""


def test_memory_facade_empty_prompt_block():
    world = create_initial_world()
    agent = world.get_agent()
    assert agent.memory.render_prompt_block(agent, world) == "No memories yet."


def test_recent_turns_records_and_renders_own_turn():
    module = RecentTurnsModule()
    module.record_turn(_turn(1), _record_ctx("agent_01", 1))
    text = module.render(_render_ctx())
    assert "Turn 1:" in text
    assert "Reasoning: thoughts" in text
    assert "Result:" in text
    assert 'You said: "Hi."' in text
    assert "  - speak" not in text


def test_reasoning_drops_after_third_newest_turn():
    module = RecentTurnsModule()
    for i in range(1, 6):
        module.record_turn(_turn(i, reasoning=f"reason-{i}"), _record_ctx("agent_01", i))

    text = module.render(_render_ctx())
    assert "Reasoning: reason-3" in text
    assert "Reasoning: reason-5" in text
    assert "Reasoning: reason-1" not in text
    assert "Reasoning: reason-2" not in text


def test_recent_turns_window_caps_at_ten():
    module = RecentTurnsModule(window=10)
    for i in range(1, 13):
        module.record_turn(_turn(i, reasoning=f"t{i}"), _record_ctx("agent_01", i))
    assert module.total_turns == 12
    assert len(module.stored_turns) == 10
    assert module.stored_turns[0].turn_number == 3
    rendered = module.render(_render_ctx())
    assert "Turn 3:" in rendered
    assert "Turn 1:" not in rendered


def test_witnessed_events_show_before_next_own_turn():
    module = RecentTurnsModule()
    module.record_turn(_turn(1), _record_ctx("agent_01", 1))
    module.record_observation(_witness_event("Goblin says hi."), _observe_ctx("agent_01"))
    module.record_turn(_turn(2), _record_ctx("agent_01", 2))

    text = module.render(_render_ctx())
    assert "Before turn 2, you observed:" in text
    assert "Goblin says hi." in text
    assert text.index("Before turn 2") < text.index("Turn 2:")


def test_pending_witnesses_show_since_last_turn():
    module = RecentTurnsModule()
    module.record_turn(_turn(1), _record_ctx("agent_01", 1))
    module.record_observation(_witness_event("Goblin waves."), _observe_ctx("agent_01"))

    text = module.render(_render_ctx())
    assert "Since turn 1, you observed:" in text
    assert "Goblin waves." in text


def test_prompt_uses_memory_section():
    world = create_initial_world()
    agent = world.get_agent()
    run_compound_turn(
        agent,
        world,
        AgentCompoundTurn(reasoning="x", turn_action="speak", content="Hello."),
        turn_number=1,
    )
    prompt = build_compound_prompt(agent, world)
    assert "Memory:" in prompt
    assert "Recent history:" not in prompt
    assert "Turn 1:" in prompt


def test_multi_agent_witness_ingested_into_observer_memory():
    world = create_initial_world()
    explorer = world.get_agent()
    create_agent_from_args(
        world,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 0,3',
    )
    goblin = world.get_agent_by_name("Goblin")

    run_compound_turn(
        explorer,
        world,
        AgentCompoundTurn(reasoning="intro", turn_action="speak", content="Hello."),
        turn_number=1,
        session_turn=1,
    )
    run_compound_turn(
        goblin,
        world,
        AgentCompoundTurn(reasoning="reply", turn_action="speak", content="Hi back."),
        turn_number=1,
        session_turn=2,
    )

    memory_text = explorer.memory.render_prompt_block(explorer, world)
    assert 'Goblin says: "Hi back."' in memory_text
    assert "Since turn 1, you observed:" in memory_text


def test_actor_does_not_witness_own_action():
    world = create_initial_world()
    agent = world.get_agent()
    run_compound_turn(
        agent,
        world,
        AgentCompoundTurn(reasoning="solo", turn_action="speak", content="Alone."),
        turn_number=1,
    )
    memory_text = agent.memory.render_prompt_block(agent, world)
    assert "Since turn" not in memory_text
    assert 'Explorer says: "Alone."' not in memory_text.split("Turn 1:")[0]


def test_turn_count_uses_total_not_window_size():
    world = create_initial_world()
    agent = world.get_agent()
    for i in range(1, 12):
        run_compound_turn(
            agent,
            world,
            AgentCompoundTurn(reasoning="x", turn_action="none"),
            turn_number=i,
        )
    assert agent.memory.turn_count == 11
    assert len(agent.memory.turns) == 10
    assert next_turn_number_for_agent(agent) == 12


def _record_ctx(agent_id: str, turn_number: int):
    from src.memory_modules.base import MemoryRecordContext

    return MemoryRecordContext(agent_id=agent_id, turn_number=turn_number)


def _observe_ctx(observer_id: str):
    from src.memory_modules.base import MemoryObserveContext

    return MemoryObserveContext(observer_id=observer_id)


def _render_ctx():
    from src.memory_modules.base import MemoryRenderContext

    world = create_initial_world()
    return MemoryRenderContext(agent=world.get_agent(), world=world)


def _witness_event(text: str) -> WitnessedEvent:
    return WitnessedEvent(
        session_turn=1,
        actor_id="agent_goblin_01",
        actor_name="Goblin",
        text=text,
        actor_position=(0, 3),
    )


def test_create_agent_with_explicit_memory_module():
    world = create_initial_world()
    agent, msg = create_agent_from_args(
        world,
        'name "Scribe" personality "Quiet." memory recent_turns at 2,2',
    )
    assert agent is not None
    assert agent.memory.module_id == "recent_turns"
    assert "memory=recent_turns" in msg


def test_create_agent_unknown_memory_module_rejected():
    world = create_initial_world()
    agent, msg = create_agent_from_args(
        world,
        'name "Scribe" personality "Quiet." memory summarizing at 2,2',
    )
    assert agent is None
    assert "Unknown memory module" in msg
    assert "recent_turns" in msg


def test_known_module_ids_lists_recent_turns():
    from src.memory_modules.registry import known_module_ids

    ids = known_module_ids()
    assert "recent_turns" in ids
    assert "salient_turns" in ids


def test_format_memory_modules_list():
    from src.memory_modules.registry import format_memory_modules_list

    text = format_memory_modules_list()
    assert "recent_turns" in text
    assert "salient_turns" in text


def test_agents_list_shows_memory_module():
    world = create_initial_world()
    create_agent_from_args(
        world,
        'name "Scribe" personality "x" memory recent_turns at 0,0',
    )
    from src.world_edit import format_agents_list

    text = format_agents_list(world, world.get_agent())
    assert "memory=recent_turns" in text


def test_default_memory_module_is_recent_turns():
    memory = Memory()
    assert memory.module_id == "recent_turns"
