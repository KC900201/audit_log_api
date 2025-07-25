from fastapi import FastAPI

from routers import audit_logs_router, tenants_router
app = FastAPI()

# Register router for endpoints
app.include_router(audit_logs_router, prefix="/api/v1", tags=["Audit Logs"])
app.include_router(tenants_router, prefix="/api/v1", tags=["Tenants"])

# root function
@app.get("/")
def root():
    return {"Hello": "World"}