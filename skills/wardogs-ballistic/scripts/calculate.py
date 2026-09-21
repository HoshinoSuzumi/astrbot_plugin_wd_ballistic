#!/usr/bin/env python3
"""Standalone two-point WARDOGS calculator for the bundled Agent Skill.

Usage: python calculate.py 'x64.85,y71.98' 'x74.85,y61.13'
"""

import math
import re
import sys

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
AXIS = re.compile(rf"(?i)([xy])\s*[:=]?\s*({NUMBER})")


def parse_point(value: str) -> tuple[float, float]:
    labelled = {axis.lower(): float(number) for axis, number in AXIS.findall(value)}
    if set(labelled) == {"x", "y"}:
        return labelled["x"], labelled["y"]
    values = [float(item) for item in re.findall(NUMBER, value)]
    if len(values) != 2:
        raise ValueError("每个位置必须有一组 x、y 坐标")
    return values[0], values[1]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("用法：calculate.py '<炮位>' '<目标位>'")
    mortar, target = parse_point(sys.argv[1]), parse_point(sys.argv[2])
    dx, dy = target[0] - mortar[0], target[1] - mortar[1]
    degrees = math.degrees(math.atan2(dx, dy)) % 360
    distance_m = math.hypot(dx, dy) * 100
    print(f"bearing_degrees={degrees:.1f}")
    print(f"bearing_mil={degrees * 6400 / 360:.0f}")
    print(f"distance_m={distance_m:.0f}")


if __name__ == "__main__":
    main()
