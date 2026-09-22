"""AstrBot entry point for the WARDOGS mortar calculator."""

import logging

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.command import GreedyStr

from .ballistic import (
    BallisticCalculator,
    CoordinateParseError,
    parse_weapon_argument,
)
from .range_card import RANGE_CARD_TEMPLATE, build_range_card_context


logger = logging.getLogger(__name__)


class WARDOGSBallisticPlugin(Star):
    """Calculate WARDOGS mortar bearing and distance for a chat user."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.calculator = BallisticCalculator(cache_ttl_seconds=105 * 60)

    @filter.command_group("wd", alias={"wardogs", "战狗"})
    def wardogs():
        """WARDOGS 游戏工具。"""

    @wardogs.command("bc", alias={"弹道", "弹道计算", "ballistic"})
    async def wardogs_ballistic(
        self, event: AstrMessageEvent, coordinates: GreedyStr
    ):
        """输入：[l81|sph2] <炮位> <目标位>；已缓存炮位时只需 <目标位>。"""
        try:
            weapon, coordinates = parse_weapon_argument(coordinates)
            result = self.calculator.calculate(
                user_id=self._user_key(event), weapon=weapon, argument=coordinates
            )
        except CoordinateParseError as exc:
            yield event.plain_result(f"坐标无法识别：{exc}\n{self.calculator.usage}")
            return

        if result.needs_mortar:
            yield event.plain_result(
                f"尚未保存你的 {result.weapon.title} 炮位坐标。请先使用两组坐标，例如：\n"
                f"/wd bc {result.weapon.id} x64.85, y71.98 x74.85, y61.13"
            )
            return

        yield event.plain_result(result.format_message())
        if not result.elevations:
            return

        try:
            image_url = await self.html_render(
                RANGE_CARD_TEMPLATE,
                build_range_card_context(result),
                options={"type": "png", "animations": "disabled"},
            )
        except Exception:
            # The textual firing solution remains useful if the optional
            # AstrBot HTML-to-image service is unavailable or misconfigured.
            logger.exception("Failed to render WARDOGS sight ruler")
            return

        yield event.image_result(image_url)

    @staticmethod
    def _user_key(event: AstrMessageEvent) -> str:
        """Namespace the sender ID by platform so IDs cannot collide across adapters."""
        return f"{event.get_platform_name()}:{event.get_sender_id()}"
