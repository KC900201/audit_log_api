from typing import Union, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
import time

from fastapi import FastAPI, Response, status, HTTPException
from pydantic import BaseModel

import psycopg
from psycopg.rows import dict_row

app = FastAPI()

# Connect to PostgreSQL database
while True: # while condition
    try:
      #   Change later to remove hardcode connection (env variables)
      conn = psycopg.connect(conninfo="host=localhost dbname=fastapi user=postgres password=password", row_factory=dict_row)
      curr = conn.cursor()
      print("Database connection was successful")
      break
    except Exception as error:
        print("Connection to database failed")
        print("Error: ", error)
        time.sleep(3)

# Declare class using Python types
class Log(BaseModel):
    id: Union[int, None] = None
    tenant_id: UUID
    user_id: UUID
    session_id: str
    ip_address: str
    user_agent: str
    action_type: str
    resource_type: str
    resource_id: str
    severity: str
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class Tenant(BaseModel):
    id: Union[int, None] = None
    name: str
    status: str

@app.get("/")
def root():
    return {"Hello": "World"}

# Logs related API (CRUD)
# GET
#  Return all or filtered logs
@app.get("/logs/")
def search_log(q: Union[str, None] = None):
    sql = "SELECT * FROM audit_logs ORDER BY id ASC;"
    curr.execute(sql)
    logs = curr.fetchall()
    return {"data": logs}

#  Return logs by id
@app.get("/logs/{id}")
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
@app.get("/logs/export")
def export_log():
    return {"Hello: World"}

# Return log statistics (tenant-scoped) **
@app.get("/logs/stats")
def get_stats():
    return {"Hello: World"}

# List accessible tenant (admin only)
@app.get("/tenants/")
def search_tenant():
    sql = "SELECT * FROM tenants ORDER BY id ASC;"
    curr.execute(sql)
    tenants = curr.fetchall()

    return {"data": tenants}

# POST
# Create log entry (with tenant-ID)
@app.post("/logs/", status_code=status.HTTP_201_CREATED)
def create_log(log: Log):
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
@app.post("/logs/bulk", status_code=status.HTTP_201_CREATED)
def create_bulk():
    return {"Hello: World"}

# Create new tenant (admin only)
@app.post("/tenants/", status_code=status.HTTP_201_CREATED)
def create_tenant(tenant: Tenant):
    sql = """
    INSERT INTO tenants
    (name, status)
    VALUES (%s, %s)
    RETURNING *;
    """
    params = (tenant.name, tenant.status)

    curr.execute(sql, params)
    new_tenant = curr.fetchone()

    # Commit statement
    conn.commit()

    return new_tenant

# PUT (not in scoped, WIP)
@app.put("/logs/{id}", )
def update_log(id: UUID, log: Log):
    return {"Hello": "World"}


# DELETE
# delete old logs (tenant-scoped) - WIP
@app.delete("logs/cleanup", status_code=status.HTTP_204_NO_CONTENT)
def delete_logs():
    return {"message": "All logs are deleted"}

# Delete logs by id
@app.delete("/logs/cleanup/{id}", status_code=status.HTTP_204_NO_CONTENT)
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

# WIP
# real-time log streaming **
@app.websocket("/logs/stream")
def log_stream():
    # What should it return?
    return {"Hello: World"}
