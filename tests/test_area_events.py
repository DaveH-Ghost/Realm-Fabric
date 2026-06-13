"""Area-wide GM/narrator events (V0.3.2a)."""

from src.area import create_initial_area
from src.area_event import DEFAULT_MAX_RECENT_AREA_EVENTS
from src.perception import build_passive_vision
from src.session import Session


def test_emit_area_event_not_in_passive_vision():
    session = Session.from_default()
    agent = session.get_active_agent()

    result = session.emit_area_event("Thunder rumbles overhead.")
    assert result.ok

    vision = build_passive_vision(agent, session.area)
    assert "Thunder rumbles overhead." not in vision
    assert "Recent events:" not in vision


def test_emit_area_event_does_not_increment_session_turn():
    session = Session.from_default()
    assert session.session_turn == 0

    session.emit_area_event("A bell tolls.")
    assert session.session_turn == 0


def test_emit_area_event_ingests_memory_for_all_agents():
    session = Session.from_default()
    session.run_command(
        'create-agent name "Goblin" personality "Grumpy." at 0,0'
    )
    explorer = session.get_agent("Explorer")
    goblin = session.get_agent("Goblin")
    assert explorer is not None and goblin is not None

    session.emit_area_event("The lights flicker.")

    for agent in (explorer, goblin):
        memory_text = agent.memory.render_prompt_block(agent, session.area)
        assert "The lights flicker." in memory_text


def test_emit_area_event_via_run_command():
    session = Session.from_default()
    result = session.run_command('emit-event "Wind howls through the room."')
    assert result.ok
    assert "Wind howls" in result.message

    snap = session.snapshot()
    assert snap["recent_events"] == [
        {"session_turn": 0, "text": "Wind howls through the room."}
    ]


def test_emit_area_event_empty_text_fails():
    session = Session.from_default()
    result = session.emit_area_event("   ")
    assert not result.ok

    result = session.run_command("emit-event")
    assert not result.ok


def test_recent_events_ring_buffer():
    session = Session.from_default()
    for i in range(DEFAULT_MAX_RECENT_AREA_EVENTS + 2):
        session.emit_area_event(f"Event {i}.")

    texts = [event.text for event in session.area.recent_events]
    assert len(texts) == DEFAULT_MAX_RECENT_AREA_EVENTS
    assert texts[0] == "Event 2."
    assert texts[-1] == "Event 6."


def test_snapshot_includes_recent_events():
    session = Session.from_default()
    session.emit_area_event("A door slams shut.")

    snap = session.snapshot()
    assert snap["recent_events"] == [
        {"session_turn": 0, "text": "A door slams shut."}
    ]


def test_multi_agent_passive_vision_omits_area_events():
    area = create_initial_area()
    session = Session(area)
    session.run_command(
        'create-agent name "Goblin" personality "Grumpy." at 0,0'
    )
    explorer = session.get_agent("Explorer")
    goblin = session.get_agent("Goblin")
    assert explorer is not None and goblin is not None

    session.emit_area_event("Rain taps the roof.")

    assert "Rain taps the roof." not in build_passive_vision(explorer, area)
    assert "Rain taps the roof." not in build_passive_vision(goblin, area)
