"""Prove another agent can act while a peer's background consolidation is in flight."""

from __future__ import annotations

import threading

from campaign_rpg_engine.llm.client import set_concurrent_llm_calls
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.memory_modules.rolling_summary import RollingSummaryModule
from campaign_rpg_engine.session import Session
from campaign_rpg_engine.session_persistence import build_save_snapshot


def _blocking_summary(started: threading.Event, release: threading.Event, text: str):
    def _gen(**kwargs):
        started.set()
        assert release.wait(timeout=5.0), "consolidation was never released"
        return text

    return _gen


def test_second_agent_turn_ok_while_first_agent_consolidates_in_background():
    """
    With concurrent LLM calls on, agent A's rolling-summary consolidation runs in
    the background after A's turn. Agent B must still complete a turn while that
    job is in flight; afterward A's consolidation finishes cleanly.
    """
    set_concurrent_llm_calls(True)
    try:
        session = Session.from_default()
        agent_a = session.get_active_agent()

        started = threading.Event()
        release = threading.Event()
        module_a = RollingSummaryModule(
            summary_interval=2,
            summary_tail=0,
            background_consolidation=True,
            _summary_generator=_blocking_summary(started, release, "A summary"),
        )
        agent_a.memory = Memory(module=module_a)

        created = session.create_agent(
            name="Second",
            position=(3, 3),
            personality="tester",
            is_player=False,
        )
        assert created.ok and created.agent is not None
        agent_b = created.agent

        assert session.run_compound_turn(
            AgentCompoundTurn(reasoning="a1", action="none", say="one"),
            agent_id=agent_a.id,
        ).ok
        assert session.run_compound_turn(
            AgentCompoundTurn(reasoning="a2", action="none", say="two"),
            agent_id=agent_a.id,
        ).ok

        assert started.wait(timeout=2.0)
        assert module_a.consolidation_state == "running"

        result_b = session.run_compound_turn(
            AgentCompoundTurn(reasoning="b1", action="none", say="hello from B"),
            agent_id=agent_b.id,
        )
        assert result_b.ok, result_b.message
        assert agent_b.memory.turn_count == 1
        # Still consolidating — peer turn did not need to wait for A.
        assert module_a.consolidation_state == "running"

        release.set()
        agent_a.memory.ensure_ready_for_turn()
        assert module_a.consolidation_state == "idle"
        assert module_a.summary == "A summary"
        assert session.gate_agent_turn(agent_a.id).ok

        snap = build_save_snapshot(session)
        assert snap["session_turn"] >= 3
    finally:
        set_concurrent_llm_calls(True)
