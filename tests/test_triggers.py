"""Path-step triggers (V0.6.0e)."""

from __future__ import annotations

from campaign_rpg_engine.actions.move import move as do_move
from campaign_rpg_engine.area import Area, GridBounds
from campaign_rpg_engine.area_edit import create_object_from_args
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.object import Object
from campaign_rpg_engine.object_action import ObjectAction
from campaign_rpg_engine.session import Session


def _session_with_trap_at(position: tuple[int, int], *, halt: bool = True) -> Session:
    session = Session.from_default()
    area = session.area
    trap = Object(
        id="obj_trap_01",
        name="Trap",
        description="",
        position=position,
        passive_description="",
        blocks_movement=False,
        hidden=True,
        actions={
            "trip": ObjectAction(
                name="trip",
                range=0,
                result="(trigger)",
                passive_result="{actor} steps on the trap.",
                kind="trigger",
                halt_movement=halt,
                delete_after_trigger=True,
            )
        },
    )
    area.add_object(trap)
    return session


def test_trigger_fires_on_path_step_and_halts():
    session = _session_with_trap_at((2, 0))
    agent = session.get_active_agent()
    agent.position = (0, 0)
    agent.move_speed = 4

    trigger_fired: set[tuple[str, str, str]] = set()
    outcome = do_move(
        agent,
        area=session.area,
        target="4,0",
        session=session,
        trigger_fired=trigger_fired,
    )

    assert agent.position == (2, 0)
    assert len(trigger_fired) == 1
    assert session.area.get_object_by_id("obj_trap_01") is None
    events = session.area.recent_events
    assert any("steps on the trap" in ev.text for ev in events)
    assert "toward" in outcome.result.lower() or "2,0" in outcome.result


def test_trigger_deduped_once_per_turn():
    session = _session_with_trap_at((1, 0), halt=False)
    agent = session.get_active_agent()
    agent.position = (0, 0)
    agent.move_speed = 2

    trigger_fired: set[tuple[str, str, str]] = set()
    do_move(
        agent,
        area=session.area,
        target="2,0",
        session=session,
        trigger_fired=trigger_fired,
    )
    do_move(
        agent,
        area=session.area,
        target="0,0",
        session=session,
        trigger_fired=trigger_fired,
    )

    assert len(trigger_fired) == 1


def test_trigger_exception_skips_agent():
    session = _session_with_trap_at((1, 0))
    trap = session.area.get_object_by_id("obj_trap_01")
    assert trap is not None
    trap.actions["trip"].trigger_exceptions = [session.get_active_agent().id]

    agent = session.get_active_agent()
    agent.position = (0, 0)
    agent.move_speed = 2
    trigger_fired: set[tuple[str, str, str]] = set()
    do_move(
        agent,
        area=session.area,
        target="2,0",
        session=session,
        trigger_fired=trigger_fired,
    )

    assert trap.id in {o.id for o in session.area.get_objects()}
    assert len(trigger_fired) == 0


def test_create_object_with_trigger_action_via_cli():
    area = Area(bounds=GridBounds.square(5))
    obj, msg = create_object_from_args(
        area,
        (
            'name "Plate" pdesc "A plate." at 1,1 hidden true blocks-movement false '
            'action trip range 0 kind trigger halt-movement true delete-after-trigger false '
            'result "(trigger)" passive "{actor} triggers the plate."'
        ),
    )
    assert obj is not None
    assert "trip" in obj.actions
    assert obj.actions["trip"].kind == "trigger"
    assert obj.actions["trip"].halt_movement is True
    assert obj.actions["trip"].delete_after_trigger is False
    assert "Created object" in msg


def _area_with_walker(*, move_speed: int | None = 4) -> tuple[Area, Agent, Session]:
    area = Area(bounds=GridBounds.square(6))
    from campaign_rpg_engine.area_edit import create_agent_from_args

    speed_clause = f"move-speed {move_speed}" if move_speed is not None else ""
    create_agent_from_args(
        area,
        f'name "Walker" pdesc "Walker." desc "Walker." personality "Walk." at 0,2 {speed_clause}'.strip(),
    )
    agent = area.agents[0]
    session = Session(area=area)
    return area, agent, session


def _multi_tile_zone(
    *,
    obj_id: str,
    passive: str,
    action_name: str = "cross",
) -> Object:
    return Object(
        id=obj_id,
        name="Zone",
        description="",
        position=(1, 2),
        width=3,
        height=1,
        passive_description="",
        blocks_movement=False,
        hidden=True,
        actions={
            action_name: ObjectAction(
                name=action_name,
                range=0,
                result="(trigger)",
                passive_result=passive,
                kind="trigger",
                halt_movement=False,
                delete_after_trigger=False,
            )
        },
    )


def test_multi_tile_tripwire_fires_on_footprint_tile():
    """Trigger range is Chebyshev to nearest footprint tile (multi-tile tripwires)."""
    area, agent, session = _area_with_walker(move_speed=4)
    area.add_object(
        _multi_tile_zone(
            obj_id="obj_wire_01",
            passive="{actor} crosses the tripwire.",
        )
    )

    trigger_fired: set[tuple[str, str, str]] = set()
    do_move(
        agent,
        area=area,
        target="2,2",
        session=session,
        trigger_fired=trigger_fired,
    )

    assert len(trigger_fired) == 1
    assert agent.position == (2, 2)
    assert area.get_object_by_id("obj_wire_01") is not None
    assert any("crosses the tripwire" in ev.text for ev in area.recent_events)


def test_multi_tile_tripwire_fires_with_unlimited_move():
    """Unlimited move still evaluates triggers on each tile along the path."""
    area, agent, session = _area_with_walker(move_speed=None)
    area.add_object(
        _multi_tile_zone(
            obj_id="obj_wire_02",
            passive="{actor} enters the zone.",
            action_name="enter",
        )
    )

    trigger_fired: set[tuple[str, str, str]] = set()
    do_move(
        agent,
        area=area,
        target="2,2",
        session=session,
        trigger_fired=trigger_fired,
    )

    assert len(trigger_fired) == 1
    assert agent.position == (2, 2)
    assert any("enters the zone" in ev.text for ev in area.recent_events)


def test_compound_turn_shares_trigger_dedupe():
    session = _session_with_trap_at((1, 0), halt=False)
    agent = session.get_active_agent()
    agent.position = (0, 0)
    agent.move_speed = 3

    record = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="walk",
            move="3,0",
            action="none",
        ),
    )

    assert record.ok
    assert len([ev for ev in session.area.recent_events if "trap" in ev.text.lower()]) == 1
