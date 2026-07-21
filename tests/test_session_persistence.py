"""Session save/load round-trip (V0.4.5)."""

import json

import pytest
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from campaign_rpg_engine.memory_modules.registry import export_module_state, restore_module_state
from campaign_rpg_engine.memory_modules.rolling_summary import RollingSummaryModule
from campaign_rpg_engine.memory_modules.salient_turns import SalientTurnsModule
from campaign_rpg_engine.prompt_blocks import PromptBlock
from campaign_rpg_engine.session import Session
from campaign_rpg_engine.session_persistence import (
    SNAPSHOT_VERSION,
    build_save_snapshot,
    load_session_from_snapshot,
)
from campaign_rpg_engine.snapshot import DEFAULT_AREA_ID
from campaign_rpg_engine.turn_record import TurnRecord, TurnStep


def _speak_turn(turn_number: int, *, content: str = "Hi.") -> TurnRecord:
    return TurnRecord(
        turn_number=turn_number,
        steps=[
            TurnStep(
                kind="speak",
                reasoning=f"reason-{turn_number}",
                target=None,
                content=content,
                result=f'You said: "{content}"',
            )
        ],
        result=f'You said: "{content}"',
        reasoning=f"reason-{turn_number}",
    )


def _two_area_session() -> Session:
    room = Area(area_description="The main room.")
    hall = Area(area_description="A narrow hall.")
    room.add_agent(
        Agent(
            id="agent_01",
            name="Explorer",
            position=(1, 1),
            personality="Curious.",
        )
    )
    hall.add_agent(
        Agent(
            id="agent_02",
            name="Guard",
            position=(0, 0),
            personality="Alert.",
        )
    )
    return Session(
        areas={"room": room, "hall": hall},
        active_area_id="room",
        agent_area={"agent_01": "room", "agent_02": "hall"},
        active_agent_id="agent_01",
    )


def test_default_session_round_trip():
    session = Session.from_default()
    restored = Session.from_snapshot(build_save_snapshot(session))
    snap = restored.snapshot(include_private=True)
    room = snap["areas"][DEFAULT_AREA_ID]
    assert room["grid"] == {"min_x": 0, "max_x": 4, "min_y": 0, "max_y": 4}
    assert snap["active_agent_id"] == "agent_01"
    assert len(snap["agents"]) == 1
    assert len(room["objects"]) == 2


def test_save_snapshot_is_json_serializable():
    session = Session.from_default()
    text = json.dumps(build_save_snapshot(session))
    loaded = json.loads(text)
    assert loaded["snapshot_version"] == SNAPSHOT_VERSION


def test_multi_area_round_trip():
    session = _two_area_session()
    session.session_turn = 3
    restored = Session.from_snapshot(build_save_snapshot(session))
    assert restored.session_turn == 3
    assert set(restored.areas) == {"room", "hall"}
    assert restored.agent_area["agent_02"] == "hall"
    assert restored.get_agent("Guard") is not None


def test_look_knowledge_round_trip():
    session = Session.from_default()
    agent = session.get_active_agent()
    agent.memory.mark_looked_at("obj_ball_01")
    restored = Session.from_snapshot(build_save_snapshot(session))
    memory = restored.get_active_agent().memory
    assert "obj_ball_01" in memory.looked_at
    assert "obj_ball_01" in memory.ever_looked


def test_custom_prompt_blocks_round_trip():
    session = Session.from_default()
    blocks = [
        PromptBlock(type="slot", name="character"),
        PromptBlock(type="text", content="\n\nCustom tail.\n"),
    ]
    session.set_prompt_blocks(blocks)
    restored = Session.from_snapshot(build_save_snapshot(session))
    assert not restored.prompt_blocks_use_default()
    restored_blocks = restored.get_prompt_blocks()
    assert len(restored_blocks) == 2
    assert restored_blocks[1].content == "\n\nCustom tail.\n"


def test_vision_units_round_trip():
    session = Session.from_default()
    session.vision_units = "ft"
    session.vision_units_per_tile = 5
    restored = Session.from_snapshot(build_save_snapshot(session))
    assert restored.vision_units == "ft"
    assert restored.vision_units_per_tile == 5


def test_include_examples_round_trip():
    session = Session.from_default(include_examples=True)
    restored = Session.from_snapshot(build_save_snapshot(session))
    assert restored.include_examples is True


def test_recent_turns_memory_render_matches():
    session = Session.from_default()
    agent = session.get_active_agent()
    agent.memory.record_turn(_speak_turn(1), agent_id=agent.id, agent_name=agent.name)
    before = agent.memory.render_prompt_block(agent, session.get_area_for_agent(agent))
    restored = Session.from_snapshot(build_save_snapshot(session))
    r_agent = restored.get_active_agent()
    after = r_agent.memory.render_prompt_block(r_agent, restored.get_area_for_agent(r_agent))
    assert after == before


def test_salient_turns_storage_survives_budget_trim():
    module = SalientTurnsModule(char_budget=200, storage_window=20)
    ctx = MemoryRecordContext(agent_id="a1", turn_number=1, agent_name="A")
    for n in range(1, 6):
        module.record_turn(_speak_turn(n, content=f"Line {n}."), ctx)
    render_ctx = MemoryRenderContext(
        agent=Agent(id="a1", name="A", personality="", position=(0, 0)),
        area=Area(),
    )
    rendered = module.render(render_ctx)
    assert "earlier memories omitted" in rendered.lower() or len(rendered) < 500
    state = export_module_state(module)
    fresh = SalientTurnsModule()
    restore_module_state(fresh, state)
    assert len(fresh.stored_turns) == 5
    assert fresh.total_turns == 5


def test_save_snapshot_succeeds_when_agent_consolidation_failed():
    """Undo/checkpoint must not raise when an agent has a failed consolidation."""
    from campaign_rpg_engine.memory import Memory

    session = Session.from_default()
    agent = session.get_active_agent()

    def always_fail(**kwargs):
        raise RuntimeError("consolidation boom")

    module = RollingSummaryModule(
        summary_interval=2,
        summary_tail=0,
        background_consolidation=False,
        _summary_generator=always_fail,
    )
    agent.memory = Memory(module=module)
    ctx = MemoryRecordContext(agent_id=agent.id, turn_number=1, agent_name=agent.name)
    module.record_turn(_speak_turn(1), ctx)
    module.record_turn(_speak_turn(2), ctx)
    assert module.consolidation_state == "failed"

    data = build_save_snapshot(session)
    assert data["snapshot_version"] == SNAPSHOT_VERSION
    assert module.consolidation_state == "failed"


def test_rolling_summary_summary_and_pending_round_trip():
    module = RollingSummaryModule(
        summary_interval=2,
        summary_tail=0,
        background_consolidation=False,
        _summary_generator=lambda **kwargs: "Saved summary text.",
    )
    ctx = MemoryRecordContext(agent_id="a1", turn_number=1, agent_name="A")
    module.record_turn(_speak_turn(1), ctx)
    module.record_turn(_speak_turn(2), ctx)
    module.record_observation(
        WitnessedEvent(
            session_turn=2,
            actor_id="agent_02",
            actor_name="Other",
            text="Other waves.",
            actor_position=(2, 2),
        ),
        MemoryObserveContext(observer_id="a1"),
    )
    state = export_module_state(module)
    fresh = RollingSummaryModule(background_consolidation=False)
    restore_module_state(fresh, state)
    assert fresh.summary == "Saved summary text."
    assert fresh.last_summarized_turn_number == 2
    assert fresh.consolidation_state == "idle"
    render_ctx = MemoryRenderContext(
        agent=Agent(id="a1", name="A", personality="", position=(0, 0)),
        area=Area(),
    )
    text = fresh.render(render_ctx)
    assert "Saved summary text." in text
    assert "Other waves." in text


def test_unsupported_snapshot_version_raises():
    session = Session.from_default()
    data = build_save_snapshot(session)
    data["snapshot_version"] = 99
    with pytest.raises(ValueError, match="Unsupported snapshot_version"):
        load_session_from_snapshot(data)


def test_unknown_profile_raises():
    session = Session.from_default()
    data = build_save_snapshot(session)
    data["profile_id"] = "nonexistent_profile_xyz"
    with pytest.raises(Exception):
        load_session_from_snapshot(data)


def test_import_fails_when_memory_module_unknown():
    session = Session.from_default()
    data = build_save_snapshot(session)
    # Force an unknown module id onto an agent in the snapshot.
    agents = data.get("agents") or []
    assert agents
    agents[0]["memory"] = {
        "module_id": "rolling_summary_custom",
        "module_state": {},
        "looked_at": [],
        "ever_looked": [],
    }

    with pytest.raises(ValueError, match="rolling_summary_custom"):
        load_session_from_snapshot(data)


def test_validate_snapshot_modules_helper():
    from campaign_rpg_engine.session_persistence import validate_snapshot_modules

    with pytest.raises(ValueError, match="unsupported memory module"):
        validate_snapshot_modules(
            {
                "agents": [
                    {"memory": {"module_id": "missing_custom_module"}},
                ]
            }
        )


def test_v1_snapshot_import_has_empty_lorebooks():
    session = Session.from_default()
    data = build_save_snapshot(session)
    data["snapshot_version"] = 1
    data.pop("lorebooks", None)
    restored = load_session_from_snapshot(data)
    assert restored.list_lorebooks() == []


def test_lorebook_round_trip_in_v2_snapshot():
    from campaign_rpg_engine.lorebook import load_lorebook_from_dict

    session = Session.from_default()
    book = load_lorebook_from_dict(
        {
            "entries": {
                "0": {
                    "uid": 0,
                    "key": ["test"],
                    "content": "Lore content.",
                    "constant": True,
                    "disable": False,
                    "order": 0,
                }
            }
        },
        filename="demo.lorebook.json",
    )
    session.update_lorebook(book)
    restored = Session.from_snapshot(build_save_snapshot(session))
    loaded = restored.get_lorebook("demo")
    assert loaded is not None
    assert loaded.entries[0].content == "Lore content."
    assert restored.lorebook_char_budget == session.lorebook_char_budget


def test_session_to_save_dict_alias():
    session = Session.from_default()
    assert session.to_save_dict()["snapshot_version"] == SNAPSHOT_VERSION
