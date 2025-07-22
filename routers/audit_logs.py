from typing import Union
from uuid import UUID

from fastapi import APIRouter, status, HTTPException, Response
from psycopg.types.json import  Json

from db import curr, conn
import schemas

router = APIRouter()
# GET endpoints
#  Return all or filtered logs
@router.get("/logs/")
def search_log(q: Union[str, None] = None):
    sql = "SELECT * FROM audit_logs ORDER BY id ASC;"
    curr.execute(sql)
    logs = curr.fetchall()
    return {"data": logs}

#  Return logs by id
@router.get("/logs/{id}")
def search_log_id(id: UUID, response: Response):
    sql = "SELECT * FROM audit_logs where id = %s;"
    param = [id]

    curr.execute(sql, param)
    log = curr.fetchone()

    if not log:
        # trigger exception
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log with id {id} does not exist")

    return log

# Export logs (tenant-scoped) **
@router.get("/logs/export")
def export_log():
    return {"Hello: World"}

# Return log statistics (tenant-scoped) **
@router.get("/logs/stats")
def get_stats():
    return {"Hello: World"}

# POST endpoints
# Create log entry (with tenant-ID)
@router.post("/logs/", status_code=status.HTTP_201_CREATED)
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
        log.before_state, log.after_state, log.metadata
    )

    curr.execute(sql, params)
    new_log = curr.fetchone()

    # Commit the insert statement
    conn.commit()

    return new_log

# Create entries in bulk (with tenant ID)
@router.post("/logs/bulk", status_code=status.HTTP_201_CREATED)
def create_bulk():
    return {"Hello: World"}

# DELETE
# delete old logs (tenant-scoped) - WIP
@router.delete("logs/cleanup", status_code=status.HTTP_204_NO_CONTENT)
def delete_logs():
    return {"message": "All logs are deleted"}

# Delete logs by id
@router.delete("/logs/cleanup/{id}", status_code=status.HTTP_204_NO_CONTENT)
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
@router.put("/logs/{id}", )
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
@router.websocket("/logs/stream")
def log_stream():
    # What should it return?
    return {"Hello: World"}
