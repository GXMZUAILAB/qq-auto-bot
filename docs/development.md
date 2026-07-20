# 开发文档

## 快速启动

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 确保 LLOneBot 已启动并登录 QQ

# 3. 启动机器人
python main.py
```

---

## 项目结构

```
config.yaml         ← 全局配置
configs/            ← 各功能配置文件
features/           ← 各功能代码
  checkin/          ← 签到功能
main.py             ← 启动入口（没有特殊需求不要改）
bot.py              ← LLOneBot 连接（不要改）
config.py           ← 配置读取工具（不要改）
```

---

## 加新功能（3 步）

**第 1 步：** 建功能目录和配置文件

```
mkdir features/myfeature/
touch configs/myfeature.yaml
```

**第 2 步：** 写功能代码

```python
# features/myfeature/handler.py

# 导入配置工具（读 configs/myfeature.yaml 用）
from config import load_feature_config

# 处理 /hello 命令
# bot       → 发消息、查信息全靠它
# group_id  → 群号
# user_id   → 发消息的人的 QQ 号
async def cmd_hello(bot, group_id, user_id):
    return "你好！"         # 返回字符串 = 机器人自动发到群里

async def cmd_help(bot, group_id, user_id):
    return "可用命令：/hello、/help"

# ★ 必须导出 COMMANDS，机器人才能发现你的命令
COMMANDS = {
    "/hello": cmd_hello,   # 群友发 /hello → 执行 cmd_hello
    "/help":  cmd_help,
}
```

**第 3 步：** 写配置（可选）

```yaml
# configs/myfeature.yaml
my_key: value
```

```python
# handler.py 里读配置文件的内容
cfg = load_feature_config("myfeature")   # 读 configs/myfeature.yaml
my_key = cfg.get("my_key")               # 取值，没有则返回 None
```

> **完成。** 启动时会自动发现，main.py 不需要改任何东西。

---

## 配置说明

| 文件 | 用途 |
|------|------|
| `config.yaml` | 全局配置，改 LLOneBot 地址、日志等级等 |
| `configs/checkin.yaml` | 签到功能的时段和时长 |

---

## 数据存储

想存数据的话，怎么简单怎么来。最简单的就是用 JSON 文件：

```python
import json, os

# 数据文件存哪里
DATA = "data/myfeature.json"

# 存数据：把整个数据写进文件
def save(data):
    os.makedirs("data", exist_ok=True)          # 确保目录存在
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)   # 中文不乱码

# 读数据：从文件读回来，没有就返回空字典
def load():
    if not os.path.exists(DATA):
        return {}
    with open(DATA, "r", encoding="utf-8") as f:
        return json.load(f)
```

```python
# 使用示例
d = load()       # 读取现有数据
d["score"] = 99  # 改数据
save(d)          # 存回去
```

等数据量大了、需要查询了，再换成 SQLite。怎么存没有标准答案，够用就行。

---

## 常用操作

```bash
python main.py                       # 启动
python -c "from features import discover, _commands; discover(); print(_commands.keys())"  # 查看已注册的命令
```

---

## 注意事项

- 每步功能里，**有 `COMMANDS` 字典才会被自动发现**
- handler 函数必须是 `async`
- 所有 handler 签名：`(bot, group_id, user_id)` 三个参数
- 返回 `None` 或空字符串 = 不回复
- `bot` 可用的函数：`bot.send_group_msg(群号, 内容)`、`bot.get_group_member_name(群号, QQ号)`
