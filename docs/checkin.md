# 签到功能

按班次签到，每人每班次每天限签一次，系统自动累计时长（小时）。

## 命令

| 命令 | 说明 |
|------|------|
| `XX楼已到`（如 `文综楼已到`） | 在当前班次签到，成功后返回班次名称和获得时长 |
| `签到统计` | 查看本人的今日 / 累计签到时长（小时） |

## 班次配置

编辑 `configs/checkin.yaml` 自定义班次。签到按当前时间落在班次的到岗 `arrive` ~ 离岗 `leave` 区间判定，命中该班次记其录入时长 `duration_hours`。

默认班次：

| 班次 | 到岗 | 离岗 | 录入时长 |
|------|------|------|---------|
| 一班次 | 07:40 | 09:20 | 2 小时 |
| 二班次 | 09:50 | 12:20 | 3 小时 |
| 三班次 | 14:10 | 15:50 | 2 小时 |
| 四班次 | 16:20 | 18:00 | 2 小时 |

## 数据

- 数据文件默认存储在 `data/checkin_data.db`
- 每一条签到记录包含：群号、用户 QQ、用户昵称/群名片、日期、班次、录入时长（小时）
- 默认不自动清理历史数据。如需自动清理，在 `configs/checkin.yaml` 中设置 `data.retain_days`（如 `retain_days: 90` 表示保留 90 天）

## 存储结构

```sql
records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id    TEXT NOT NULL,      -- 群号
    user_id     TEXT NOT NULL,      -- 用户 QQ
    user_name   TEXT DEFAULT '',    -- 昵称/群名片
    date        TEXT NOT NULL,      -- 签到日期
    period      TEXT NOT NULL,      -- 班次名称
    duration    INTEGER DEFAULT 0   -- 录入时长（小时）
)
```

通过 `group_id + user_id + date + period` 唯一索引保证每人每班次每天只能签到一次。
