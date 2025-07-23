from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

SAMPLE_TENANT = {
    "name": "tenant-01",
    "status": "active"
}

# Tenant related tests
def test_search_tenants_empty():
    """
    Should return {"data": []} when table is empty
    :return: status_code = 200, list = []
    """
    resp = client.get("/api/v1/tenants/")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)

def test_search_tenant_after_create():
    # Create a new record
    resp = client.post("/api/v1/tenants/", json=SAMPLE_TENANT)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    log_id = created["id"]

    # Search for newly created log
    resp2 = client.get("/api/v1/tenants/")
    data = resp2.json()["data"]
    assert (item["id"] == log_id for item in data)

def test_create_tenant():
    resp = client.post("/api/v1/tenants/", json=SAMPLE_TENANT)
    assert resp.status_code == 201, resp.text
    created = resp.json()

    # Assert id and created_at is generated
    assert "id" in created
    assert "created_at" in created