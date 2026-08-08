import asyncio
from . import storage


async def _checkin(bot, group_id: str, user_id: str) -> str:
    user_name = await bot.get_group_member_name(group_id, user_id)
    return await asyncio.to_thread(storage.checkin, group_id, user_id, user_name)


async def _statistics(bot, group_id: str, user_id: str) -> str:
    return await asyncio.to_thread(storage.statistics, group_id, user_id)


COMMANDS = {
    "/签到": _checkin,
    "/签到统计": _statistics,
}
