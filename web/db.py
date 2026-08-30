import os
import re
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
    return [{"name": r["name"], "type": r["type"], "pk": r["pk"]} for r in rows]


def _pk_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    return [r["name"] for r in _columns(conn, table_name) if r["pk"] > 0]


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


def _filter_clause(
    conn: sqlite3.Connection, table_name: str, filter_col: str | None, filter_val: str | None
) -> tuple[str, tuple]:
    """构造筛选 WHERE 片段（包含匹配），字段名走白名单校验"""
    if not filter_col or not filter_val:
        return "", ()
    col_names = {r["name"] for r in _columns(conn, table_name)}
    if filter_col not in col_names:
        raise ValueError(f"筛选字段不存在: {filter_col}")
    escaped = filter_val.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f" AND {_quote_ident(filter_col)} LIKE ? ESCAPE '\\'", (f"%{escaped}%",)


def get_data(
    db_name: str,
    table_name: str,
    page: int = 1,
    size: int = 100,
    filter_col: str | None = None,
    filter_val: str | None = None,
) -> dict:
    conn = _get_conn(db_name)
    try:
        if not _resolve_table(conn, table_name):
            raise ValueError(f"表不存在: {table_name}")
        size = max(1, min(int(size), MAX_PAGE_SIZE))
        page = max(1, int(page))
        offset = (page - 1) * size

        where_sql, where_params = _filter_clause(conn, table_name, filter_col, filter_val)
        table = _quote_ident(table_name)

        total = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE 1=1{where_sql}", where_params
        ).fetchone()[0]

        pk_cols = _pk_columns(conn, table_name)
        if pk_cols:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE 1=1{where_sql} LIMIT ? OFFSET ?",
                where_params + (size, offset),
            ).fetchall()
            columns = [r["name"] for r in _columns(conn, table_name)]
            keys = [[[c, row[c]] for c in pk_cols] for row in rows]
        else:
            # 无主键时用 rowid 识别行，_rowid 不进入展示列
            rows = conn.execute(
                f"SELECT rowid AS _rowid, * FROM {table} WHERE 1=1{where_sql} LIMIT ? OFFSET ?",
                where_params + (size, offset),
            ).fetchall()
            columns = [r["name"] for r in _columns(conn, table_name)]
            keys = [[["rowid", row["_rowid"]]] for row in rows]
            rows = [[row[c] for c in columns] for row in rows]

        return {
            "columns": columns,
            "rows": [list(r) for r in rows],
            "keys": keys,
            "total": total,
            "page": page,
            "size": size,
        }
    finally:
        conn.close()


def aggregate(
    db_name: str,
    table_name: str,
    group_fields: list[str],
    sum_field: str,
) -> dict:
    """按多个字段分组、对另一字段求和"""
    conn = _get_conn(db_name)
    try:
        if not _resolve_table(conn, table_name):
            raise ValueError(f"表不存在: {table_name}")
        col_names = {r["name"] for r in _columns(conn, table_name)}
        if not group_fields:
            raise ValueError("请至少选择一个分组字段")
        for gf in group_fields:
            if gf not in col_names:
                raise ValueError(f"分组字段不存在: {gf}")
        if sum_field not in col_names:
            raise ValueError(f"汇总字段不存在: {sum_field}")

        group_sql = ", ".join(_quote_ident(gf) for gf in group_fields)
        rows = conn.execute(
            f"SELECT {group_sql}, COALESCE(SUM({_quote_ident(sum_field)}), 0) AS total "
            f"FROM {_quote_ident(table_name)} "
            f"GROUP BY {group_sql} "
            f"ORDER BY total DESC"
        ).fetchall()
        return {
            "columns": group_fields + [f"{sum_field} 汇总"],
            "rows": [list(r) for r in rows],
            "total": len(rows),
        }
    finally:
        conn.close()


def query_rows(
    db_name: str,
    table_name: str,
    fields: list[str] | None = None,
    filter_col: str | None = None,
    filter_val: str | None = None,
) -> dict:
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

        where_sql, where_params = _filter_clause(conn, table_name, filter_col, filter_val)
        col_str = ", ".join(_quote_ident(c) for c in selected)
        rows = conn.execute(
            f"SELECT {col_str} FROM {_quote_ident(table_name)} WHERE 1=1{where_sql}",
            where_params,
        ).fetchall()
        return {"columns": selected, "rows": [list(r) for r in rows]}
    finally:
        conn.close()


# ---- 增删改 ----

def _coerce(value, col_type: str | None):
    """按列类型亲和性轻量转换：数字列转数字、空串转 NULL"""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    if col_type and re.search(r"INT|REAL|NUM|DEC|FLOA|DOUB", col_type, re.I):
        try:
            return int(value)
        except (ValueError, TypeError):
            pass
        try:
            return float(value)
        except (ValueError, TypeError):
            pass
    return value


def _validate_values(conn: sqlite3.Connection, table_name: str, values: dict) -> dict:
    """列名白名单过滤，返回清洗后的 values"""
    if not isinstance(values, dict):
        raise ValueError("values 必须是对象")
    cols = {r["name"]: r["type"] for r in _columns(conn, table_name)}
    clean = {}
    for k, v in values.items():
        if k not in cols:
            raise ValueError(f"字段不存在: {k}")
        clean[k] = _coerce(v, cols[k])
    return clean


def _row_where(conn: sqlite3.Connection, table_name: str, key) -> tuple[str, tuple]:
    """由 key([[col, value], ...]) 构造 WHERE 片段，只允许主键列或 rowid"""
    if not isinstance(key, list) or not key:
        raise ValueError("缺少行标识 key")
    pk_cols = _pk_columns(conn, table_name) or ["rowid"]
    conditions, params = [], []
    for pair in key:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("key 每项应为 [列名, 值]")
        col, val = pair[0], pair[1]
        if col not in pk_cols:
            raise ValueError(f"行标识字段无效: {col}")
        conditions.append(f"{_quote_ident(col)} = ?")
        params.append(val)
    return " AND ".join(conditions), tuple(params)


def insert_row(db_name: str, table_name: str, values: dict) -> dict:
    conn = _get_conn(db_name)
    try:
        if not _resolve_table(conn, table_name):
            raise ValueError(f"表不存在: {table_name}")
        clean = _validate_values(conn, table_name, values)
        # 主键列留空则剔除，交给 SQLite 自动生成
        for c in _pk_columns(conn, table_name):
            clean.pop(c, None)
        if not clean:
            raise ValueError("没有可写入的字段")
        cols = list(clean.keys())
        sql = (
            f"INSERT INTO {_quote_ident(table_name)} "
            f"({', '.join(_quote_ident(c) for c in cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})"
        )
        cur = conn.execute(sql, list(clean.values()))
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


def update_row(db_name: str, table_name: str, key, values: dict) -> dict:
    conn = _get_conn(db_name)
    try:
        if not _resolve_table(conn, table_name):
            raise ValueError(f"表不存在: {table_name}")
        where_sql, where_params = _row_where(conn, table_name, key)
        clean = _validate_values(conn, table_name, values)
        # 不允许修改主键列
        for c in _pk_columns(conn, table_name):
            clean.pop(c, None)
        if not clean:
            raise ValueError("没有可更新的字段")
        set_sql = ", ".join(f"{_quote_ident(c)} = ?" for c in clean)
        cur = conn.execute(
            f"UPDATE {_quote_ident(table_name)} SET {set_sql} WHERE {where_sql}",
            list(clean.values()) + list(where_params),
        )
        conn.commit()
        return {"ok": True, "affected": cur.rowcount}
    finally:
        conn.close()


def delete_row(db_name: str, table_name: str, key) -> dict:
    conn = _get_conn(db_name)
    try:
        if not _resolve_table(conn, table_name):
            raise ValueError(f"表不存在: {table_name}")
        where_sql, where_params = _row_where(conn, table_name, key)
        cur = conn.execute(
            f"DELETE FROM {_quote_ident(table_name)} WHERE {where_sql}",
            where_params,
        )
        conn.commit()
        return {"ok": True, "affected": cur.rowcount}
    finally:
        conn.close()
