from typing import Union
from fastapi import APIRouter, status, HTTPException, Response

from db import curr, conn
import schemas

router = APIRouter(prefix="/tenants")

# GET
# List accessible tenant (admin only)
@router.get("/")
def search_tenant(name: Union[str, None] = None, status: Union[str, None] = None):
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
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_tenant(tenant: schemas.Tenant):
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
