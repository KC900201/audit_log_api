from datetime import datetime, timedelta
from typing import Union, List
from uuid import UUID
import io, csv

from fastapi import APIRouter, status, HTTPException, Response
from psycopg.types.json import  Json
from starlette.responses import StreamingResponse

from db import curr, conn
import schemas

router = APIRouter(prefix="/logs")
# GET endpoints
#  Return all or filtered logs
@router.get("/")
def search_log(q: Union[str, None] = None):
    sql = "SELECT * FROM audit_logs ORDER BY id ASC;"
    curr.execute(sql)
    logs = curr.fetchall()
    return {"data": logs}

# Return log statistics (tenant-scoped) **
@router.get("/stats")
def get_stats():
    # 1. Total count
    curr.execute("SELECT COUNT(*) as total from audit_logs;")
    total = curr.fetchone()["total"]
    # 2. Counts by action_type
    curr.execute("""
        SELECT action_type, COUNT(*) AS count
        FROM audit_logs
        GROUP BY action_type
        ORDER BY count DESC
    """)
    by_action = curr.fetchall()
    # 3. Counts by severity
    curr.execute("""
        SELECT severity, COUNT(*) as count
        FROM audit_logs
        GROUP BY severity
        ORDER BY count DESC
    """)
    by_severity = curr.fetchall()
    # 4. Logs per day for the last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    curr.execute("""
        SELECT DATE_TRUNC('day', created_at) AS day,
        COUNT(*) AS count
        FROM audit_logs
        WHERE created_at >= %s
        GROUP BY day
        ORDER BY day;
    """, (seven_days_ago,))
    per_day = curr.fetchall()

    return {
        "total_logs": total,
        "by_action": by_action,
        "by_severity": by_severity,
        "last_7_days": per_day
    }

# Export logs (tenant-scoped) **
@router.get("/export")
def export_log():
    sql = "SELECT * FROM audit_logs ORDER BY created_at DESC;"
    curr.execute(sql)
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
def search_log_id(id: UUID, response: Response):
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
def create_log(log: schemas.Log):
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

    return new_log

# Create entries in bulk (with tenant ID)
@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def create_bulk(logs: List[schemas.Log]):
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
def log_stream():
    # What should it return?
    return {"Hello: World"}
