"""Background consolidation runner for rolling-summary memory."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Literal

from campaign_rpg_engine.llm.memory_summary import log_consolidation_error
from campaign_rpg_engine.memory_modules.base import WitnessedEvent
from campaign_rpg_engine.turn_record import TurnRecord

ConsolidationState = Literal["idle", "running", "failed"]

ConsolidationRun = Callable[["ConsolidationSnapshot"], str]
ConsolidationSuccess = Callable[[str, "ConsolidationSnapshot"], None]


class MemoryConsolidationError(RuntimeError):
    """Raised when an agent cannot act until rolling summary consolidation succeeds."""

    def __init__(
        self,
        *,
        agent_name: str = "",
        turn_number: int | None = None,
    ) -> None:
        subject = f"Agent {agent_name!r}" if agent_name else "Agent"
        if turn_number is not None:
            subject = f"{subject} (turn {turn_number})"
        super().__init__(
            f"{subject} cannot act until memory summary consolidation succeeds. "
            "Check the log for consolidation errors (API, network, or LLM response). "
            "Fix the issue and try again."
        )
        self.agent_name = agent_name
        self.turn_number = turn_number


@dataclass
class ConsolidationSnapshot:
    turns: list[TurnRecord]
    witnessed_before: list[list[WitnessedEvent]]
    agent_name: str
    turn_number: int
    previous_summary: str


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

    @property
    def state(self) -> ConsolidationState:
        return self._state

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
                raise MemoryConsolidationError(
                    agent_name=snapshot.agent_name if snapshot else "",
                    turn_number=snapshot.turn_number if snapshot else None,
                )

    def wait_for_background(self) -> None:
        thread = None
        with self._lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join()

    def _worker(
        self,
        snapshot: ConsolidationSnapshot,
        run: ConsolidationRun,
        on_success: ConsolidationSuccess,
    ) -> None:
        try:
            new_summary = run(snapshot)
        except Exception as exc:
            log_consolidation_error("Rolling summary consolidation failed", exc)
            with self._lock:
                self._state = "failed"
                self._thread = None
            return

        with self._lock:
            if self._snapshot is snapshot or self._snapshot_matches(snapshot):
                on_success(new_summary, snapshot)
                self._state = "idle"
                self._snapshot = None
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
                return

        try:
            new_summary = run(snapshot)
        except Exception as exc:
            log_consolidation_error("Rolling summary consolidation retry failed", exc)
            with self._lock:
                self._state = "failed"
            return

        with self._lock:
            if self._snapshot is snapshot or self._snapshot_matches(snapshot):
                on_success(new_summary, snapshot)
                self._state = "idle"
                self._snapshot = None

    def _snapshot_matches(self, snapshot: ConsolidationSnapshot) -> bool:
        if self._snapshot is None:
            return False
        return self._snapshot.turn_number == snapshot.turn_number
