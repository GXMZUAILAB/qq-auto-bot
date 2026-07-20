from config import load_feature_config


async def _demo(bot, group_id, user_id):
    # 检查功能是否启用，未启用时不回复
    cfg = load_feature_config("demo") # 读取自定义的 demo.yaml 配置文件
    if not cfg.get("enabled", False):  # cfg.get("enabled") 读取 enabled 的值
        return None

    return "晚上早点睡，梦里啥都有"

# 注册指令
# 格式：指令名: 函数名
COMMANDS = {
    "烤肠": _demo,   # 指令不一定要带 /，也可以是 "/烤肠"
}