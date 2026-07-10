"""Tests for relative compass bearings (V0.4.1c)."""

from campaign_rpg_engine.vision_bearing import (
    format_action_range_label,
    format_relative_bearing_phrase,
    relative_compass_direction,
)


def test_relative_compass_direction_cardinals():
    assert relative_compass_direction(0, -4) == "North"
    assert relative_compass_direction(0, 4) == "South"
    assert relative_compass_direction(4, 0) == "East"
    assert relative_compass_direction(-4, 0) == "West"


def test_relative_compass_direction_diagonals():
    assert relative_compass_direction(2, 2) == "South-East"
    assert relative_compass_direction(-2, 2) == "South-West"
    assert relative_compass_direction(2, -2) == "North-East"
    assert relative_compass_direction(-2, -2) == "North-West"


def test_sign_from_explorer_is_south():
    """Demo sign at (2, 4) from Explorer at (1, 1) — south on screen (Y down)."""
    assert relative_compass_direction(1, 3) == "South"


def test_format_relative_bearing_phrase():
    phrase = format_relative_bearing_phrase(
        (1, 1),
        (2, 4),
        units="ft",
        units_per_tile=5,
    )
    assert phrase == "South of you, 15 ft away"


def test_format_relative_bearing_same_tile():
    assert (
        format_relative_bearing_phrase((2, 2), (2, 2), units="ft", units_per_tile=5)
        == "on your tile"
    )


def test_format_action_range_label_tiles_by_default():
    assert format_action_range_label(1) == "range 1"
    assert format_action_range_label(0) == "same tile"


def test_format_action_range_label_with_session_units():
    assert (
        format_action_range_label(1, vision_units="ft", units_per_tile=5)
        == "range 5 ft"
    )
    assert (
        format_action_range_label(2, vision_units="ft", units_per_tile=5)
        == "range 10 ft"
    )
    assert format_action_range_label(1, units_per_tile=5) == "range 5"
