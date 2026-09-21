"""Pure parsing, caching, and geometry logic for the WARDOGS plugin.

Map coordinates use X as east and Y as north.  Bearings are clockwise from map
north, matching the usual in-game compass convention.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import time
from typing import Callable

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
AXIS_VALUE = re.compile(rf"(?i)([xy])\s*[:=]?\s*({NUMBER})")
BARE_NUMBER = re.compile(NUMBER)

# L81 firing table, community-measured for the current WARDOGS build.  Each
# pair is (range in metres, elevation setting in the weapon's own mil scale).
# Values between rows are linearly interpolated.
L81_FIRING_TABLE = (
    (132, 850),
    (140, 840),
    (151, 830),
    (163, 820),
    (175, 810),
    (187, 800),
    (198, 790),
    (208, 780),
    (219, 770),
    (229, 760),
    (239, 750),
    (250, 740),
    (260, 730),
    (270, 720),
    (280, 710),
    (290, 700),
    (300, 690),
    (310, 680),
    (319, 670),
    (329, 660),
    (339, 650),
    (348, 640),
    (358, 630),
    (367, 620),
    (376, 610),
    (385, 600),
    (394, 590),
    (403, 580),
    (412, 570),
    (420, 560),
    (429, 550),
    (437, 540),
    (446, 530),
    (454, 520),
    (462, 510),
    (470, 500),
    (478, 490),
    (486, 480),
    (494, 470),
    (501, 460),
    (509, 450),
    (516, 440),
    (524, 430),
    (531, 420),
    (538, 410),
    (545, 400),
    (552, 390),
    (559, 380),
    (565, 370),
    (572, 360),
    (578, 350),
    (585, 340),
    (591, 330),
    (597, 320),
    (603, 310),
    (609, 300),
    (615, 290),
    (620, 280),
    (626, 270),
    (631, 260),
    (636, 250),
    (641, 240),
    (646, 230),
    (651, 220),
    (656, 210),
    (661, 200),
    (666, 190),
    (670, 180),
    (675, 170),
    (680, 160),
    (684, 150),
)


class CoordinateParseError(ValueError):
    """Raised when an argument cannot unambiguously yield one or two points."""


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def display(self) -> str:
        return f"x{self.x:.2f}, y{self.y:.2f}"


@dataclass(frozen=True)
class CalculationResult:
    mortar: Point | None
    target: Point | None
    bearing: float | None = None
    distance: float | None = None
    elevation_mil: float | None = None
    cached_mortar: bool = False

    @property
    def needs_mortar(self) -> bool:
        return self.mortar is None

    def format_message(self) -> str:
        assert self.mortar is not None and self.target is not None
        assert self.bearing is not None and self.distance is not None
        cache_note = (
            "（已使用缓存炮位）" if self.cached_mortar else "（炮位已缓存 105 分钟）"
        )
        return (
            "WARDOGS 迫击炮解算\n"
            f"炮位：{self.mortar.display()}\n"
            f"目标：{self.target.display()}\n"
            f"方位角：{self.bearing:.1f}° {compass_direction(self.bearing)}"
            f"（{degrees_to_mils(self.bearing):.0f} MIL）\n"
            f"距离：{self.distance:.0f} M（{self.distance / 100:.2f} 地图单位）\n"
            f"射程密位（L81）：{format_elevation(self.elevation_mil)}\n"
            f"{cache_note}"
        )


class BallisticCalculator:
    """Stores each user's last mortar location for a bounded amount of time."""

    usage = (
        "用法：/wdbc <炮位> <目标位>；已设置炮位后可用 /wdbc <目标位>。\n"
        "示例：/wdbc x64.85,y71.98 y74.85x61.13 或 /wdbc 64.85 71.98 74.85,61.13"
    )

    def __init__(
        self,
        cache_ttl_seconds: float = 105 * 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds
        self.clock = clock
        self._mortars: dict[str, tuple[Point, float]] = {}

    def calculate(self, user_id: str, argument: str) -> CalculationResult:
        points = parse_points(argument)
        if len(points) == 2:
            mortar, target = points
            self._mortars[user_id] = (mortar, self.clock() + self.cache_ttl_seconds)
            return self._solve(mortar, target, cached_mortar=False)

        mortar = self._get_mortar(user_id)
        if mortar is None:
            return CalculationResult(mortar=None, target=points[0])
        return self._solve(mortar, points[0], cached_mortar=True)

    def _get_mortar(self, user_id: str) -> Point | None:
        cached = self._mortars.get(user_id)
        if cached is None:
            return None
        mortar, expires_at = cached
        if self.clock() >= expires_at:
            del self._mortars[user_id]
            return None
        return mortar

    @staticmethod
    def _solve(mortar: Point, target: Point, cached_mortar: bool) -> CalculationResult:
        dx = target.x - mortar.x
        dy = target.y - mortar.y
        # atan2(east, north): 0° north, 90° east, increasing clockwise.
        bearing = math.degrees(math.atan2(dx, dy)) % 360
        distance = math.hypot(dx, dy) * 100
        return CalculationResult(
            mortar=mortar,
            target=target,
            bearing=bearing,
            distance=distance,
            elevation_mil=interpolate_mil(distance, L81_FIRING_TABLE),
            cached_mortar=cached_mortar,
        )


def parse_points(text: str) -> list[Point]:
    """Parse one or two points from labelled or unlabelled WARDOGS coordinates."""
    normalized = text.replace("，", ",").strip()
    if not normalized:
        raise CoordinateParseError("没有提供坐标")

    labelled = list(AXIS_VALUE.finditer(normalized))
    if labelled:
        residue = AXIS_VALUE.sub(" ", normalized)
        if BARE_NUMBER.search(residue) or re.search(r"[a-wzA-WZ]", residue):
            raise CoordinateParseError("请勿混用带轴标记和不带轴标记的坐标")
        return _parse_labelled(labelled)

    if re.search(r"[a-zA-Z]", normalized):
        raise CoordinateParseError("轴标记只能使用 x 或 y")
    values = [float(match.group()) for match in BARE_NUMBER.finditer(normalized)]
    if len(values) not in (2, 4):
        raise CoordinateParseError("不带轴标记时需要输入 2 或 4 个数字（按 x y 顺序）")
    return [
        _point_from_values(*values[index : index + 2])
        for index in range(0, len(values), 2)
    ]


def _parse_labelled(matches: list[re.Match[str]]) -> list[Point]:
    points: list[Point] = []
    current: dict[str, float] = {}
    for match in matches:
        axis, value = match.group(1).lower(), float(match.group(2))
        if axis in current:
            if set(current) != {"x", "y"}:
                raise CoordinateParseError("每组带轴坐标必须各包含一个 x 和一个 y")
            points.append(_point_from_values(current["x"], current["y"]))
            current = {}
        current[axis] = value
    if set(current) != {"x", "y"}:
        raise CoordinateParseError("每组带轴坐标必须各包含一个 x 和一个 y")
    points.append(_point_from_values(current["x"], current["y"]))
    if len(points) not in (1, 2):
        raise CoordinateParseError("最多可输入炮位和目标位两组坐标")
    return points


def _point_from_values(x: float, y: float) -> Point:
    if not (math.isfinite(x) and math.isfinite(y)):
        raise CoordinateParseError("坐标必须是有限数字")
    if x < 0 or y < 0:
        raise CoordinateParseError("WARDOGS 地图坐标不能为负数")
    return Point(x, y)


def compass_direction(bearing: float) -> str:
    directions = ("北", "东北", "东", "东南", "南", "西南", "西", "西北")
    return directions[int((bearing + 22.5) // 45) % len(directions)]


def degrees_to_mils(degrees: float) -> float:
    """Convert a compass angle to NATO-style 6400-mil azimuth."""
    return degrees * 6400 / 360


def interpolate_mil(
    distance: float, table: tuple[tuple[int, int], ...]
) -> float | None:
    """Return an elevation mil interpolated from a range card, if in range."""
    if not table[0][0] <= distance <= table[-1][0]:
        return None
    for (low_distance, low_mil), (high_distance, high_mil) in zip(table, table[1:]):
        if low_distance <= distance <= high_distance:
            ratio = (distance - low_distance) / (high_distance - low_distance)
            return low_mil + ratio * (high_mil - low_mil)
    return float(table[-1][1])


def format_elevation(mil: float | None) -> str:
    if mil is None:
        return "超出 L81 射表 132–684 M"
    return f"{mil:.0f} MIL"
