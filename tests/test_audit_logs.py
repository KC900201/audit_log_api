import uuid
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from auth import generate_mock_jwt
from main import app

client = TestClient(app)

SAMPLE_LOG = {
    "tenant_id": str(uuid.uuid4()),
    "user_id": str(uuid.uuid4()),
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

JWT_LOG = {
    "tenant_id": "f248d1ee-f3c7-458a-9c17-27cef4b89e38", # same tenant_id with jwt token
    "user_id": str(uuid.uuid4()),
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

token = generate_mock_jwt()
headers = {"Authorization": f"Bearer {token}"}

def test_search_log_empty():
    """
    Should return {"data": []} when table is empty
    :return: status_code = 200, list = []
    """
    resp = client.get("/api/v1/logs/", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)

def test_search_log_after_create():
    # Create a new record
    resp = client.post("/api/v1/logs/", json=JWT_LOG, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    log_id = created["id"]

    # Search for newly created log
    resp2 = client.get("/api/v1/logs/", headers=headers)
    data = resp2.json()["data"]
    assert (item["id"] == log_id for item in data)

def test_get_log_stats():
    # Create a new log
    resp1 = client.post("/api/v1/logs/", json=JWT_LOG, headers=headers)
    assert resp1.status_code == 201, resp1.text
    created = resp1.json()

    # Retrieve the log stats after the created log
    resp2 = client.get("/api/v1/logs/stats", headers=headers)
    assert resp2.status_code == 200

def test_tenant_id_mismatch_when_creating_log():
    # Create a new log
    resp = client.post("/api/v1/logs/", json=SAMPLE_LOG, headers=headers)
    assert resp.status_code == 403, resp.text # http status 403 for unauthorized access

@patch("routers.audit_logs.send_log_to_sqs")
def test_create_new_log(mock_send_log_to_sqs):
    # Create a new log
    resp = client.post("/api/v1/logs/", json=JWT_LOG, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()

    # Assert send_log_to_sqs was called
    mock_send_log_to_sqs.assert_called_once()

    # Assert that the new log has a auto-generated id and created_at date
    assert "id" in created
    assert "created_at" in created

@patch("routers.audit_logs.send_log_to_sqs")
@pytest.mark.parametrize("size", [0, 2])
def test_create_bulk(mock_send_log_to_sqs, size):
    """
    :param size: 0, 2
    :return: none
    """
    payload = []
    for i in range(size):
        entry = JWT_LOG.copy()
        entry["resource_id"] = f"bulk-{i}"
        payload.append(entry)

    resp = client.post("/api/v1/logs/bulk", json=payload, headers=headers)
    if size == 0:
        assert resp.status_code == 400
    else:
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert "Data inserted" in body
        assert body["Data inserted"] == size
        assert mock_send_log_to_sqs.call_count == len(payload)

def test_websocket_log_stream():
    tenant_id = uuid4()
    with client.websocket_connect(f"/api/v1/logs/stream?tenant_id={tenant_id}") as ws:
        # Simulate ping to keep connection alive
        ws.send_text("ping")
