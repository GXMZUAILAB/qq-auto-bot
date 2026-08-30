import sqlite3
import os
from datetime import datetime, timedelta

from config import get, load_feature_config

TIMEZONE = timedelta(hours=8)
DB_FILE = get("data", "file", default="data/checkin_data.db")
RETAIN_DAYS = get("data", "retain_days", default=0)


def _shifts() -> list[dict]:
    """读取班次配置"""
    cfg = load_feature_config("checkin")
    raw = cfg.get("checkin_shifts", [])
    shifts = []
    for s in raw:
        ah, am = map(int, s["arrive"].split(":"))
        lh, lm = map(int, s["leave"].split(":"))
        shifts.append({
            "name": s["name"],
            "duration": s["duration_hours"],
            "arrive_m": ah * 60 + am,
            "leave_m": lh * 60 + lm,
        })
    return shifts


def _now() -> datetime:
    return datetime.utcnow() + TIMEZONE


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


def _current_shift() -> dict | None:
    """根据当前时间匹配对应班次（到岗 ~ 离岗）"""
    now = _now()
    t = now.hour * 60 + now.minute

    for s in _shifts():
        if s["arrive_m"] <= t < s["leave_m"]:
            return s
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
            user_name   TEXT DEFAULT '',
            date        TEXT NOT NULL,
            period      TEXT NOT NULL,
            duration    INTEGER DEFAULT 0
        )
    """)
    # 兼容旧表：为已有 records 表补上 user_name 列
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(records)").fetchall()}
    if "user_name" not in cols:
        conn.execute("ALTER TABLE records ADD COLUMN user_name TEXT DEFAULT ''")
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


def checkin(group_id: str, user_id: str, user_name: str = "") -> str:
    if not group_id or not user_id:
        return "参数错误。"

    shift = _current_shift()
    if shift is None:
        return "当前不在任何班次的到岗~离岗时段内。"

    today = _today_str()

    conn = _get_conn()
    try:
        # 检查该班次是否已签到
        row = conn.execute(
            "SELECT id FROM records WHERE group_id=? AND user_id=? AND date=? AND period=?",
            (group_id, user_id, today, shift["name"]),
        ).fetchone()

        if row:
            return f"你今天「{shift['name']}」已经签到过了。"

        duration = shift["duration"]
        conn.execute(
            "INSERT INTO records (group_id, user_id, user_name, date, period, duration) VALUES (?, ?, ?, ?, ?, ?)",
            (group_id, user_id, user_name, today, shift["name"], duration),
        )
        conn.commit()
        _cleanup(conn)

        return f"签到成功! {shift['name']} +{_format_duration(duration)}"
    finally:
        conn.close()


def statistics(group_id: str, user_id: str) -> str:
    conn = _get_conn()
    try:
        today = _today_str()
        today_minutes = conn.execute(
            "SELECT COALESCE(SUM(duration), 0) FROM records WHERE group_id=? AND user_id=? AND date=?",
            (group_id, user_id, today),
        ).fetchone()[0]
        total_minutes = _get_total(conn, group_id, user_id)

        return (
            f"今日: {_format_duration(today_minutes)}\n"
            f"累计: {_format_duration(total_minutes)}"
        )
    finally:
        conn.close()


# ---- 内部辅助 ----

def _get_total(conn: sqlite3.Connection, group_id: str, user_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(duration), 0) FROM records WHERE group_id=? AND user_id=?",
        (group_id, user_id),
    ).fetchone()
    return row[0]


def _format_duration(hours: int) -> str:
    return f"{hours}小时" if hours > 0 else "0小时"
