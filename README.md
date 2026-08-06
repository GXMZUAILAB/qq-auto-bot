# 🤖 qq-auto-bot

实验室群聊智能回复机器人二次开发项目

基于 LLOneBot (OneBot v11) + Python，支持功能模块自动发现，开箱即用。

## 🚀 快速开始

### 1. 启动后端（LLOneBot）

双击 `LLOneBot-win-x64-ffmpeg/llonebot.exe`，登录 QQ。

> LLOneBot 启动后会在本地开启端口 3000（HTTP API）和 3001（WebSocket）。

### 2. 启动机器人

```bash
pip install -r requirements.txt
python main.py
```

## 📁 项目结构

```
config.yaml        ← 全局配置（含 web 网页服务配置）
configs/           ← 各功能独立配置
features/          ← 功能代码（自动发现，加新功能无需改 main.py）
web/               ← 网页数据统计（FastAPI 后端 + 前端页面）
docs/              ← 开发文档
```

## ✅ 已有功能

- [**签到**](docs/checkin.md) — 分时段签到，每人每时段限签一次，按小时累计时长
- **数据统计** — 网页查看所有数据表，支持分页浏览、按字段分组汇总、勾选字段导出 Excel（默认关闭）
- **Demo** — 功能开发示例（默认禁用，配置开启后输入 `/烤肠` 触发）

## 🌐 网页数据统计

默认关闭。启用方法：将 `config.yaml` 中 `web.enabled` 改为 `true` 后启动机器人，访问 `http://127.0.0.1:8000`。

- 左侧选择数据库和表查看数据，表格区域内部滚动，支持分页
- **数据** 模式：查看原始数据，表头可勾选字段，点击「导出 Excel」下载所选列
- **统计** 模式：选择「分组字段 + 汇总字段」自动汇总（如按 `user_id` 分组求和 `duration` 得到每人总时长），也可导出 Excel
- 只监听 `127.0.0.1`，仅本机可访问；库名/表名/字段名均做白名单校验

## 📖 开发文档

详见 `docs/` 目录：

- [`development.md`](docs/development.md) — 新手入门，3 步加新功能
- [`api.md`](docs/api.md) — 框架 API 速查
- [`qqbot-api.md`](docs/qqbot-api.md) — QQ 机器人 API 速查
- [`mirai-deploy.md`](docs/mirai-deploy.md) — Overflow (Mirai) 部署与 AutoReply 自动回复教程
