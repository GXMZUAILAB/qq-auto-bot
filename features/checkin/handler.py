import asyncio
import re
from . import storage


def _extract_hours(text: str) -> int | None:
    m = re.search(r"\+(\d+)\s*$", text)
    return int(m.group(1)) if m else None


async def _checkin(bot, group_id: str, user_id: str, text: str) -> str:
    user_name = await bot.get_group_member_name(group_id, user_id)
    return await asyncio.to_thread(storage.checkin, group_id, user_id, user_name, _extract_hours(text))


# 签到触发词："文综楼已到"、"博达楼已到" 等 "XX楼已到"；晚班可带 +N 后缀指定时长
COMMAND_PATTERNS = {
    r"^[\u4e00-\u9fa5]+楼已到(?:\+\d{1,2})?$": _checkin,
}
