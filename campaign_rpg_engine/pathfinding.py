"""
pathfinding.py

V0.6.0a — BFS pathfinding with movement blocking (5e: 8-way, cost 1 per step).
V0.7.1 — tie-break collinear moves to stay on the shared row/column.
"""

from __future__ import annotations

from collections import deque

from campaign_rpg_engine.area import Area
from campaign_rpg_engine.occupancy import NEIGHBOR_DELTAS, is_tile_enterable, resolve_standable_goal


def _path_neighbor_priority(
    current: tuple[int, int],
    neighbor: tuple[int, int],
    goal: tuple[int, int],
    start: tuple[int, int],
) -> tuple[int, int, int]:
    """
    Sort key for BFS neighbor expansion (lower is better).

    When *start* and *goal* share a row or column, prefer staying on that line.
    Otherwise prefer diagonal steps toward *goal* (5e-style greedy tie-break).
    """
    nx, ny = neighbor
    gx, gy = goal
    sx, sy = start
    cx, cy = current

    remaining = max(abs(gx - nx), abs(gy - ny))

    if sy == gy:
        off_axis = abs(ny - gy)
    elif sx == gx:
        off_axis = abs(nx - gx)
    else:
        ndx = nx - cx
        ndy = ny - cy
        tdx = gx - cx
        tdy = gy - cy
        if tdx != 0 and tdy != 0:
            is_diagonal = ndx != 0 and ndy != 0
            toward_x = ndx == 0 or (ndx > 0) == (tdx > 0)
            toward_y = ndy == 0 or (ndy > 0) == (tdy > 0)
            if is_diagonal and toward_x and toward_y:
                off_axis = 0
            elif not is_diagonal and (ndx == 0 or ndy == 0) and toward_x and toward_y:
                off_axis = 1
            else:
                off_axis = 2
        else:
            off_axis = 0

    return (off_axis, remaining, abs(gx - nx) + abs(gy - ny))


def _sorted_neighbors(
    current: tuple[int, int],
    goal: tuple[int, int],
    start: tuple[int, int],
) -> list[tuple[int, int]]:
    ranked: list[tuple[tuple[int, int, int], tuple[int, int]]] = []
    for dx, dy in NEIGHBOR_DELTAS:
        neighbor = (current[0] + dx, current[1] + dy)
        ranked.append(
            (
                _path_neighbor_priority(current, neighbor, goal, start),
                neighbor,
            )
        )
    ranked.sort(key=lambda item: item[0])
    return [neighbor for _, neighbor in ranked]


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

    standable = resolve_standable_goal(area, goal, mover_id, from_pos=start)
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

        for neighbor in _sorted_neighbors(current, standable, start):
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

    standable = resolve_standable_goal(area, to_pos, mover_id, from_pos=from_pos)
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
