import sqlite3
import os
from datetime import datetime, timedelta

from config import get, load_feature_config

TIMEZONE = timedelta(hours=8)
DB_FILE = get("data", "file", default="data/checkin_data.db")
RETAIN_DAYS = get("data", "retain_days", default=90)


def _periods() -> list[dict]:
    """读取签到时段配置，将 duration_hours 转为秒"""
    cfg = load_feature_config("checkin")
    raw = cfg.get("checkin_periods", [])
    return [{
        "name": p["name"],
        "start": p["start"],
        "end": p["end"],
        "duration": p["duration_hours"] * 3600,
    } for p in raw]


def _now() -> datetime:
    return datetime.utcnow() + TIMEZONE


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


def _week_range() -> tuple[str, str]:
    today = _now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def _month_str() -> str:
    return _now().strftime("%Y-%m")


def _current_period() -> dict | None:
    """根据当前时间匹配对应的时段"""
    now = _now()
    t = now.hour * 60 + now.minute  # 当前分钟数

    for p in _periods():
        sh, sm = map(int, p["start"].split(":"))
        eh, em = map(int, p["end"].split(":"))
        start_m = sh * 60 + sm
        end_m = eh * 60 + em

        if start_m <= end_m:
            # 正常时段（如 09:00~12:00）
            if start_m <= t < end_m:
                return p
        else:
            # 跨午夜时段（如 18:00~05:00）
            if t >= start_m or t < end_m:
                return p
    return None


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            date        TEXT NOT NULL,
            period      TEXT NOT NULL,
            duration    INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_records_unique
            ON records(group_id, user_id, date, period)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_records_cleanup
            ON records(date)
    """)


def _cleanup(conn: sqlite3.Connection):
    if RETAIN_DAYS <= 0:
        return
    cutoff = (_now() - timedelta(days=RETAIN_DAYS)).strftime("%Y-%m-%d")
    conn.execute("DELETE FROM records WHERE date < ?", (cutoff,))
    conn.commit()


def checkin(group_id: str, user_id: str) -> str:
    if not group_id or not user_id:
        return "参数错误。"

    period = _current_period()
    if period is None:
        return "当前不在可签到时段内。"

    now = _now()
    today = _today_str()

    conn = _get_conn()
    try:
        # 检查该时段是否已签到
        row = conn.execute(
            "SELECT id FROM records WHERE group_id=? AND user_id=? AND date=? AND period=?",
            (group_id, user_id, today, period["name"]),
        ).fetchone()

        if row:
            return f"你今天「{period['name']}」已经签到过了。"

        duration = period["duration"]
        conn.execute(
            "INSERT INTO records (group_id, user_id, date, period, duration) VALUES (?, ?, ?, ?, ?)",
            (group_id, user_id, today, period["name"], duration),
        )
        conn.commit()
        _cleanup(conn)

        total = _get_total(conn, group_id, user_id)
        return (
            f"签到成功！时段: {period['name']}\n"
            f"+{_format_duration(duration)}\n"
            f"累计时长: {_format_duration(total)}"
        )
    finally:
        conn.close()


def statistics(group_id: str, user_id: str) -> str:
    conn = _get_conn()
    try:
        today = _today_str()
        week_start, week_end = _week_range()
        month = _month_str()

        today_sec = _sum(conn, group_id, user_id, "date=?", (today,))
        week_sec = _sum(conn, group_id, user_id, "date BETWEEN ? AND ?", (week_start, week_end))
        month_sec = _sum(conn, group_id, user_id, "date LIKE ?", (month + "%",))
        total_sec = _get_total(conn, group_id, user_id)
        days_count = conn.execute(
            "SELECT COUNT(DISTINCT date) FROM records WHERE group_id=? AND user_id=? AND duration>0",
            (group_id, user_id),
        ).fetchone()[0]

        return (
            f"📊 签到统计\n"
            f"今日: {_format_duration(today_sec)}\n"
            f"本周: {_format_duration(week_sec)}\n"
            f"本月: {_format_duration(month_sec)}\n"
            f"累计: {_format_duration(total_sec)}\n"
            f"签到天数: {days_count} 天"
        )
    finally:
        conn.close()


async def ranking(group_id: str, name_resolver=None) -> str:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT user_id, SUM(duration) as total FROM records WHERE group_id=? AND duration>0 GROUP BY user_id ORDER BY total DESC LIMIT 10",
            (group_id,),
        ).fetchall()

        if not rows:
            return "本群暂无签到数据。"

        lines = ["🏆 签到时长排行"]
        for i, row in enumerate(rows, 1):
            dur = _format_duration(row["total"])
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            name = await name_resolver(row["user_id"]) if name_resolver else row["user_id"]
            lines.append(f"{medal} {name} — {dur}")

        return "\n".join(lines)
    finally:
        conn.close()


# ---- 内部辅助 ----

def _get_total(conn: sqlite3.Connection, group_id: str, user_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(duration), 0) FROM records WHERE group_id=? AND user_id=?",
        (group_id, user_id),
    ).fetchone()
    return row[0]


def _sum(conn: sqlite3.Connection, group_id: str, user_id: str, where: str, params: tuple) -> int:
    row = conn.execute(
        f"SELECT COALESCE(SUM(duration), 0) FROM records WHERE group_id=? AND user_id=? AND {where}",
        (group_id, user_id) + params,
    ).fetchone()
    return row[0]


def _format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}小时{minutes}分" if minutes else f"{hours}小时"
    else:
        return f"{minutes}分"
