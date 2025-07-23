from datetime import datetime, timedelta
from typing import Union, List
from uuid import UUID
import io, csv

from fastapi import APIRouter, status, HTTPException, Response, Depends
from psycopg.types.json import  Json
from starlette.responses import StreamingResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from db import curr, conn
from auth import verity_jwt
from utils import send_log_to_sqs
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
        for ws in self.active.get(tenant_id, []):
            await ws.send_json(message)

manager = ConnectionManager()

# GET endpoints
#  Return all or filtered logs
@router.get("/")
def search_log(
        user_id: Union[UUID, None] = None,
        session_id: Union[str, None] = None,
        action_type: Union[str, None] = None,
        resource_type: Union[str, None] = None,
        severity: Union[str, None] = None,
        q: Union[str, None] = None,
        user = Depends(verity_jwt())
    ):

    tenant_id = UUID(user["tenant_id"])
    conditions = []
    params: list = [tenant_id]

    # if tenant_id:
    #     conditions.append("tenant_id = %s")
    #     params.append(tenant_id)

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
@router.get("/stats")
def get_stats(user = Depends(verity_jwt())):
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
        WHERE tenant_id = %s
        FROM audit_logs
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
@router.get("/export")
def export_log(user = Depends(verity_jwt())):
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
@router.get("/{id}")
def search_log_id(id: UUID):
    sql = "SELECT * FROM audit_logs where id = %s;"
    param = [id]

    curr.execute(sql, param)
    log = curr.fetchone()

    if not log:
        # trigger exception
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log with id {id} does not exist")

    return log

# POST endpoints
# Create log entry (with tenant-ID)
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_log(log: schemas.Log, token: dict = Depends(verity_jwt())):
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
    conn.commit()

    # Send to SQS
    send_log_to_sqs({
        **log.model_dump(),
        "tenant_id": str(tenant_id)
    })

    return new_log

# Create entries in bulk (with tenant ID)
@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def create_bulk(logs: List[schemas.Log], token: dict = Depends(verity_jwt())):
    # verify tenant_id
    # tenant_id = token.get("tenant_id")
    # if tenant_id != str(logs[0].tenant_id):
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant ID mismatch")

    if not logs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request body is empty")

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
    conn.commit()

    # Send to SQS
    for log in logs:
        send_log_to_sqs({
            **log.model_dump(),
            "tenant_id": str(log.tenant_id)
        })

    return {"Data inserted": len(params)}

# DELETE
# delete old logs (tenant-scoped) - WIP
@router.delete("/cleanup", status_code=status.HTTP_204_NO_CONTENT)
def delete_logs():
    sql = "DELETE FROM audit_logs RETURNING *;"
    curr.execute(sql)

    # Commit sql statement
    conn.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Delete logs by id
@router.delete("/cleanup/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_log(id: UUID):
    sql = "DELETE FROM audit_logs WHERE id = %s RETURNING *;"
    param = [id]

    curr.execute(sql, param)
    deleted_log = curr.fetchone()

    # Commit sql statement
    conn.commit()

    if deleted_log:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log with id {id} does not exist")

# PUT (not in scoped, WIP)
@router.put("/{id}", )
def update_log(id: UUID, log: schemas.Log):
    sql = """UPDATE audit_logs 
    SET tenant_id = %s, user_id = %s, session_id = %s,
    ip_address = %s, user_agent = %s, action_type = %s, 
    resource_type = %s, resource_id = %s, severity = %s,
    before_state = %s, after_state = %s, metadata = %s
    WHERE id = %s RETURNING *;"""

    params = (
        log.tenant_id, log.user_id, log.session_id,
        log.ip_address, log.user_agent, log.action_type,
        log.resource_type, log.resource_id, log.severity,
        Json(log.before_state), Json(log.after_state), Json(log.metadata),
        id
    )

    curr.execute(sql, params)
    updated_log = curr.fetchone()
    # Commit statement
    conn.commit()

    if not updated_log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log with id {id} does not exist")

    return updated_log

# WEBSOCKET
# real-time log streaming **
@router.websocket("/stream")
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
