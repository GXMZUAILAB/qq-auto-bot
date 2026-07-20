import asyncio
from . import storage


async def _checkin(bot, group_id: str, user_id: str) -> str:
    return await asyncio.to_thread(storage.checkin, group_id, user_id)


async def _statistics(bot, group_id: str, user_id: str) -> str:
    return await asyncio.to_thread(storage.statistics, group_id, user_id)


async def _ranking(bot, group_id: str, user_id: str) -> str:
    name_cache = {}

    async def resolve_name(uid: str) -> str:
        if uid not in name_cache:
            name_cache[uid] = await bot.get_group_member_name(group_id, uid)
        return name_cache[uid]

    return await storage.ranking(group_id, resolve_name)


COMMANDS = {
    "/签到": _checkin,
    "/签到统计": _statistics,
    "/签到排行": _ranking,
}
