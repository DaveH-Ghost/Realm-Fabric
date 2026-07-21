"""Background consolidation runner for rolling-summary memory."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from campaign_rpg_engine.llm.client import is_concurrency_limit_error
from campaign_rpg_engine.llm.memory_summary import log_consolidation_error
from campaign_rpg_engine.log_utils import exception_already_logged
from campaign_rpg_engine.memory_modules.base import WitnessedEvent
from campaign_rpg_engine.memory_modules.consolidation_hooks import notify_consolidation_failure
from campaign_rpg_engine.turn_record import TurnRecord

ConsolidationState = Literal["idle", "running", "failed"]

ConsolidationRun = Callable[["ConsolidationSnapshot"], Any]
ConsolidationSuccess = Callable[[Any, "ConsolidationSnapshot"], None]

ERROR_CODE_CONCURRENCY_LIMIT = "concurrency_limit_exceeded"


class MemoryConsolidationError(RuntimeError):
    """Raised when an agent cannot act until rolling summary consolidation succeeds."""

    def __init__(
        self,
        *,
        agent_name: str = "",
        turn_number: int | None = None,
        concurrency_limit_exceeded: bool = False,
    ) -> None:
        subject = f"Agent {agent_name!r}" if agent_name else "Agent"
        if turn_number is not None:
            subject = f"{subject} (turn {turn_number})"
        if concurrency_limit_exceeded:
            detail = (
                f"{subject} cannot act until memory summary consolidation succeeds. "
                "The last consolidation failed because the LLM provider rejected an "
                "overlapping request (concurrency limit). This often happens during "
                "background memory consolidation or affinity Call A/B. Disable "
                "Concurrent LLM calls for one-at-a-time providers, then try again."
            )
        else:
            detail = (
                f"{subject} cannot act until memory summary consolidation succeeds. "
                "Check the log for consolidation errors (API, network, or LLM response). "
                "Fix the issue and try again."
            )
        super().__init__(detail)
        self.agent_name = agent_name
        self.turn_number = turn_number
        self.concurrency_limit_exceeded = concurrency_limit_exceeded
        self.error_code = (
            ERROR_CODE_CONCURRENCY_LIMIT if concurrency_limit_exceeded else None
        )


@dataclass
class ConsolidationSnapshot:
    turns: list[TurnRecord]
    witnessed_before: list[list[WitnessedEvent]]
    agent_name: str
    turn_number: int
    previous_summary: str
    """Optional module-specific freeze data (e.g. affinity candidates)."""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsolidationRunner:
    """
    Runs consolidation work synchronously or on a daemon thread.

    States: idle → running → idle (success) or failed (retry on next ensure_ready).
    """

    _state: ConsolidationState = field(default="idle", init=False)
    _snapshot: ConsolidationSnapshot | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _last_failure_was_concurrency: bool = field(default=False, init=False)

    @property
    def state(self) -> ConsolidationState:
        return self._state

    @property
    def last_failure_was_concurrency(self) -> bool:
        return self._last_failure_was_concurrency

    def start(
        self,
        snapshot: ConsolidationSnapshot,
        *,
        background: bool,
        run: ConsolidationRun,
        on_success: ConsolidationSuccess,
        thread_name: str,
    ) -> None:
        with self._lock:
            self._snapshot = snapshot
            self._state = "running"
            self._last_failure_was_concurrency = False

        if background:
            thread = threading.Thread(
                target=self._worker,
                args=(snapshot, run, on_success),
                daemon=True,
                name=thread_name,
            )
            with self._lock:
                self._thread = thread
            thread.start()
            return

        self._worker(snapshot, run, on_success)

    def ensure_ready(
        self,
        *,
        run: ConsolidationRun,
        on_success: ConsolidationSuccess,
    ) -> None:
        """Block until idle; sync-retry if the last run failed."""
        while True:
            with self._lock:
                state = self._state

            if state == "idle":
                return

            if state == "running":
                self.wait_for_background()
                continue

            if state == "failed":
                self._retry_sync(run, on_success)
                with self._lock:
                    if self._state == "idle":
                        return
                    snapshot = self._snapshot
                    concurrency = self._last_failure_was_concurrency
                raise MemoryConsolidationError(
                    agent_name=snapshot.agent_name if snapshot else "",
                    turn_number=snapshot.turn_number if snapshot else None,
                    concurrency_limit_exceeded=concurrency,
                )

    def wait_for_background(self) -> None:
        thread = None
        with self._lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join()

    def flush_for_save(self) -> None:
        """
        Wait until consolidation is idle or failed.

        Unlike ``ensure_ready``, does not retry a failed job and never raises.
        Used before session save/checkpoint so one agent's failed consolidation
        cannot block another agent's turn undo snapshot.
        """
        while True:
            with self._lock:
                state = self._state
            if state in ("idle", "failed"):
                return
            if state == "running":
                self.wait_for_background()
                continue
            return

    def _mark_failed(self, exc: BaseException, snapshot: ConsolidationSnapshot | None) -> None:
        concurrency = is_concurrency_limit_error(exc)
        with self._lock:
            self._state = "failed"
            self._thread = None
            self._last_failure_was_concurrency = concurrency
        notify_consolidation_failure(
            agent_name=snapshot.agent_name if snapshot else "",
            turn_number=snapshot.turn_number if snapshot else None,
            concurrency_limit_exceeded=concurrency,
            message=str(exc),
            error_code="concurrency_limit_exceeded" if concurrency else None,
        )

    def _worker(
        self,
        snapshot: ConsolidationSnapshot,
        run: ConsolidationRun,
        on_success: ConsolidationSuccess,
    ) -> None:
        try:
            new_summary = run(snapshot)
        except Exception as exc:
            if not exception_already_logged(exc):
                log_consolidation_error(
                    "Memory consolidation failed",
                    exc,
                    turn_number=snapshot.turn_number,
                )
            self._mark_failed(exc, snapshot)
            return

        with self._lock:
            if self._snapshot is snapshot or self._snapshot_matches(snapshot):
                on_success(new_summary, snapshot)
                self._state = "idle"
                self._snapshot = None
                self._last_failure_was_concurrency = False
            self._thread = None

    def _retry_sync(
        self,
        run: ConsolidationRun,
        on_success: ConsolidationSuccess,
    ) -> None:
        with self._lock:
            snapshot = self._snapshot
            if snapshot is None:
                self._state = "idle"
                self._last_failure_was_concurrency = False
                return

        try:
            new_summary = run(snapshot)
        except Exception as exc:
            if not exception_already_logged(exc):
                log_consolidation_error(
                    "Memory consolidation retry failed",
                    exc,
                    turn_number=snapshot.turn_number if snapshot else 0,
                )
            self._mark_failed(exc, snapshot)
            return

        with self._lock:
            if self._snapshot is snapshot or self._snapshot_matches(snapshot):
                on_success(new_summary, snapshot)
                self._state = "idle"
                self._snapshot = None
                self._last_failure_was_concurrency = False

    def _snapshot_matches(self, snapshot: ConsolidationSnapshot) -> bool:
        if self._snapshot is None:
            return False
        return self._snapshot.turn_number == snapshot.turn_number
