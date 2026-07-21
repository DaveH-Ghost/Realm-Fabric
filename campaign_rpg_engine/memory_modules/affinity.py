"""Affinity memory — rolling summary plus per-agent relationship affinities."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from campaign_rpg_engine.area_event import AREA_EVENT_ACTOR_ID
from campaign_rpg_engine.llm.affinity_update import generate_affinity_updates
from campaign_rpg_engine.llm.client import concurrent_llm_calls_enabled
from campaign_rpg_engine.llm.memory_summary import other_agents_from_snapshot_extra
from campaign_rpg_engine.memory_modules.affinity_ladder import (
    DEFAULT_RELATIONSHIP_SUMMARY_MAX_CHARS,
    clamp_affinity,
    format_affinity_tag,
)
from campaign_rpg_engine.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from campaign_rpg_engine.memory_modules.consolidation_runner import ConsolidationSnapshot
from campaign_rpg_engine.memory_modules.formatting import (
    corpus_for_name_matching,
    format_stored_turns_block,
    format_turns_batch_for_summary,
    is_reserved_mention_name,
    join_lines,
)
from campaign_rpg_engine.memory_modules.rolling_summary import (
    RollingSummaryModule,
)
from campaign_rpg_engine.turn_record import TurnRecord

AffinityUpdateGenerator = Callable[..., list[dict[str, Any]]]


def _is_trackable_affinity_actor(agent_id: str) -> bool:
    """False for GM/area broadcast actors (``__area__`` / Environment)."""
    return bool(agent_id) and agent_id != AREA_EVENT_ACTOR_ID


@dataclass
class AffinityModule(RollingSummaryModule):
    """
    Rolling summary plus relationship affinities (-10…+10).

    Consolidation runs Call A (summary) and Call B (affinity deltas). When
    ``concurrent_llm_calls_enabled()`` is True they run in parallel; otherwise
    sequentially. Background consolidation is also disabled when concurrent
    LLM calls are off.
    """

    module_id: str = "affinity"
    relationship_summary_max_chars: int = DEFAULT_RELATIONSHIP_SUMMARY_MAX_CHARS
    _affinity_generator: AffinityUpdateGenerator = field(
        default=generate_affinity_updates, repr=False
    )
    _affinities: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _directory: dict[str, str] = field(default_factory=dict, repr=False)
    # Agents co-present in the owner's area at any turn since last consolidation.
    _window_nearby_ids: set[str] = field(default_factory=set, repr=False)

    def record_turn(self, record: TurnRecord, ctx: MemoryRecordContext) -> None:
        self._remember_agents(ctx.nearby_agents)
        super().record_turn(record, ctx)

    def record_observation(self, event: WitnessedEvent, ctx: MemoryObserveContext) -> None:
        if _is_trackable_affinity_actor(event.actor_id):
            self._directory[event.actor_id] = event.actor_name
        super().record_observation(event, ctx)

    def render(self, ctx: MemoryRenderContext) -> str:
        for other in ctx.area.agents:
            if other.id != ctx.agent.id:
                self._directory[other.id] = other.name

        detail = format_stored_turns_block(self._turns, self._witnessed_before, self._pending)
        detail_text = join_lines(detail) if detail else ""
        affinity_ids = self._prompt_affinity_ids(ctx, detail_text)
        affinity_lines = self._format_affinity_block(affinity_ids)

        lines: list[str] = []
        if affinity_lines:
            lines.append("Relationships:")
            lines.extend(affinity_lines)
            if self._summary or detail:
                lines.append("")
        if self._summary:
            lines.append("Summary:")
            lines.append(self._summary)
            if detail:
                lines.append("")
        lines.extend(detail)
        if not lines:
            return ""
        return join_lines(lines)

    def _schedule_consolidation(
        self,
        agent_name: str,
        turn_number: int,
        *,
        personality: str = "",
        appearance: str = "",
        other_agents: tuple[tuple[str, str], ...] = (),
    ) -> None:
        batch_turns, batch_witnessed = self._turns_for_summary_batch()
        batch_text = format_turns_batch_for_summary(batch_turns, batch_witnessed)
        candidates = self._build_candidates(batch_turns, batch_witnessed, batch_text)
        snapshot = ConsolidationSnapshot(
            turns=copy.deepcopy(batch_turns),
            witnessed_before=copy.deepcopy(batch_witnessed),
            agent_name=agent_name,
            turn_number=turn_number,
            previous_summary=self._summary,
            extra={
                "candidates": copy.deepcopy(candidates),
                "personality": personality,
                "appearance": appearance,
                "other_agents": list(other_agents),
            },
        )
        self._consolidation_runner.start(
            snapshot,
            background=self.background_consolidation and concurrent_llm_calls_enabled(),
            run=self._run_affinity_consolidation,
            on_success=self._apply_affinity_consolidation,
            thread_name=f"affinity-{agent_name}-turn-{turn_number}",
        )

    def ensure_ready_for_turn(self) -> None:
        self._consolidation_runner.ensure_ready(
            run=self._run_affinity_consolidation,
            on_success=self._apply_affinity_consolidation,
        )

    def flush_for_save(self) -> None:
        self._consolidation_runner.flush_for_save()

    def _run_affinity_consolidation(self, snapshot: ConsolidationSnapshot) -> dict[str, Any]:
        batch_text = format_turns_batch_for_summary(snapshot.turns, snapshot.witnessed_before)
        candidates = list(snapshot.extra.get("candidates") or [])
        identity = {
            "personality": str(snapshot.extra.get("personality") or ""),
            "appearance": str(snapshot.extra.get("appearance") or ""),
            "other_agents": other_agents_from_snapshot_extra(snapshot.extra),
        }

        def run_a() -> str:
            return self._summary_generator(
                agent_name=snapshot.agent_name,
                previous_summary=snapshot.previous_summary,
                batch_text=batch_text,
                max_chars=self.max_summary_chars,
                turn_number=snapshot.turn_number,
                **identity,
            )

        def run_b() -> list[dict[str, Any]]:
            if not candidates:
                return []
            return self._affinity_generator(
                agent_name=snapshot.agent_name,
                batch_text=batch_text,
                candidates=candidates,
                max_summary_chars=self.relationship_summary_max_chars,
                turn_number=snapshot.turn_number,
                **identity,
            )

        if concurrent_llm_calls_enabled():
            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_a = pool.submit(run_a)
                fut_b = pool.submit(run_b)
                # Raise if either failed (all-or-nothing).
                new_summary = fut_a.result()
                updates = fut_b.result()
        else:
            # One LLM call at a time (Featherless low concurrency / DeepSeek unit cost).
            new_summary = run_a()
            updates = run_b()
        if not str(new_summary).strip():
            raise RuntimeError("Affinity Call A returned empty summary")
        return {"summary": str(new_summary), "updates": updates}

    def _apply_affinity_consolidation(
        self,
        result: Any,
        snapshot: ConsolidationSnapshot,
    ) -> None:
        if isinstance(result, str):
            # Defensive: should not happen for affinity path.
            new_summary = result
            updates: list[dict[str, Any]] = []
        else:
            new_summary = str(result["summary"])
            updates = list(result.get("updates") or [])

        for row in updates:
            agent_id = str(row["agent_id"])
            if not _is_trackable_affinity_actor(agent_id):
                continue
            prior = self._affinities.get(agent_id) or {
                "name": row.get("name") or agent_id,
                "score": 0,
                "summary": "",
            }
            score = clamp_affinity(int(prior.get("score", 0)) + int(row["delta"]))
            name = str(row.get("name") or prior.get("name") or agent_id)
            row_summary = str(row.get("summary") or "").strip()
            prior_summary = str(prior.get("summary") or "").strip()
            self._affinities[agent_id] = {
                "name": name,
                "score": score,
                # Empty LLM blurb must not wipe a prior relationship summary.
                "summary": row_summary or prior_summary,
            }
            self._directory[agent_id] = name

        self._apply_successful_consolidation(new_summary, snapshot)
        self._window_nearby_ids.clear()

    def _build_candidates(
        self,
        batch_turns: list[TurnRecord],
        batch_witnessed: list[list[WitnessedEvent]],
        batch_text: str,
    ) -> list[dict[str, Any]]:
        del batch_text  # LLM Call B still uses full batch; mentions use body corpus.
        ids: set[str] = set()
        for events in batch_witnessed:
            for event in events:
                if not _is_trackable_affinity_actor(event.actor_id):
                    continue
                ids.add(event.actor_id)
                self._directory[event.actor_id] = event.actor_name
        mention_text = corpus_for_name_matching(batch_turns, batch_witnessed)
        self._add_mentioned_agent_ids(ids, mention_text)
        # Anyone same-area on any turn since the last successful consolidation.
        ids.update(
            agent_id for agent_id in self._window_nearby_ids if _is_trackable_affinity_actor(agent_id)
        )

        candidates: list[dict[str, Any]] = []
        for agent_id in sorted(ids):
            if not _is_trackable_affinity_actor(agent_id):
                continue
            name = self._directory.get(agent_id) or (
                str(self._affinities.get(agent_id, {}).get("name") or agent_id)
            )
            entry = self._affinities.get(agent_id) or {
                "name": name,
                "score": 0,
                "summary": "",
            }
            candidates.append(
                {
                    "agent_id": agent_id,
                    "name": str(entry.get("name") or name),
                    "score": clamp_affinity(int(entry.get("score", 0))),
                    "summary": str(entry.get("summary") or ""),
                }
            )
        return candidates

    def _add_mentioned_agent_ids(self, ids: set[str], mention_text: str) -> None:
        if not mention_text.strip():
            return
        for agent_id, name in self._directory.items():
            if not _is_trackable_affinity_actor(agent_id):
                continue
            if self._name_mentioned(name, mention_text):
                ids.add(agent_id)
        for agent_id, entry in self._affinities.items():
            if not _is_trackable_affinity_actor(agent_id):
                continue
            name = str(entry.get("name") or "")
            if self._name_mentioned(name, mention_text):
                ids.add(agent_id)

    @staticmethod
    def _name_mentioned(name: str, mention_text: str) -> bool:
        cleaned = (name or "").strip()
        if not cleaned or is_reserved_mention_name(cleaned):
            return False
        return bool(re.search(rf"\b{re.escape(cleaned)}\b", mention_text, re.IGNORECASE))

    def _remember_agents(self, nearby: tuple[tuple[str, str], ...]) -> None:
        for agent_id, name in nearby:
            self._window_nearby_ids.add(agent_id)
            self._directory[agent_id] = name

    def _prompt_affinity_ids(self, ctx: MemoryRenderContext, detail_text: str) -> list[str]:
        del detail_text  # Mention scan uses body corpus, not rendered headings.
        ids: set[str] = set()
        for other in ctx.area.agents:
            if other.id != ctx.agent.id:
                ids.add(other.id)
                self._directory[other.id] = other.name
        mention_text = corpus_for_name_matching(
            self._turns,
            self._witnessed_before,
            pending=self._pending,
        )
        self._add_mentioned_agent_ids(ids, mention_text)
        # Stable order by name
        return sorted(ids, key=lambda i: (self._directory.get(i) or i).lower())

    def _format_affinity_block(self, agent_ids: list[str]) -> list[str]:
        lines: list[str] = []
        for agent_id in agent_ids:
            entry = self._affinities.get(agent_id)
            name = (entry or {}).get("name") or self._directory.get(agent_id) or agent_id
            score = clamp_affinity(int((entry or {}).get("score", 0))) if entry else 0
            summary = str((entry or {}).get("summary") or "").strip()
            tag = format_affinity_tag(score, str(name))
            if summary:
                lines.append(f"{tag}: {summary}")
            elif entry:
                lines.append(tag)
            # No entry and score 0 with empty summary: still show mild tag for area mates
            else:
                lines.append(tag)
        return lines

    @property
    def affinities(self) -> dict[str, dict[str, Any]]:
        return copy.deepcopy(self._affinities)

    def export_state(self) -> dict:
        data = super().export_state()
        data["affinities"] = copy.deepcopy(self._affinities)
        data["directory"] = dict(self._directory)
        data["window_nearby_ids"] = sorted(self._window_nearby_ids)
        data["relationship_summary_max_chars"] = self.relationship_summary_max_chars
        return data

    def restore_state(self, data: dict) -> None:
        super().restore_state(data)
        raw = data.get("affinities") or {}
        self._affinities = {}
        if isinstance(raw, dict):
            for agent_id, entry in raw.items():
                if not isinstance(entry, dict):
                    continue
                key = str(agent_id)
                if not _is_trackable_affinity_actor(key):
                    continue
                self._affinities[key] = {
                    "name": str(entry.get("name") or agent_id),
                    "score": clamp_affinity(int(entry.get("score", 0))),
                    "summary": str(entry.get("summary") or ""),
                }
        directory = data.get("directory") or {}
        self._directory = (
            {
                str(k): str(v)
                for k, v in directory.items()
                if _is_trackable_affinity_actor(str(k))
            }
            if isinstance(directory, dict)
            else {}
        )
        window_nearby = data.get("window_nearby_ids") or []
        self._window_nearby_ids = (
            {
                str(agent_id)
                for agent_id in window_nearby
                if _is_trackable_affinity_actor(str(agent_id))
            }
            if isinstance(window_nearby, list)
            else set()
        )
        if "relationship_summary_max_chars" in data:
            self.relationship_summary_max_chars = int(data["relationship_summary_max_chars"])
