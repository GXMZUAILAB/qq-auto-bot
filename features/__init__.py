"""功能模块自动发现与命令路由。

规范：
- features/ 下每个子包就是一个功能模块
- 每个模块的 handler.py 必须导出 COMMANDS 字典
- COMMANDS = {"/cmd": async_handler, ...}
- handler 签名: async def handler(bot, group_id, user_id) -> str | None
  返回字符串则自动发送，返回 None 则静默
"""

import importlib
import logging
import pkgutil
from typing import Callable

logger = logging.getLogger("features")

_commands: dict[str, Callable] = {}


def discover():
    """扫描 features/ 下所有模块，收集 COMMANDS"""
    global _commands
    _commands.clear()

    for finder, name, ispkg in pkgutil.iter_modules(__path__):
        if not ispkg:
            continue
        try:
            mod = importlib.import_module(f"features.{name}.handler")
            cmds = getattr(mod, "COMMANDS", {})
            for cmd, handler in cmds.items():
                if cmd in _commands:
                    logger.warning(f"命令 {cmd} 被多个功能注册，后面的覆盖前面的")
                _commands[cmd] = handler
                logger.info(f"注册命令 [{cmd}] ← features/{name}")
        except Exception as e:
            logger.error(f"加载 features/{name} 失败: {e}")

    logger.info(f"共注册 {len(_commands)} 条命令: {list(_commands.keys())}")


async def dispatch(bot, group_id: str, user_id: str, text: str) -> str | None:
    """路由消息到对应的命令处理器"""
    handler = _commands.get(text)
    if handler is None:
        return None  # 没有匹配的命令，静默
    try:
        reply = await handler(bot, group_id, user_id)
        return reply
    except Exception as e:
        logger.exception(f"执行命令 {text} 异常: {e}")
        return f"命令执行出错: {e}"
