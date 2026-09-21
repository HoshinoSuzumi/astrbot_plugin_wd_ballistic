import math

import pytest

from ballistic import (
    BallisticCalculator,
    CoordinateParseError,
    Point,
    parse_points,
    strip_command_prefix,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("x64.85, y71.98", [Point(64.85, 71.98)]),
        ("x64.85,y71.98 y74.85x61.13", [Point(64.85, 71.98), Point(61.13, 74.85)]),
        ("64.85 71.98 74.85,61.13", [Point(64.85, 71.98), Point(74.85, 61.13)]),
        ("x64.85,y71.98 74.85,61.13", [Point(64.85, 71.98), Point(74.85, 61.13)]),
        ("64.85,71.98 x74.85,y61.13", [Point(64.85, 71.98), Point(74.85, 61.13)]),
        ("x64.85 71.98 74.85 y61.13", [Point(64.85, 71.98), Point(74.85, 61.13)]),
        ("Y1 X2", [Point(2, 1)]),
    ],
)
def test_parse_supported_coordinate_forms(raw, expected):
    assert parse_points(raw) == expected


@pytest.mark.parametrize(
    "message",
    [
        "/wdbc x64.85, y71.98 x74.85, y61.13",
        "wdbc x64.85,y71.98 x74.85,y61.13",
        "x64.85,y71.98 y74.85x61.13",
    ],
)
def test_accepts_command_text_preserved_by_adapters(message):
    assert len(parse_points(strip_command_prefix(message))) == 2


@pytest.mark.parametrize("raw", ["x1 y2 3", "a1 y2", "x-1 y2", "1 2 3"])
def test_rejects_ambiguous_or_invalid_coordinates(raw):
    with pytest.raises(CoordinateParseError):
        parse_points(raw)


def test_calculates_clockwise_bearing_from_north_and_distance():
    calculator = BallisticCalculator()
    result = calculator.calculate("u", "0 0 3 4")
    assert result.distance == 500
    assert result.elevation_mil == pytest.approx(461.43, abs=0.01)
    assert math.isclose(result.bearing, 36.8698976458)
    assert "方位角：36.9° NE(东北)" in result.format_message()
    assert "已缓存" not in result.format_message()
    assert "WARDOGS 迫击炮解算" not in result.format_message()


def test_interpolates_l81_range_card_at_a_known_example():
    result = BallisticCalculator().calculate("u", "0 0 0 4.5")
    assert result.distance == 450
    assert result.elevation_mil == 525


def test_one_point_uses_per_user_cached_mortar_and_expires():
    now = [0.0]
    calculator = BallisticCalculator(10, clock=lambda: now[0])
    calculator.calculate("one", "10 10 20 10")
    cached = calculator.calculate("one", "10 20")
    assert cached.cached_mortar is True
    assert cached.bearing == 0
    assert calculator.calculate("two", "10 20").needs_mortar is True
    now[0] = 10
    assert calculator.calculate("one", "10 20").needs_mortar is True


def test_accepts_large_legal_map_coordinates():
    assert parse_points("x163.84 y120")[0] == Point(163.84, 120)
