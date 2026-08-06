import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
MAX_PAGE_SIZE = 500


def _db_files() -> dict[str, str]:
    """扫描 data/ 目录下所有 .db 文件，返回 {文件名: 绝对路径}"""
    if not os.path.isdir(DATA_DIR):
        return {}
    return {
        name: os.path.join(DATA_DIR, name)
        for name in os.listdir(DATA_DIR)
        if name.endswith(".db")
    }


def list_databases() -> list[str]:
    return sorted(_db_files().keys())


def _resolve_db(name: str) -> str | None:
    return _db_files().get(name)


def _get_conn(db_name: str) -> sqlite3.Connection:
    path = _resolve_db(db_name)
    if path is None:
        raise ValueError(f"数据库不存在: {db_name}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _columns(conn: sqlite3.Connection, table_name: str) -> list[dict]:
    rows = conn.execute(f"PRAGMA table_info({_quote_ident(table_name)})").fetchall()
    return [{"name": r["name"], "type": r["type"]} for r in rows]


def _resolve_table(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone() is not None


def list_tables(db_name: str) -> list[dict]:
    """列出库内所有表及其列信息"""
    conn = _get_conn(db_name)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [
            {"name": r["name"], "columns": _columns(conn, r["name"])}
            for r in rows
        ]
    finally:
        conn.close()


def get_data(db_name: str, table_name: str, page: int = 1, size: int = 100) -> dict:
    conn = _get_conn(db_name)
    try:
        if not _resolve_table(conn, table_name):
            raise ValueError(f"表不存在: {table_name}")
        size = max(1, min(int(size), MAX_PAGE_SIZE))
        page = max(1, int(page))
        offset = (page - 1) * size

        total = conn.execute(f"SELECT COUNT(*) FROM {_quote_ident(table_name)}").fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM {_quote_ident(table_name)} LIMIT ? OFFSET ?",
            (size, offset),
        ).fetchall()
        columns = [r["name"] for r in _columns(conn, table_name)]

        return {
            "columns": columns,
            "rows": [list(r) for r in rows],
            "total": total,
            "page": page,
            "size": size,
        }
    finally:
        conn.close()


def aggregate(db_name: str, table_name: str, group_by: str, sum_field: str) -> dict:
    """按指定字段分组、对另一字段求和"""
    conn = _get_conn(db_name)
    try:
        if not _resolve_table(conn, table_name):
            raise ValueError(f"表不存在: {table_name}")
        col_names = {r["name"] for r in _columns(conn, table_name)}
        if group_by not in col_names:
            raise ValueError(f"分组字段不存在: {group_by}")
        if sum_field not in col_names:
            raise ValueError(f"汇总字段不存在: {sum_field}")

        rows = conn.execute(
            f"SELECT {_quote_ident(group_by)} AS g, "
            f"COALESCE(SUM({_quote_ident(sum_field)}), 0) AS total "
            f"FROM {_quote_ident(table_name)} "
            f"GROUP BY {_quote_ident(group_by)} "
            f"ORDER BY total DESC"
        ).fetchall()
        return {
            "columns": [group_by, f"{sum_field} 汇总"],
            "rows": [list(r) for r in rows],
            "total": len(rows),
        }
    finally:
        conn.close()


def query_rows(db_name: str, table_name: str, fields: list[str] | None = None) -> dict:
    """按字段白名单查询整表数据，供导出使用"""
    conn = _get_conn(db_name)
    try:
        if not _resolve_table(conn, table_name):
            raise ValueError(f"表不存在: {table_name}")
        all_cols = [r["name"] for r in _columns(conn, table_name)]

        if fields:
            selected = [f for f in fields if f in all_cols]
            if not selected:
                raise ValueError("没有有效的导出字段")
        else:
            selected = all_cols

        col_str = ", ".join(_quote_ident(c) for c in selected)
        rows = conn.execute(
            f"SELECT {col_str} FROM {_quote_ident(table_name)}"
        ).fetchall()
        return {"columns": selected, "rows": [list(r) for r in rows]}
    finally:
        conn.close()
