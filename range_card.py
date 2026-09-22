"""Jinja view model and template for a WARDOGS sight-setting ruler."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .ballistic import CalculationResult


RANGE_CARD_TEMPLATE = """
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: #101713;
    color: #edf4e9;
    font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
  }
  .card {
    width: 920px;
    padding: 34px 40px 38px;
    background: linear-gradient(135deg, #19251d, #101713 62%);
    border: 1px solid #56634e;
  }
  .eyebrow { color: #b7c79b; font-size: 16px; letter-spacing: 2px; }
  h1 { margin: 8px 0 24px; font-size: 31px; letter-spacing: 1px; }
  .summary {
    display: flex;
    gap: 26px;
    padding: 14px 16px;
    background: #0b100d;
    border-left: 4px solid #91a96d;
    color: #cbd7c2;
    font-size: 18px;
  }
  .summary strong { color: #f5f8ef; }
  .trajectory { margin-top: 30px; }
  .trajectory-title { display: flex; justify-content: space-between; font-size: 20px; }
  .trajectory-title .setting { color: #ffcf70; font-weight: 700; }
  .ruler-wrap { position: relative; margin: 44px 16px 28px; }
  .ruler {
    height: 24px;
    border: 1px solid #849276;
    background-color: #2b382c;
    background-image: repeating-linear-gradient(90deg, transparent 0, transparent 9px,
      rgba(230, 239, 218, .42) 9px, rgba(230, 239, 218, .42) 10px);
  }
  .tick { position: absolute; top: 30px; color: #aebaa6; font-size: 15px; transform: translateX(-50%); }
  .tick::before { content: ""; position: absolute; height: 9px; border-left: 1px solid #aebaa6; top: -10px; left: 50%; }
  .pointer { position: absolute; top: -29px; transform: translateX(-50%); text-align: center; }
  .pointer .value { display: block; white-space: nowrap; color: #fff5d8; font-size: 19px; font-weight: 700; }
  .pointer .arrow { margin: 4px auto 0; width: 0; height: 0; border-left: 10px solid transparent;
    border-right: 10px solid transparent; border-top: 15px solid #e15140; }
  .range { display: flex; justify-content: space-between; margin-top: 9px; color: #aebaa6; font-size: 15px; }
  .footnote { margin-top: 30px; color: #93a08d; font-size: 14px; }
</style>
<section class="card">
  <div class="eyebrow">WARDOGS · FIRE CONTROL</div>
  <h1>{{ weapon }} 瞄准标尺</h1>
  <div class="summary">
    <span>方位 <strong>{{ bearing }}</strong></span>
    <span>距离 <strong>{{ distance }}</strong></span>
    <span>目标 <strong>{{ target }}</strong></span>
  </div>
  {% for trajectory in trajectories %}
  <div class="trajectory">
    <div class="trajectory-title">
      <span>{{ trajectory.label }}</span>
      <span class="setting">设定 {{ trajectory.setting }}</span>
    </div>
    <div class="ruler-wrap">
      <div class="ruler"></div>
      {% for tick in trajectory.ticks %}
      <span class="tick" style="left: {{ tick.position }}%">{{ tick.label }}</span>
      {% endfor %}
      {% for marker in trajectory.markers %}
      <div class="pointer" style="left: {{ marker.position }}%">
        <span class="value">{{ marker.label }}</span><span class="arrow"></span>
      </div>
      {% endfor %}
      <div class="range"><span>{{ trajectory.min_mil }} MIL</span><span>{{ trajectory.max_mil }} MIL</span></div>
    </div>
  </div>
  {% endfor %}
  <div class="footnote">标尺按当前武器射表插值；未计算高差、地形或车辆姿态修正。</div>
</section>
"""


def build_range_card_context(result: CalculationResult) -> dict[str, Any]:
    """Create JSON-like data consumed by :data:`RANGE_CARD_TEMPLATE`.

    Each available trajectory gets its own ruler, because the SPH-2 low and
    high arcs use different sight-setting scales.
    """
    assert result.mortar is not None and result.target is not None
    assert result.bearing is not None and result.distance is not None

    elevations = dict(result.elevations)
    trajectories = []
    for trajectory in result.weapon.trajectories:
        mils = elevations.get(trajectory.label)
        if not mils:
            continue

        table_mils = tuple(mil for _, mil in trajectory.table)
        min_mil, max_mil = min(table_mils), max(table_mils)
        span = max(max_mil - min_mil, 1)

        def position(mil: float) -> float:
            return max(0.0, min(100.0, (mil - min_mil) / span * 100))

        trajectories.append(
            {
                "label": trajectory.label,
                "setting": " / ".join(f"{mil:.0f} MIL" for mil in mils),
                "min_mil": min_mil,
                "max_mil": max_mil,
                "ticks": _ruler_ticks(min_mil, max_mil, position),
                "markers": tuple(
                    {
                        "label": f"{mil:.0f}",
                        "position": round(position(mil), 3),
                    }
                    for mil in sorted(mils)
                ),
            }
        )

    return {
        "weapon": result.weapon.title.removesuffix(" 弹道计算"),
        "bearing": f"{result.bearing:.1f}°",
        "distance": f"{result.distance:.0f} M",
        "target": result.target.display(),
        "trajectories": tuple(trajectories),
    }


def _ruler_ticks(min_mil: int, max_mil: int, position) -> tuple[dict[str, Any], ...]:
    """Return five readable major ticks, including both endpoints."""
    if min_mil == max_mil:
        return ({"label": str(min_mil), "position": 0.0},)
    step = max(10, math.ceil((max_mil - min_mil) / 4 / 10) * 10)
    values = list(range(min_mil, max_mil + 1, step))
    if values[-1] != max_mil:
        values.append(max_mil)
    return tuple(
        {"label": str(mil), "position": round(position(mil), 3)} for mil in values
    )
