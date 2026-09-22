"""Jinja view model and template for a WARDOGS sight-setting ruler."""

from __future__ import annotations

from bisect import bisect_left
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
  h1 { margin: 8px 0 24px; font-size: 31px; letter-spacing: 1px; }
  .summary {
    display: flex;
    gap: 12px;
    padding: 14px 16px;
    background: #0b100d;
    border-left: 4px solid #91a96d;
    color: #cbd7c2;
    font-size: 12px;
  }
  .summary strong { color: #f5f8ef; font-size: 18px; }
  .trajectory { margin-top: 32px; }
  .trajectory-title { display: flex; justify-content: space-between; font-size: 20px; }
  .trajectory-title .setting { color: #ffcf70; font-weight: 700; }
  .ruler-wrap { position: relative; height: 388px; margin: 26px 90px 18px; }
  .ruler { position: absolute; left: 50%; top: 0; bottom: 0; width: 8px; transform: translateX(-50%);
    border: 1px solid #849276; background: linear-gradient(#607257, #293729 12%, #293729 88%, #607257); }
  .tick { position: absolute; left: 50%; width: 168px; height: 1px; border-top: 1px solid #d1dbc8;
    transform: translateY(-50%); color: #dce6d4; font-size: 17px; }
  .tick::after { content: attr(data-mil); position: absolute; left: 182px; top: -12px; white-space: nowrap; }
  .tick.major { width: 206px; border-color: #f1f6eb; }
  .pointer { position: absolute; left: 50%; width: 250px; height: 1px; border-top: 2px solid #e15140;
    transform: translateY(-50%); }
  .pointer .value { position: absolute; right: 264px; top: -15px; white-space: nowrap; color: #fff5d8;
    font-size: 19px; font-weight: 700; }
  .pointer .arrow { position: absolute; left: -2px; top: -7px; width: 0; height: 0;
    border-top: 7px solid transparent; border-bottom: 7px solid transparent; border-left: 12px solid #e15140; }
  .footnote { margin-top: 30px; color: #93a08d; font-size: 14px; }
</style>
<section class="card">
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
      <span class="tick {% if tick.is_bound %}major{% endif %}" data-mil="{{ tick.label }} MIL" style="top: {{ tick.position }}%; opacity: {{ tick.opacity }}"></span>
      {% endfor %}
      {% for marker in trajectory.markers %}
      <div class="pointer" style="top: {{ marker.position }}%">
        <span class="value">目标 {{ marker.label }} MIL</span><span class="arrow"></span>
      </div>
      {% endfor %}
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

        trajectories.append(
            {
                "label": trajectory.label,
                "setting": " / ".join(f"{mil:.0f} MIL" for mil in mils),
                **_local_ruler(tuple(mil for _, mil in trajectory.table), mils),
            }
        )

    return {
        "weapon": result.weapon.title.removesuffix(" 弹道计算"),
        "bearing": f"{result.bearing:.1f}°",
        "distance": f"{result.distance:.0f} M",
        "target": result.target.display(),
        "trajectories": tuple(trajectories),
    }


def _local_ruler(
    table_mils: tuple[int, ...], target_mils: tuple[float, ...]
) -> dict[str, Any]:
    """Build a short local scale around the target's enclosing table marks."""
    values = tuple(sorted(set(table_mils)))
    primary = target_mils[0]
    insertion = bisect_left(values, primary)

    if insertion < len(values) and values[insertion] == primary:
        lower_index = max(0, insertion - 1)
        upper_index = min(len(values) - 1, insertion + 1)
    else:
        lower_index = max(0, insertion - 1)
        upper_index = min(len(values) - 1, insertion)

    start = max(0, lower_index - 2)
    end = min(len(values) - 1, upper_index + 2)
    displayed = values[start : end + 1]
    min_display, max_display = displayed[0], displayed[-1]
    span = max(max_display - min_display, 1)

    def position(mil: float) -> float:
        # Sight settings increase from top to bottom, matching the in-game ruler.
        return max(0.0, min(100.0, (mil - min_display) / span * 100))

    bounds = {values[lower_index], values[upper_index]}
    return {
        "ticks": tuple(
            {
                "label": str(mil),
                "position": round(position(mil), 3),
                "is_bound": mil in bounds,
                "opacity": _tick_opacity(values.index(mil), lower_index, upper_index),
            }
            for mil in displayed
        ),
        "markers": tuple(
            {"label": f"{mil:.0f}", "position": round(position(mil), 3)}
            for mil in sorted(target_mils)
        ),
    }


def _tick_opacity(index: int, lower_index: int, upper_index: int) -> float:
    """Fade extension ticks while retaining the target's enclosing marks."""
    distance = min(abs(index - lower_index), abs(index - upper_index))
    return 1.0 if distance == 0 else 0.68 if distance == 1 else 0.38
