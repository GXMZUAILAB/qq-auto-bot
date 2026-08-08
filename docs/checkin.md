# 签到功能

分时段签到，每人每时段限签一次，系统自动累计时长。

## 命令

| 命令 | 说明 |
|------|------|
| `/签到` | 在当前时段签到，成功后返回时段名称和获得时长 |
| `/签到统计` | 查看本人的今日 / 本周 / 本月 / 累计签到时长及签到天数 |

## 时段配置

编辑 `configs/checkin.yaml` 自定义时段。支持跨午夜时段（如晚上 18:00~05:00）。

默认时段：

| 时段 | 时间 | 签到可得时长 |
|------|------|-------------|
| 早上 | 05:00~09:00 | 2 小时 |
| 上午 | 09:00~12:00 | 3 小时 |
| 下午 | 12:00~18:00 | 2 小时 |
| 晚上 | 18:00~05:00 | 1 小时 |

## 数据

- 数据文件默认存储在 `data/checkin_data.db`
- 每一条签到记录包含：群号、用户 QQ、用户昵称/群名片、日期、时段、获得时长
- 默认不自动清理历史数据。如需自动清理，在 `configs/checkin.yaml` 中设置 `data.retain_days`（如 `retain_days: 90` 表示保留 90 天）

## 存储结构

```sql
records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id    TEXT NOT NULL,      -- 群号
    user_id     TEXT NOT NULL,      -- 用户 QQ
    user_name   TEXT DEFAULT '',    -- 昵称/群名片
    date        TEXT NOT NULL,      -- 签到日期
    period      TEXT NOT NULL,      -- 时段名称
    duration    INTEGER DEFAULT 0   -- 获得时长（小时）
)
```

通过 `group_id + user_id + date + period` 唯一索引保证每人每时段每天只能签到一次。
