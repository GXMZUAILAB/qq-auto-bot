import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from web import db, excel

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def create_app() -> FastAPI:
    app = FastAPI(title="QQ Bot 数据统计")

    @app.get("/api/databases")
    def api_databases():
        return {"databases": db.list_databases()}

    @app.get("/api/tables")
    def api_tables(db_name: str = Query(alias="db")):
        try:
            return {"tables": db.list_tables(db_name)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/data")
    def api_data(
        db_name: str = Query(alias="db"),
        table_name: str = Query(alias="table"),
        page: int = 1,
        size: int = 100,
        filter_col: str = Query(alias="filter_col", default=""),
        filter_val: str = Query(alias="filter_val", default=""),
    ):
        try:
            return db.get_data(
                db_name, table_name, page, size, filter_col or None, filter_val or None
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/aggregate")
    def api_aggregate(
        db_name: str = Query(alias="db"),
        table_name: str = Query(alias="table"),
        group_by: str = Query(alias="group_by"),
        sum_field: str = Query(alias="sum"),
    ):
        try:
            group_fields = [g.strip() for g in group_by.split(",") if g.strip()]
            return db.aggregate(db_name, table_name, group_fields, sum_field)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/row")
    async def api_insert_row(request: Request):
        body = await request.json()
        db_name, table_name = body.get("db"), body.get("table")
        try:
            return db.insert_row(db_name, table_name, body.get("values", {}))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.put("/api/row")
    async def api_update_row(request: Request):
        body = await request.json()
        db_name, table_name = body.get("db"), body.get("table")
        try:
            return db.update_row(db_name, table_name, body.get("key"), body.get("values", {}))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.delete("/api/row")
    async def api_delete_row(request: Request):
        body = await request.json()
        db_name, table_name = body.get("db"), body.get("table")
        try:
            return db.delete_row(db_name, table_name, body.get("key"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/export")
    def api_export(
        db_name: str = Query(alias="db"),
        table_name: str = Query(alias="table"),
        fields: str = "",
        group_by: str = Query(alias="group_by", default=""),
        sum_field: str = Query(alias="sum", default=""),
        filter_col: str = Query(alias="filter_col", default=""),
        filter_val: str = Query(alias="filter_val", default=""),
    ):
        try:
            fc, fv = filter_col or None, filter_val or None
            if group_by and sum_field:
                group_fields = [g.strip() for g in group_by.split(",") if g.strip()]
                content = excel.export_aggregate_xlsx(db_name, table_name, group_fields, sum_field)
            else:
                field_list = [f.strip() for f in fields.split(",") if f.strip()] or None
                content = excel.export_xlsx(db_name, table_name, field_list, fc, fv)
            filename = f"{db_name}_{table_name}.xlsx"
            return Response(
                content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


async def start(host: str, port: int):
    from uvicorn import Config, Server

    server = Server(Config(create_app(), host=host, port=port, log_level="info"))
    await server.serve()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8000, log_level="info")
