from http.client import HTTPException
from typing import Union
from fastapi import APIRouter, status as http_status, Depends, HTTPException

from auth import verity_jwt
from db import curr, conn
import schemas
from utils import send_log_to_sqs

router = APIRouter(prefix="/tenants")

# GET
# List accessible tenant (admin only)
@router.get("/")
def search_tenant(name: Union[str, None] = None,
                  status: Union[str, None] = None,
                  user=Depends(verity_jwt)
                  ):
    if user["role"] != "admin":
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Admin access required")

    conditions = []
    params = []

    if name:
        conditions.append("name = %s")
        params.append(name)

    if status:
        conditions.append("status = %s")
        params.append(status)

    base_sql = "SELECT * FROM tenants"

    if conditions:
        base_sql += " WHERE " + " AND ".join(conditions)
    base_sql += " ORDER BY created_at DESC;"

    curr.execute(base_sql, params)
    tenants = curr.fetchall()

    return {"data": tenants}

# POST
# Create new tenant (admin only)
@router.post("/", status_code=http_status.HTTP_201_CREATED)
def create_tenant(tenant: schemas.Tenant, user=Depends(verity_jwt)):
    if user["role"] != "admin":
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Admin access required")

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

    # Send to SQS
    send_log_to_sqs({
        **tenant.model_dump(),
        "tenant_id": str(user["tenant_id"])
    })

    return new_tenant
