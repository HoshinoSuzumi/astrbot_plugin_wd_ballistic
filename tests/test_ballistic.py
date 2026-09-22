import math

import pytest

from ballistic import (
    BallisticCalculator,
    CoordinateParseError,
    L81,
    Point,
    SPH2,
    parse_points,
    parse_weapon_argument,
    strip_command_prefix,
)
from range_card import RANGE_CARD_TEMPLATE, build_range_card_context


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
        "/wd bc x64.85, y71.98 x74.85, y61.13",
        "wardogs ballistic x64.85,y71.98 x74.85,y61.13",
        "战狗 弹道计算 x64.85,y71.98 x74.85,y61.13",
        "bc x64.85,y71.98 x74.85,y61.13",
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
    result = calculator.calculate("u", L81, "0 0 3 4")
    assert result.distance == 500
    assert result.elevations[0][1][0] == pytest.approx(461.43, abs=0.01)
    assert math.isclose(result.bearing, 36.8698976458)
    assert "方位：36.9° NE(东北)" in result.format_message()
    assert "已缓存" not in result.format_message()
    assert result.format_message().startswith("L81 弹道计算")


def test_interpolates_l81_range_card_at_a_known_example():
    result = BallisticCalculator().calculate("u", L81, "0 0 0 4.5")
    assert result.distance == 450
    assert result.elevations[0][1] == (525,)


def test_one_point_uses_per_user_cached_mortar_and_expires():
    now = [0.0]
    calculator = BallisticCalculator(10, clock=lambda: now[0])
    calculator.calculate("one", L81, "10 10 20 10")
    cached = calculator.calculate("one", L81, "10 20")
    assert cached.cached_mortar is True
    assert cached.bearing == 0
    assert calculator.calculate("two", L81, "10 20").needs_mortar is True
    assert calculator.calculate("one", SPH2, "10 20").needs_mortar is True
    now[0] = 10
    assert calculator.calculate("one", L81, "10 20").needs_mortar is True


def test_accepts_large_legal_map_coordinates():
    assert parse_points("x163.84 y120")[0] == Point(163.84, 120)


@pytest.mark.parametrize("alias", ["sph2", "SPH-2", "攀枝花", "PZH", "pzh2000", "自火"])
def test_parses_case_insensitive_sph2_aliases(alias):
    weapon, coordinates = parse_weapon_argument(f"{alias} x1,y2 x3,y4")
    assert weapon is SPH2
    assert coordinates == "x1,y2 x3,y4"


def test_defaults_to_l81_without_a_weapon_token():
    weapon, coordinates = parse_weapon_argument("x1,y2 x3,y4")
    assert weapon is L81
    assert coordinates == "x1,y2 x3,y4"


def test_sph2_outputs_both_arcs_when_both_are_available():
    result = BallisticCalculator().calculate("u", SPH2, "0 0 15 15")
    message = result.format_message()
    assert message.startswith("SPH-2 弹道计算")
    assert "方位：45.0° NE(东北)" in message
    assert "射程密位(低弹道)：" in message
    assert "射程密位(高弹道)：" in message


def test_sph2_outputs_only_high_arc_at_short_range_and_range_error_when_needed():
    calculator = BallisticCalculator()
    high_only = calculator.calculate("u", SPH2, "0 0 0 8")
    assert "低弹道" not in high_only.format_message()
    assert "高弹道" in high_only.format_message()
    out_of_range = calculator.calculate("u", SPH2, "0 0 30 0")
    assert "超出射表(780–2629M)" in out_of_range.format_message()


def test_sph2_preserves_the_two_community_high_arc_values_at_maximum_range():
    result = BallisticCalculator().calculate("u", SPH2, "0 0 26.29 0")
    assert "射程密位(高弹道)：610–620 MIL" in result.format_message()
    offset_result = BallisticCalculator().calculate("u", SPH2, "60 60 86.29 60")
    assert "射程密位(高弹道)：610–620 MIL" in offset_result.format_message()


def test_range_card_marks_l81_interpolated_sight_setting():
    result = BallisticCalculator().calculate("u", L81, "0 0 0 4.5")
    context = build_range_card_context(result)

    assert context["weapon"] == "L81"
    assert context["distance"] == "450 M"
    assert len(context["trajectories"]) == 1
    trajectory = context["trajectories"][0]
    assert trajectory["label"] == "射程密位（L81）"
    assert trajectory["setting"] == "525 MIL"
    assert trajectory["markers"] == ({"label": "525", "position": 53.571},)
    assert "{% for marker in trajectory.markers %}" in RANGE_CARD_TEMPLATE


def test_range_card_shows_both_sph2_trajectory_rulers_when_available():
    result = BallisticCalculator().calculate("u", SPH2, "0 0 15 15")
    context = build_range_card_context(result)

    assert [item["label"] for item in context["trajectories"]] == [
        "射程密位(低弹道)",
        "射程密位(高弹道)",
    ]


def test_out_of_range_solution_has_no_ruler_data():
    result = BallisticCalculator().calculate("u", L81, "0 0 10 0")
    assert build_range_card_context(result)["trajectories"] == ()
