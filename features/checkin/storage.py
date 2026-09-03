import sqlite3
import os
from datetime import datetime, timedelta

from config import get, load_feature_config

TIMEZONE = timedelta(hours=8)
DB_FILE = get("data", "file", default="data/checkin_data.db")
RETAIN_DAYS = get("data", "retain_days", default=0)

DT_FMT = "%Y-%m-%d %H:%M:%S"


# ---- 班次配置 ----

def _parse_hhmm(s: str) -> int:
    h, m = map(int, s.split(":"))
    return h * 60 + m


def _shifts() -> list[dict]:
    """读取班次配置。

    每个班次:
      arrive_m    签到窗口开始
      signin_to_m 签到窗口截止(有 leave_tiers 的档位班次为首档时刻, 其余为 leave_m)
      leave_m     离岗/班次结束时刻
      duration    白天固定录入时长(小时)
      tiers       晚班按签退时刻给时长: 升序 [(分钟, 小时), ...], 无则 None
    """
    cfg = load_feature_config("checkin")
    shifts = []
    for s in cfg.get("checkin_shifts", []):
        arrive_m = _parse_hhmm(s["arrive"])
        leave_m = _parse_hhmm(s["leave"])
        tiers_raw = s.get("leave_tiers")
        tiers = (
            sorted((_parse_hhmm(t["at"]), t["hours"]) for t in tiers_raw)
            if tiers_raw else None
        )
        shifts.append({
            "name": s["name"],
            "duration": s.get("duration_hours", 0),
            "arrive_m": arrive_m,
            "leave_m": leave_m,
            "signin_to_m": tiers[0][0] if tiers else leave_m,
            "tiers": tiers,
        })
    return shifts


def _shift_by_name(name: str) -> dict | None:
    return next((s for s in _shifts() if s["name"] == name), None)


def _default_credit() -> int:
    cfg = load_feature_config("checkin")
    return cfg.get("checkin_default_credit", 2)


def _min_minutes() -> int:
    """签退需晚于签到的最短分钟数(防签到即签退刷时长);0 表示不限制"""
    cfg = load_feature_config("checkin")
    return int(cfg.get("checkin_min_minutes", 0) or 0)


# ---- 时间 ----

def _now() -> datetime:
    return datetime.utcnow() + TIMEZONE


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


def _current_shift() -> dict | None:
    """根据当前时间匹配签到窗口(到岗 ~ 签到窗口截止)"""
    now = _now()
    t = now.hour * 60 + now.minute
    for s in _shifts():
        if s["arrive_m"] <= t < s["signin_to_m"]:
            return s
    return None


def _at_datetime(date_str: str, minutes: int) -> datetime:
    y, m, d = map(int, date_str.split("-"))
    return datetime(y, m, d, minutes // 60, minutes % 60)


# ---- 数据库 ----

def _get_conn() -> sqlite3.Connection:
    dirname = os.path.dirname(DB_FILE)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
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
            duration    INTEGER DEFAULT 0,
            sign_in_at  TEXT,
            sign_out_at TEXT
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
    conn.commit()


def _cleanup(conn: sqlite3.Connection):
    if RETAIN_DAYS <= 0:
        return
    cutoff = (_now() - timedelta(days=RETAIN_DAYS)).strftime("%Y-%m-%d")
    conn.execute("DELETE FROM records WHERE date < ?", (cutoff,))
    conn.commit()


# ---- 签到 / 签退 ----

def _pending_rows(conn: sqlite3.Connection, group_id: str, user_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, date, period, sign_in_at FROM records "
        "WHERE group_id=? AND user_id=? AND sign_out_at IS NULL ORDER BY id",
        (group_id, user_id),
    ).fetchall()


def _expire_pending(conn: sqlite3.Connection, row: sqlite3.Row):
    """把一条已过本班次离岗时刻的待结算记录按兜底时长结算"""
    shift = _shift_by_name(row["period"])
    if shift is None:
        return
    leave_dt = _at_datetime(row["date"], shift["leave_m"])
    if _now() > leave_dt:
        conn.execute(
            "UPDATE records SET sign_out_at=?, duration=? WHERE id=?",
            (leave_dt.strftime(DT_FMT), _default_credit(), row["id"]),
        )


def _finalize_expired(conn: sqlite3.Connection, group_id: str, user_id: str):
    """把所有已过离岗时刻的待结算记录结算为兜底时长"""
    rows = _pending_rows(conn, group_id, user_id)
    if not rows:
        return
    for row in rows:
        _expire_pending(conn, row)
    conn.commit()


def checkin(group_id: str, user_id: str, user_name: str = "") -> str:
    if not group_id or not user_id:
        return "参数错误。"

    shift = _current_shift()
    if shift is None:
        return "当前不在任何班次的签到时段内。"

    now = _now()
    today = now.strftime("%Y-%m-%d")

    conn = _get_conn()
    try:
        # 先结算本人已过时的未签退班次(漏签退 → 兜底)
        _finalize_expired(conn, group_id, user_id)

        # INSERT OR IGNORE 依赖唯一索引, 消除 SELECT→INSERT 竞态, 保证每班次每天只签一次
        cur = conn.execute(
            "INSERT OR IGNORE INTO records "
            "(group_id, user_id, user_name, date, period, duration, sign_in_at) "
            "VALUES (?, ?, ?, ?, ?, 0, ?)",
            (group_id, user_id, user_name, today, shift["name"], now.strftime(DT_FMT)),
        )
        if cur.rowcount == 0:
            return f"你今天「{shift['name']}」已经签到过了。"
        conn.commit()
        _cleanup(conn)
        return f"签到成功! {shift['name']}，请离岗时发送「签退」。"
    finally:
        conn.close()


def signout(group_id: str, user_id: str) -> str:
    if not group_id or not user_id:
        return "参数错误。"

    conn = _get_conn()
    try:
        now = _now()
        rows = _pending_rows(conn, group_id, user_id)
        if not rows:
            return "今天没有需要签退的班次。"

        # 只结算最近一条; 更早的未签退班次视为漏签退 → 兜底
        for row in rows[:-1]:
            _expire_pending(conn, row)
        conn.commit()
        target = rows[-1]

        # 最短在岗限制: 防止签到即签退刷时长
        min_m = _min_minutes()
        if min_m > 0 and target["sign_in_at"]:
            sign_in_dt = datetime.strptime(target["sign_in_at"], DT_FMT)
            waited = int((now - sign_in_dt).total_seconds() // 60)
            if waited < min_m:
                return f"签到满 {min_m} 分钟才能签退(已 {waited} 分钟)。"

        shift = _shift_by_name(target["period"])
        hours = _signout_hours(shift, now)
        conn.execute(
            "UPDATE records SET sign_out_at=?, duration=? WHERE id=?",
            (now.strftime(DT_FMT), hours, target["id"]),
        )
        conn.commit()
        _cleanup(conn)
        return f"签退成功! {target['period']} +{_format_duration(hours)}"
    finally:
        conn.close()


def _signout_hours(shift: dict | None, now: datetime) -> int:
    if shift is not None and shift["tiers"]:
        m = now.hour * 60 + now.minute
        for at_m, hours in shift["tiers"]:
            if m <= at_m:
                return hours
        return shift["tiers"][-1][1]  # 超过最后一档按最高档
    return shift["duration"] if shift else _default_credit()


def statistics(group_id: str, user_id: str) -> str:
    conn = _get_conn()
    try:
        # 把已过时未签退的班次结算掉, 统计才准确
        _finalize_expired(conn, group_id, user_id)

        today = _today_str()
        today_sum = conn.execute(
            "SELECT COALESCE(SUM(duration), 0) FROM records WHERE group_id=? AND user_id=? AND date=?",
            (group_id, user_id, today),
        ).fetchone()[0]
        total_sum = _get_total(conn, group_id, user_id)
        pending = len(_pending_rows(conn, group_id, user_id))

        msg = (
            f"今日: {_format_duration(today_sum)}\n"
            f"累计: {_format_duration(total_sum)}"
        )
        if pending:
            msg += f"\n另有 {pending} 个班次待签退"
        return msg
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
