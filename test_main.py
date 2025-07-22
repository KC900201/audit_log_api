import uuid

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Hello": "World"}

SAMPLE_LOG = {
    "tenant_id": str(uuid.uuid4()),
    "user_id":   str(uuid.uuid4()),
    "session_id": "sess-test-001",
    "ip_address": "127.0.0.1",
    "user_agent": "test-client/1.0",
    "action_type": "CREATE",
    "resource_type": "test_resource",
    "resource_id": "res-123",
    "severity": "INFO",
    "before_state": {"foo": "bar"},
    "after_state": {"foo": "baz"},
    "metadata": {"test_meta": True}
}

SAMPLE_TENANT = {
    "name": "tenant-01",
    "status": "active"
}

def test_search_log_empty():
    """
    Should return {"data": []} when table is empty
    :return: status_code = 200, list = []
    """
    resp = client.get("/api/v1/logs/")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)

def test_search_log_after_create():
    # Create a new record
    resp = client.post("/api/v1/logs/", json=SAMPLE_LOG)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    log_id = created["id"]

    # Search for newly created log
    resp2 = client.get("/api/v1/logs/")
    data = resp2.json()["data"]
    assert (item["id"] == log_id for item in data)

def test_get_log_stats():
    # Create a new log
    resp1 = client.post("/api/v1/logs/", json=SAMPLE_LOG)
    assert resp1.status_code == 201, resp1.text
    created = resp1.json()

    # Retrieve the log stats after the created log
    resp2 = client.get("/api/v1/logs/stats")
    assert resp2.status_code == 200


def test_create_new_log():
    # Create a new log
    resp = client.post("/api/v1/logs/", json=SAMPLE_LOG)
    assert resp.status_code == 201, resp.text
    created = resp.json()

    # Assert that the new log has a auto-generated id and created_at date
    assert "id" in created
    assert "created_at" in created

@pytest.mark.parametrize("size", [0, 2])
def test_create_bulk(size):
    """
    :param size: 0, 2
    :return: none
    """
    payload = []
    for i in range(size):
        entry = SAMPLE_LOG.copy()
        entry["resource_id"] = f"bulk-{i}"
        payload.append(entry)

    resp = client.post("/api/v1/logs/bulk", json=payload)
    if size == 0:
        assert resp.status_code == 400
    else:
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert "Data inserted" in body
        assert body["Data inserted"] == size

# Tenant related tests
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
