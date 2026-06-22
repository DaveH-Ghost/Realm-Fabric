"""ManualStepper CLI: intro, help, state, and LLM turn logging."""

from src.main import ManualStepper


def test_stepper_intro_documents_key_commands():
    intro = ManualStepper.intro
    assert "step-compound" in intro
    assert "effects" in intro
    assert "memory-modules" in intro
    assert "run" in intro


def test_help_step_compound_documents_usage(capsys):
    stepper = ManualStepper()
    stepper.onecmd("help step-compound")
    out = capsys.readouterr().out
    assert "step-compound" in out.lower()
    assert "interact" in out.lower()


def test_state_shows_step_breakdown_after_compound_turn(capsys):
    stepper = ManualStepper()
    stepper.onecmd("step-compound 2,3 speak Hello.")
    stepper.onecmd("state")
    out = capsys.readouterr().out
    assert "Last turn" in out
    assert "steps:" in out
    assert "[move]" in out or "move" in out
    assert "Composite result:" in out


def test_stepper_delegates_to_session():
    from src.main import ManualStepper
    from src.session import Session

    stepper = ManualStepper()
    assert isinstance(stepper.session, Session)
    assert stepper.area is stepper.session.area
    assert stepper.agent is stepper.session.get_active_agent()


def test_run_logs_single_compound_phase(monkeypatch):
    from src.llm.types import LLMResponse
    from src.llm.schemas import AgentCompoundTurn

    logged_phases = []

    def fake_log_turn(_turn_number, *, phase=None, **kwargs):
        if phase:
            logged_phases.append(phase)

    def fake_compound(_prompt):
        return LLMResponse(
            parsed=AgentCompoundTurn(
                reasoning="stay and speak",
                move=None,
                action="none",
                say="Hi.",
            ),
            raw_response="{}",
        )

    monkeypatch.setattr("src.main.log_turn", fake_log_turn)
    monkeypatch.setattr("src.llm.client.get_compound_turn", fake_compound)

    stepper = ManualStepper()
    stepper._run_llm_turn_for_agent(stepper.agent)

    assert logged_phases == ["compound"]
