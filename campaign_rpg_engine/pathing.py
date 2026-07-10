"""
pathing.py

V0.4.0b — D&D 5e grid movement: diagonal and orthogonal steps each cost 1.
Diagonal steps are taken first when both axes differ.
"""

from __future__ import annotations


def chebyshev_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Minimum steps to reach *b* from *a* when diagonals cost 1 (5e)."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def path_step_towards(
    from_pos: tuple[int, int], to_pos: tuple[int, int]
) -> tuple[int, int]:
    """One greedy step toward *to_pos* (diagonal first, then straight)."""
    fx, fy = from_pos
    tx, ty = to_pos
    dx = tx - fx
    dy = ty - fy
    if dx == 0 and dy == 0:
        return from_pos

    nx, ny = fx, fy
    if dx != 0 and dy != 0:
        nx += 1 if dx > 0 else -1
        ny += 1 if dy > 0 else -1
    elif dx != 0:
        nx += 1 if dx > 0 else -1
    else:
        ny += 1 if dy > 0 else -1
    return (nx, ny)


def walk_towards(
    from_pos: tuple[int, int],
    to_pos: tuple[int, int],
    max_steps: int,
) -> tuple[tuple[int, int], bool]:
    """
    Walk up to *max_steps* toward *to_pos*.

    Returns ``(final_position, reached_target)``.
    """
    current = from_pos
    if max_steps <= 0:
        return current, current == to_pos

    for _ in range(max_steps):
        if current == to_pos:
            return current, True
        current = path_step_towards(current, to_pos)

    return current, current == to_pos
