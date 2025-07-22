from fastapi import APIRouter, status, HTTPException, Response

from db import curr, conn
import schemas

router = APIRouter()

# GET
# List accessible tenant (admin only)
@router.get("/tenants/")
def search_tenant():
    sql = "SELECT * FROM tenants ORDER BY id ASC;"
    curr.execute(sql)
    tenants = curr.fetchall()

    return {"data": tenants}


# POST
# Create new tenant (admin only)
@router.post("/tenants/", status_code=status.HTTP_201_CREATED)
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
