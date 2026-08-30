import asyncio
from . import storage


async def _checkin(bot, group_id: str, user_id: str) -> str:
    user_name = await bot.get_group_member_name(group_id, user_id)
    return await asyncio.to_thread(storage.checkin, group_id, user_id, user_name)


async def _statistics(bot, group_id: str, user_id: str) -> str:
    return await asyncio.to_thread(storage.statistics, group_id, user_id)


COMMANDS = {
    "签到统计": _statistics,
}

# 签到触发词："文综楼已到"、"博达楼已到" 等 "XX楼已到"
COMMAND_PATTERNS = {
    r"^[\u4e00-\u9fa5]+楼已到$": _checkin,
}
