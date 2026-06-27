"""
pathfinding.py

V0.6.0a — BFS pathfinding with movement blocking (5e: 8-way, cost 1 per step).
"""

from __future__ import annotations

from collections import deque

from src.area import Area
from src.occupancy import NEIGHBOR_DELTAS, is_tile_enterable, resolve_standable_goal


def find_path(
    start: tuple[int, int],
    goal: tuple[int, int],
    area: Area,
    mover_id: str,
) -> list[tuple[int, int]]:
    """
    Shortest path from *start* to *goal* inclusive.

    Returns an empty list when no path exists. Uses a standable goal when the
    raw goal tile cannot be entered.
    """
    if start == goal:
        if is_tile_enterable(area, goal, mover_id):
            return [start]
        return []

    standable = resolve_standable_goal(area, goal, mover_id)
    if standable is None:
        return []

    if start == standable:
        return [start]

    queue: deque[tuple[int, int]] = deque([start])
    parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}

    while queue:
        current = queue.popleft()
        if current == standable:
            path: list[tuple[int, int]] = []
            node: tuple[int, int] | None = current
            while node is not None:
                path.append(node)
                node = parents[node]
            path.reverse()
            return path

        for dx, dy in NEIGHBOR_DELTAS:
            neighbor = (current[0] + dx, current[1] + dy)
            if neighbor in parents:
                continue
            if not is_tile_enterable(area, neighbor, mover_id):
                continue
            parents[neighbor] = current
            queue.append(neighbor)

    return []


def walk_with_pathfinding(
    from_pos: tuple[int, int],
    to_pos: tuple[int, int],
    max_steps: int,
    area: Area,
    mover_id: str,
) -> tuple[tuple[int, int], bool, list[tuple[int, int]]]:
    """
    Walk up to *max_steps* along a shortest path toward *to_pos*.

    Returns ``(final_position, reached_standable_goal, path_positions)`` where
    *path_positions* includes the start tile and each stepped tile.
    """
    if max_steps <= 0:
        return from_pos, from_pos == to_pos, [from_pos]

    standable = resolve_standable_goal(area, to_pos, mover_id)
    if standable is None:
        return from_pos, False, [from_pos]

    path = find_path(from_pos, standable, area, mover_id)
    if not path:
        return from_pos, False, [from_pos]

    steps_to_take = min(max_steps, len(path) - 1)
    segment = path[: steps_to_take + 1]
    final = segment[-1]
    reached = final == standable
    return final, reached, segment
