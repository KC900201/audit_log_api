from datetime import datetime, timedelta
from typing import Union, List
from uuid import UUID
import io, csv

from fastapi import APIRouter, status, HTTPException, Response, Depends
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import  Json
from starlette.responses import StreamingResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from db import curr, commit
from auth import verify_jwt
from utils import send_log_to_sqs, index_log_to_opensearch
import schemas

router = APIRouter(prefix="/logs")

# Set up connection manager for broadcasting
class ConnectionManager:
    def __init__(self):
        self.active: dict[UUID, list[WebSocket]] = {}

    async def connect(self, tenant_id: UUID, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(tenant_id, []).append(ws)

    def disconnect(self, tenant_id: UUID, ws: WebSocket):
        conns = self.active.get(tenant_id, [])
        if ws in conns:
            conns.remove(ws)
            if not conns:
                del self.active[tenant_id]

    async def broadcast(self, tenant_id: UUID, message: dict):
        """
        Send message to clients
        :return: None
        """
        conns = self.active.get(tenant_id, [])
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception as e:
                print(f"Exception: {e}")
                pass

manager = ConnectionManager()

# GET endpoints
#  Return all or filtered logs
@router.get("/", summary="Search audit logs (filtered, tenant scoped)")
def search_log(
        user_id: Union[UUID, None] = None,
        session_id: Union[str, None] = None,
        action_type: Union[str, None] = None,
        resource_type: Union[str, None] = None,
        severity: Union[str, None] = None,
        q: Union[str, None] = None,
        user = Depends(verify_jwt)
    ):

    tenant_id = UUID(user["tenant_id"])
    conditions = []
    params: list = [tenant_id]

    if user_id:
        conditions.append("user_id = %s")
        params.append(user_id)

    if session_id:
        conditions.append("session_id = %s")
        params.append(session_id)

    if action_type:
        conditions.append("action_type = %s")
        params.append(action_type)

    if severity:
        conditions.append("severity = %s")
        params.append(severity)

    if resource_type:
        conditions.append("resource_type = %s")
        params.append(resource_type)

    if q:
        # Example fuzzy search in resource_id and metadata
        conditions.append("(CAST(resource_id AS TEXT) ILIKE %s OR CAST(metadata AS TEXT) ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    base_sql = "SELECT * FROM audit_logs WHERE tenant_id = %s"
    if conditions:
        base_sql += " AND ".join(conditions)
    base_sql += " ORDER BY created_at ASC;"
    curr.execute(base_sql, params)
    logs = curr.fetchall()
    return {"data": logs}

# Return log statistics (tenant-scoped) **
@router.get("/stats", summary="Get audit logs statistics (tenant-scoped)")
def get_stats(user = Depends(verify_jwt)):
    tenant_id = UUID(user["tenant_id"])
    total_count_sql = "SELECT COUNT(*) as total from audit_logs WHERE tenant_id = %s;"
    total_action_type_sql = """
        SELECT action_type, COUNT(*) AS count
        FROM audit_logs
        WHERE tenant_id = %s
        GROUP BY action_type
        ORDER BY count DESC
    """
    total_severity_count_sql = """
        SELECT severity, COUNT(*) as count
        FROM audit_logs
        WHERE tenant_id = %s
        GROUP BY severity
        ORDER BY count DESC
    """
    total_logs_for_last_week_sql = """
        SELECT DATE_TRUNC('day', created_at) AS day,
        COUNT(*) AS count
        FROM audit_logs
        WHERE created_at >= %s AND tenant_id = %s
        GROUP BY day
        ORDER BY day;
    """

    # 1. Total count
    curr.execute(total_count_sql, (tenant_id,))
    total = curr.fetchone()["total"]
    # 2. Counts by action_type
    curr.execute(total_action_type_sql, (tenant_id,))
    by_action = curr.fetchall()
    # 3. Counts by severity
    curr.execute(total_severity_count_sql, (tenant_id,))
    by_severity = curr.fetchall()
    # 4. Logs per day for the last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    curr.execute(total_logs_for_last_week_sql, (seven_days_ago,tenant_id,))
    per_day = curr.fetchall()

    return {
        "total_logs": total,
        "by_action": by_action,
        "by_severity": by_severity,
        "last_7_days": per_day
    }

# Export logs (tenant-scoped) **
@router.get("/export", summary="Export logs to CSV format file (tenant-scoped)")
def export_log(user = Depends(verify_jwt)):
    tenant_id = UUID(user["tenant_id"])
    sql = "SELECT * FROM audit_logs WHERE tenant_id = %s ORDER BY created_at DESC;"

    curr.execute(sql, (tenant_id,))
    rows = curr.fetchall()

    # Generate CSV stream chunks
    def iter_csv():
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Write header
        if rows:
            writer.writerow(rows[0].keys())
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
        # Write each row
        for row in rows:
            writer.writerow(row.values())
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    # return as StreamingResponse for downloading
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={}
    )

#  Return logs by id
@router.get("/{id}", summary="Search log by id (tenant-scoped)")
def search_log_id(id: UUID, user = Depends(verify_jwt)):
    tenant_id = UUID(user["tenant_id"])

    sql = "SELECT * FROM audit_logs where id = %s AND tenant_id = %s;"
    param = [id, tenant_id]

    curr.execute(sql, param)
    log = curr.fetchone()

    if not log:
        # trigger exception
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log with id {id} does not exist")

    return log

# POST endpoints
# Create log entry (with tenant-ID)
@router.post("/", status_code=status.HTTP_201_CREATED,
             response_model=schemas.Log, summary="Create new log entry (tenant-scoped)")
def create_log(log: schemas.Log, token: dict = Depends(verify_jwt)):
    tenant_id = token.get("tenant_id")
    if tenant_id != str(log.tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant ID mismatch")

    sql = """
    INSERT INTO audit_logs 
    (tenant_id, user_id, session_id, ip_address, user_agent,
     action_type, resource_type, resource_id, severity,
     before_state, after_state, metadata)
    VALUES
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING *;
    """

    params = (
        log.tenant_id, log.user_id, log.session_id, log.ip_address, log.user_agent,
        log.action_type, log.resource_type, log.resource_id, log.severity,
        Json(log.before_state) if log.before_state is not None else None,
        Json(log.after_state) if log.after_state is not None else None,
        Json(log.metadata) if log.metadata is not None else None,
    )

    curr.execute(sql, params)
    new_log = curr.fetchone()

    # Commit the insert statement
    commit()

    # Send to SQS
    send_log_to_sqs(jsonable_encoder({
        **log.model_dump(),
        "tenant_id": str(tenant_id)
    }))

    # Call OpenSearch
    index_log_to_opensearch(log=log.model_dump(), index="audit-logs")

    return jsonable_encoder(new_log)

# Create entries in bulk (with tenant ID)
@router.post("/bulk", status_code=status.HTTP_201_CREATED, summary="Create log entries in bulk (tenant-scoped)")
def create_bulk(logs: List[schemas.Log], token: dict = Depends(verify_jwt)):
    if not logs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request body is empty")

    # verify tenant_id
    tenant_id = token.get("tenant_id")
    if tenant_id != str(logs[0].tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant ID mismatch")

    sql = """
    INSERT INTO audit_logs 
    (tenant_id, user_id, session_id, ip_address, user_agent,
     action_type, resource_type, resource_id, severity,
     before_state, after_state, metadata)
    VALUES
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING *;
    """
    params = []
    for log in logs:
        params.append((
            log.tenant_id, log.user_id, log.session_id, log.ip_address, log.user_agent,
            log.action_type, log.resource_type, log.resource_id, log.severity,
            Json(log.before_state) if log.before_state is not None else None,
            Json(log.after_state)  if log.after_state  is not None else None,
            Json(log.metadata)     if log.metadata     is not None else None,
        ))

    # Execute many
    curr.executemany(sql, params)
    commit()

    for log in logs:
        # send to SQS
        send_log_to_sqs(jsonable_encoder({
            **log.model_dump(),
            "tenant_id": str(log.tenant_id)
        }))
        # call OpenSearch
        index_log_to_opensearch(log=log.model_dump(), index="audit-logs")

    return {"Data inserted": len(params)}

# DELETE
# delete old logs (tenant-scoped) - WIP
@router.delete("/cleanup", status_code=status.HTTP_204_NO_CONTENT, summary="Delete log entry (tenant-scoped)")
def delete_logs(token: dict = Depends(verify_jwt)):
    tenant_id = token.get("tenant_id")

    sql = "DELETE FROM audit_logs WHERE tenant_id = %s RETURNING *;"
    param = (tenant_id,)

    curr.execute(sql, param)
    # Commit sql statement
    commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Delete logs by id
@router.delete("/cleanup/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete log entry by id (tenant-scoped)")
def delete_log(id: UUID, token: dict = Depends(verify_jwt)):
    tenant_id = token.get("tenant_id")
    sql = "DELETE FROM audit_logs WHERE tenant_id = %s AND id = %s RETURNING *;"
    param = [tenant_id, id]

    curr.execute(sql, param)
    deleted_log = curr.fetchone()

    # Commit sql statement
    commit()

    if deleted_log:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log with id {id} does not exist")

# WEBSOCKET
# real-time log streaming **
@router.websocket("/stream", name="Real time log streaming")
async def log_stream(websocket: WebSocket, tenant_id: UUID):
    # Establish connection
    await manager.connect(tenant_id, websocket)

    try:
        # Keep connection alive until client disconnects
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(tenant_id, websocket)

@router.post("/mock-broadcast")
async def mock_broadcast(tenant_id: UUID, msg: str):
    """
    To test websocket broadcast test by creating a mock endpoint
    :return: None
    """
    await manager.broadcast(tenant_id, message={"message": str})
    return {"status": "sent"}
