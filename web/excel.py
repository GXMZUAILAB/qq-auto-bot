from io import BytesIO

from openpyxl import Workbook

from . import db


def _safe_sheet_name(name: str) -> str:
    for ch in '[]:*?/\\':
        name = name.replace(ch, "_")
    return name[:31] or "sheet"


def _build_xlsx(table_name: str, columns: list[str], rows: list) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = _safe_sheet_name(table_name)
    ws.append(columns)
    for row in rows:
        ws.append(row)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def export_xlsx(db_name: str, table_name: str, fields: list[str] | None) -> bytes:
    result = db.query_rows(db_name, table_name, fields)
    return _build_xlsx(table_name, result["columns"], result["rows"])


def export_aggregate_xlsx(db_name: str, table_name: str, group_by: str, sum_field: str) -> bytes:
    result = db.aggregate(db_name, table_name, group_by, sum_field)
    return _build_xlsx(table_name, result["columns"], result["rows"])
