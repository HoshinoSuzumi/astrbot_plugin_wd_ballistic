"""AstrBot entry point for the WARDOGS mortar calculator."""

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .ballistic import BallisticCalculator, CoordinateParseError, strip_command_prefix


class WARDOGSBallisticPlugin(Star):
    """Calculate WARDOGS mortar bearing and distance for a chat user."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.calculator = BallisticCalculator(cache_ttl_seconds=105 * 60)

    @filter.command("wdbc")
    async def wardogs_ballistic(self, event: AstrMessageEvent):
        """计算迫击炮方位和距离：/wdbc <炮位> <目标位>，或 /wdbc <目标位>。"""
        try:
            result = self.calculator.calculate(
                user_id=self._user_key(event), argument=strip_command_prefix(event.message_str)
            )
        except CoordinateParseError as exc:
            yield event.plain_result(f"坐标无法识别：{exc}\n{self.calculator.usage}")
            return

        if result.needs_mortar:
            yield event.plain_result(
                "尚未保存你的炮位坐标。请先使用两组坐标，例如：\n"
                "/wdbc x64.85, y71.98 x74.85, y61.13"
            )
            return

        yield event.plain_result(result.format_message())

    @staticmethod
    def _user_key(event: AstrMessageEvent) -> str:
        """Namespace the sender ID by platform so IDs cannot collide across adapters."""
        return f"{event.get_platform_name()}:{event.get_sender_id()}"
