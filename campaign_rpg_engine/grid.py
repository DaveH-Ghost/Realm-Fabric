"""Grid distance helpers."""

from __future__ import annotations


def chebyshev_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Chebyshev distance: max(|dx|, |dy|)."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))
