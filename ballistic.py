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
# Accept the complete group command, only its child command, or no command text
# at all.  Some adapters preserve different portions in ``event.message_str``.
COMMAND_PREFIX = re.compile(
    r"^\s*/?(?:(?:wd|wardogs|战狗)\s+)?(?:弹道计算|ballistic|弹道|bc)(?=\s|$)",
    re.IGNORECASE,
)
RANGE_EPSILON = 1e-6

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


def _table(raw: str) -> tuple[tuple[int, int], ...]:
    """Decode compact ``range:mil`` firing-table data."""
    return tuple(tuple(map(int, pair.split(":"))) for pair in raw.split())


# Community SPH-2 table from apollyon-sys/wardogs-calculator (MIT), current
# when this plugin version was released. Values are in metres and sight mils.
SPH2_LOW_TABLE = _table(
    "1181:20 1232:30 1283:40 1334:50 1384:60 1433:70 1482:80 1529:90 "
    "1576:100 1622:110 1666:120 1709:130 1751:140 1792:150 1832:160 "
    "1870:170 1907:180 1944:190 1979:200 2014:210 2046:220 2079:230 "
    "2110:240 2139:250 2168:260 2196:270 2223:280 2249:290 2273:300 "
    "2296:310 2319:320 2341:330 2362:340 2383:350 2403:360 2422:370 "
    "2439:380 2456:390 2471:400 2485:410 2499:420 2513:430 2526:440 "
    "2538:450 2550:460 2561:470 2570:480 2579:490 2586:500 2593:510 "
    "2599:520 2605:530 2610:540 2615:550 2620:560 2623:570 2626:580 "
    "2628:590 2629:600"
)
SPH2_HIGH_TABLE = _table(
    "2629:610 2629:620 2628:630 2626:640 2624:650 2621:660 2617:670 "
    "2613:680 2609:690 2604:700 2599:710 2592:720 2584:730 2576:740 "
    "2567:750 2557:760 2546:770 2536:780 2524:790 2513:800 2501:810 "
    "2488:820 2474:830 2460:840 2444:850 2429:860 2412:870 2395:880 "
    "2378:890 2360:900 2342:910 2323:920 2303:930 2282:940 2261:950 "
    "2239:960 2217:970 2194:980 2171:990 2147:1000 2123:1010 2098:1020 "
    "2072:1030 2046:1040 2019:1050 1991:1060 1963:1070 1934:1080 "
    "1905:1090 1875:1100 1844:1110 1813:1120 1782:1130 1750:1140 "
    "1717:1150 1684:1160 1650:1170 1616:1180 1582:1190 1547:1200 "
    "1512:1210 1475:1220 1438:1230 1401:1240 1363:1250 1324:1260 "
    "1285:1270 1245:1280 1205:1290 1165:1300 1124:1310 1083:1320 "
    "1041:1330 999:1340 956:1350 913:1360 869:1370 825:1380 780:1390"
)


@dataclass(frozen=True)
class Trajectory:
    label: str
    table: tuple[tuple[int, int], ...]
    min_range: int
    max_range: int


@dataclass(frozen=True)
class WeaponProfile:
    id: str
    title: str
    aliases: frozenset[str]
    min_range: int
    max_range: int
    trajectories: tuple[Trajectory, ...]


L81 = WeaponProfile(
    id="l81",
    title="L81 弹道计算",
    aliases=frozenset({"l81", "迫击炮"}),
    min_range=132,
    max_range=684,
    trajectories=(Trajectory("射程密位（L81）", L81_FIRING_TABLE, 132, 684),),
)
SPH2 = WeaponProfile(
    id="sph2",
    title="SPH-2 弹道计算",
    aliases=frozenset({"sph2", "sph-2", "攀枝花", "pzh", "pzh2000", "自火"}),
    min_range=780,
    max_range=2629,
    trajectories=(
        Trajectory("射程密位(低弹道)", SPH2_LOW_TABLE, 1181, 2629),
        Trajectory("射程密位(高弹道)", SPH2_HIGH_TABLE, 780, 2629),
    ),
)
WEAPONS = (L81, SPH2)
DEFAULT_WEAPON = L81


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
    weapon: WeaponProfile
    mortar: Point | None
    target: Point | None
    bearing: float | None = None
    distance: float | None = None
    elevations: tuple[tuple[str, tuple[float, ...]], ...] = ()
    cached_mortar: bool = False

    @property
    def needs_mortar(self) -> bool:
        return self.mortar is None

    def format_message(self) -> str:
        assert self.mortar is not None and self.target is not None
        assert self.bearing is not None and self.distance is not None
        lines = [
            self.weapon.title,
            f"炮位：{self.mortar.display()}",
            f"目标：{self.target.display()}",
            f"方位：{self.bearing:.1f}° {compass_direction(self.bearing)}",
            f"距离：{self.distance:.0f} M",
        ]
        if self.elevations:
            lines.extend(
                f"{label}：{format_elevation(mils)}" for label, mils in self.elevations
            )
        else:
            lines.append(
                f"射程密位({self.weapon.id.upper()})："
                f"超出射表({self.weapon.min_range}–{self.weapon.max_range}M)"
            )
        return "\n".join(lines)


class BallisticCalculator:
    """Stores each user's last mortar location for a bounded amount of time."""

    usage = (
        "用法：\n"
        "- /wd bc [l81|sph2] <炮位> <目标位>\n"
        "    使用炮位+目标位坐标计算。指定过炮位后，炮位坐标会缓存 105 分钟。\n"
        "- /wd bc [l81|sph2] <目标位>\n"
        "    使用缓存的炮位坐标计算。\n"
        "示例：/wd bc sph2 x64.85, y71.98 x74.85, y61.13"
    )

    def __init__(
        self,
        cache_ttl_seconds: float = 105 * 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds
        self.clock = clock
        self._mortars: dict[tuple[str, str], tuple[Point, float]] = {}

    def calculate(
        self, user_id: str, weapon: WeaponProfile, argument: str
    ) -> CalculationResult:
        points = parse_points(argument)
        cache_key = (user_id, weapon.id)
        if len(points) == 2:
            mortar, target = points
            self._mortars[cache_key] = (mortar, self.clock() + self.cache_ttl_seconds)
            return self._solve(weapon, mortar, target, cached_mortar=False)

        mortar = self._get_mortar(cache_key)
        if mortar is None:
            return CalculationResult(weapon=weapon, mortar=None, target=points[0])
        return self._solve(weapon, mortar, points[0], cached_mortar=True)

    def _get_mortar(self, cache_key: tuple[str, str]) -> Point | None:
        cached = self._mortars.get(cache_key)
        if cached is None:
            return None
        mortar, expires_at = cached
        if self.clock() >= expires_at:
            del self._mortars[cache_key]
            return None
        return mortar

    @staticmethod
    def _solve(
        weapon: WeaponProfile, mortar: Point, target: Point, cached_mortar: bool
    ) -> CalculationResult:
        dx = target.x - mortar.x
        dy = target.y - mortar.y
        # atan2(east, north): 0° north, 90° east, increasing clockwise.
        bearing = math.degrees(math.atan2(dx, dy)) % 360
        distance = math.hypot(dx, dy) * 100
        elevations = tuple(
            (trajectory.label, lookup_mils(distance, trajectory))
            for trajectory in weapon.trajectories
            if trajectory.min_range - RANGE_EPSILON
            <= distance
            <= trajectory.max_range + RANGE_EPSILON
        )
        return CalculationResult(
            weapon=weapon,
            mortar=mortar,
            target=target,
            bearing=bearing,
            distance=distance,
            elevations=elevations,
            cached_mortar=cached_mortar,
        )


def parse_points(text: str) -> list[Point]:
    """Parse one or two points from mixed labelled/unlabelled coordinates."""
    normalized = text.replace("，", ",").strip()
    if not normalized:
        raise CoordinateParseError("没有提供坐标")

    labelled = list(AXIS_VALUE.finditer(normalized))
    tokens: list[tuple[str | None, float]] = []
    cursor = 0
    for match in labelled:
        _append_bare_tokens(normalized[cursor : match.start()], tokens)
        tokens.append((match.group(1).lower(), float(match.group(2))))
        cursor = match.end()
    _append_bare_tokens(normalized[cursor:], tokens)
    if not tokens:
        raise CoordinateParseError("没有识别到坐标")
    return _points_from_tokens(tokens)


def strip_command_prefix(message: str) -> str:
    """Accept adapters that preserve the command path or only its arguments."""
    return COMMAND_PREFIX.sub("", message, count=1).strip()


def parse_weapon_argument(argument: str) -> tuple[WeaponProfile, str]:
    """Take an optional case-insensitive weapon token from a command argument."""
    parts = argument.strip().split(maxsplit=1)
    head = parts[0] if parts else ""
    tail = parts[1] if len(parts) == 2 else ""
    normalized = head.casefold()
    for weapon in WEAPONS:
        if normalized in weapon.aliases:
            if not tail.strip():
                raise CoordinateParseError(f"请在 {weapon.title} 后输入坐标")
            return weapon, tail.strip()
    return DEFAULT_WEAPON, argument.strip()


def _append_bare_tokens(fragment: str, tokens: list[tuple[str | None, float]]) -> None:
    """Append bare numbers from a gap and reject anything that is not a separator."""
    residue = BARE_NUMBER.sub("", fragment)
    if not re.fullmatch(r"[\s,;/|()]*", residue):
        raise CoordinateParseError("轴标记只能使用 x 或 y，分隔符只能使用空格或标点")
    tokens.extend(
        (None, float(match.group())) for match in BARE_NUMBER.finditer(fragment)
    )


def _points_from_tokens(tokens: list[tuple[str | None, float]]) -> list[Point]:
    """Build points while treating each bare value as the next missing x/y axis."""
    points: list[Point] = []
    current: dict[str, float] = {}
    for labelled_axis, value in tokens:
        if labelled_axis is None:
            if set(current) == {"x", "y"}:
                points.append(_point_from_values(current["x"], current["y"]))
                current = {}
            # A bare coordinate uses x then y; with one labelled axis, fill
            # whichever axis remains instead (e.g. ``x10 20``).
            axis = "x" if "x" not in current else "y"
        else:
            axis = labelled_axis
        if axis in current:
            if set(current) != {"x", "y"}:
                raise CoordinateParseError("同一组坐标中 x 或 y 重复，无法确定配对")
            points.append(_point_from_values(current["x"], current["y"]))
            current = {}
        current[axis] = value
    if set(current) != {"x", "y"}:
        raise CoordinateParseError("每组坐标必须各包含一个 x 和一个 y")
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
    directions = (
        "N(北)",
        "NE(东北)",
        "E(东)",
        "SE(东南)",
        "S(南)",
        "SW(西南)",
        "W(西)",
        "NW(西北)",
    )
    return directions[int((bearing + 22.5) // 45) % len(directions)]


def degrees_to_mils(degrees: float) -> float:
    """Convert a compass angle to NATO-style 6400-mil azimuth."""
    return degrees * 6400 / 360


def lookup_mils(distance: float, trajectory: Trajectory) -> tuple[float, ...]:
    """Look up a trajectory with linear interpolation and preserve exact ties."""
    exact = tuple(
        mil
        for range_m, mil in trajectory.table
        if math.isclose(range_m, distance, abs_tol=RANGE_EPSILON)
    )
    if exact:
        return exact
    ordered = sorted(trajectory.table)
    for (low_distance, low_mil), (high_distance, high_mil) in zip(ordered, ordered[1:]):
        if low_distance < distance < high_distance:
            ratio = (distance - low_distance) / (high_distance - low_distance)
            return (low_mil + ratio * (high_mil - low_mil),)
    raise ValueError("distance must be within trajectory range")


def format_elevation(mils: tuple[float, ...]) -> str:
    return "–".join(f"{mil:.0f}" for mil in sorted(mils)) + " MIL"
