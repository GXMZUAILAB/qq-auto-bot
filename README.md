# qq-auto-bot

实验室群聊智能回复机器人二次开发项目

基于 LLOneBot (OneBot v11) + Python，支持功能模块自动发现，开箱即用。

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

## 项目结构

```
config.yaml        ← 全局配置
configs/           ← 各功能独立配置
features/          ← 功能代码（自动发现，加新功能无需改 main.py）
docs/              ← 开发文档
```

## 已有功能

- **签到** — 分时段签到，每人每时段限签一次，自动累计时长

## 开发文档

详见 `docs/` 目录：

- `development.md` — 新手入门，3 步加新功能
- `api.md` — 框架 API 速查
- `qqbot-api.md` — QQ 机器人 API 速查
