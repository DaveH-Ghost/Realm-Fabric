"""Salient-turns memory — retain important turns, render under a character budget."""

from __future__ import annotations

from dataclasses import dataclass, field

from campaign_rpg_engine.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from campaign_rpg_engine.memory_modules.formatting import (
    WITNESS_SALIENCE,
    format_own_turn,
    format_witnessed_events,
    join_lines,
    join_step_results,
    select_salient_steps,
    should_include_reasoning,
    step_salience,
)
from campaign_rpg_engine.memory_modules.serialization import (
    deserialize_turn_list,
    deserialize_witness_list,
    deserialize_witnessed_before,
    serialize_turn_list,
    serialize_witness_list,
    serialize_witnessed_before,
)
from campaign_rpg_engine.turn_record import TurnRecord

DEFAULT_CHAR_BUDGET = 2500
MIN_CHAR_BUDGET = 200
MAX_CHAR_BUDGET = 8000
DEFAULT_STORAGE_WINDOW = 50
DEFAULT_RECENCY_FLOOR = 2

OMISSION_LINE = "…earlier memories omitted."


def validate_char_budget(value: int) -> None:
    if value < MIN_CHAR_BUDGET or value > MAX_CHAR_BUDGET:
        raise ValueError(
            f"memory-budget must be between {MIN_CHAR_BUDGET} and {MAX_CHAR_BUDGET} (got {value})."
        )


def storage_salience(turn: TurnRecord) -> int:
    """Peak step salience for storage eviction (move-only turns score lowest)."""
    if not turn.steps:
        return 0
    return max(step_salience(step.kind) for step in turn.steps)


@dataclass
class _RenderBlock:
    order: int
    text: str
    salience: int
    in_recency_floor: bool


@dataclass
class SalientTurnsModule:
    """
    Ingest like recent_turns; retain by peak step salience in storage; render
    chronologically within ``char_budget`` with step-level trimming on older turns.
    """

    module_id: str = "salient_turns"
    char_budget: int = DEFAULT_CHAR_BUDGET
    storage_window: int = DEFAULT_STORAGE_WINDOW
    recency_floor: int = DEFAULT_RECENCY_FLOOR

    _turns: list[TurnRecord] = field(default_factory=list, repr=False)
    _witnessed_before: list[list[WitnessedEvent]] = field(default_factory=list, repr=False)
    _salience_scores: list[int] = field(default_factory=list, repr=False)
    _pending: list[WitnessedEvent] = field(default_factory=list, repr=False)
    _total_turns: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        validate_char_budget(self.char_budget)
        if self.recency_floor < 1:
            raise ValueError("recency_floor must be at least 1")
        if self.storage_window < self.recency_floor:
            raise ValueError("storage_window must be >= recency_floor")

    def record_turn(self, record: TurnRecord, ctx: MemoryRecordContext) -> None:
        del ctx
        witnessed = list(self._pending)
        self._pending.clear()
        self._witnessed_before.append(witnessed)
        self._turns.append(record)
        self._salience_scores.append(storage_salience(record))
        self._total_turns += 1
        self._evict_storage_if_needed()

    def record_observation(self, event: WitnessedEvent, ctx: MemoryObserveContext) -> None:
        del ctx
        self._pending.append(event)

    def render(self, ctx: MemoryRenderContext) -> str:
        del ctx
        blocks = self._build_render_blocks()
        if not blocks:
            return ""
        selected = self._select_blocks_for_budget(blocks)
        if not selected:
            return blocks[-1].text if blocks else ""

        selected.sort(key=lambda block: block.order)
        lines: list[str] = []
        if selected[0].order > 0:
            lines.append(OMISSION_LINE)
            lines.append("")

        for index, block in enumerate(selected):
            if index > 0:
                lines.append("")
            lines.append(block.text)

        return join_lines(lines)

    def _build_render_blocks(self) -> list[_RenderBlock]:
        blocks: list[_RenderBlock] = []
        order = 0
        total = len(self._turns)
        recency_start = max(0, total - self.recency_floor)

        for index, turn in enumerate(self._turns):
            in_recency_floor = index >= recency_start
            witnessed = self._witnessed_before[index] if index < len(self._witnessed_before) else []
            if witnessed:
                blocks.append(
                    _RenderBlock(
                        order=order,
                        text=join_lines(
                            format_witnessed_events(
                                witnessed,
                                f"Before turn {turn.turn_number}, you observed:",
                            )
                        ),
                        salience=WITNESS_SALIENCE,
                        in_recency_floor=in_recency_floor,
                    )
                )
                order += 1

            selected_steps = select_salient_steps(turn.steps, in_recency_floor=in_recency_floor)
            result_text = join_step_results(selected_steps)
            include_reasoning = should_include_reasoning(index, total)
            if not result_text and not (include_reasoning and turn.reasoning):
                continue

            block_salience = (
                max(step_salience(step.kind) for step in selected_steps) if selected_steps else 0
            )
            blocks.append(
                _RenderBlock(
                    order=order,
                    text=join_lines(
                        format_own_turn(
                            turn,
                            include_reasoning=include_reasoning,
                            result_text=result_text,
                        )
                    ),
                    salience=block_salience,
                    in_recency_floor=in_recency_floor,
                )
            )
            order += 1

        if self._pending:
            if self._turns:
                heading = f"Since turn {self._turns[-1].turn_number}, you observed:"
            else:
                heading = "You observed:"
            blocks.append(
                _RenderBlock(
                    order=order,
                    text=join_lines(format_witnessed_events(self._pending, heading)),
                    salience=WITNESS_SALIENCE,
                    in_recency_floor=True,
                )
            )
        return blocks

    def _select_blocks_for_budget(self, blocks: list[_RenderBlock]) -> list[_RenderBlock]:
        selected: list[_RenderBlock] = []
        used = 0

        def try_add(block: _RenderBlock) -> bool:
            nonlocal used
            extra = 2 if selected else 0  # blank line between blocks
            cost = len(block.text) + extra
            if selected and used + cost > self.char_budget:
                return False
            if not selected and cost > self.char_budget:
                selected.append(block)
                used = cost
                return True
            if used + cost > self.char_budget:
                return False
            selected.append(block)
            used += cost
            return True

        recency = [block for block in blocks if block.in_recency_floor]
        for block in sorted(recency, key=lambda item: item.order, reverse=True):
            try_add(block)

        remaining = [block for block in blocks if block not in selected]
        remaining.sort(key=lambda item: (-item.salience, -item.order))
        for block in remaining:
            try_add(block)

        return selected

    def _evict_storage_if_needed(self) -> None:
        while len(self._turns) > self.storage_window:
            protected = set(range(max(0, len(self._turns) - self.recency_floor), len(self._turns)))
            evict_index = None
            evict_score = None
            for index in range(len(self._turns)):
                if index in protected:
                    continue
                score = self._salience_scores[index]
                if evict_score is None or score < evict_score:
                    evict_score = score
                    evict_index = index
            if evict_index is None:
                break
            self._turns.pop(evict_index)
            self._witnessed_before.pop(evict_index)
            self._salience_scores.pop(evict_index)

    @property
    def total_turns(self) -> int:
        return self._total_turns

    @property
    def stored_turns(self) -> list[TurnRecord]:
        """Own turns in storage (up to ``storage_window``); render may compress older turns."""
        return list(self._turns)

    def export_state(self) -> dict:
        return {
            "char_budget": self.char_budget,
            "storage_window": self.storage_window,
            "recency_floor": self.recency_floor,
            "total_turns": self._total_turns,
            "turns": serialize_turn_list(self._turns),
            "witnessed_before": serialize_witnessed_before(self._witnessed_before),
            "salience_scores": list(self._salience_scores),
            "pending": serialize_witness_list(self._pending),
        }

    def restore_state(self, data: dict) -> None:
        self.char_budget = int(data["char_budget"])
        self.storage_window = int(data["storage_window"])
        self.recency_floor = int(data["recency_floor"])
        validate_char_budget(self.char_budget)
        if self.recency_floor < 1:
            raise ValueError("recency_floor must be at least 1")
        if self.storage_window < self.recency_floor:
            raise ValueError("storage_window must be >= recency_floor")
        self._total_turns = int(data["total_turns"])
        self._turns = deserialize_turn_list(data.get("turns", []))
        self._witnessed_before = deserialize_witnessed_before(data.get("witnessed_before", []))
        self._salience_scores = [int(score) for score in data.get("salience_scores", [])]
        self._pending = deserialize_witness_list(data.get("pending", []))
