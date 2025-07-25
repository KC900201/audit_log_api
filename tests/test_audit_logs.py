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

test_tenant_id = "f248d1ee-f3c7-458a-9c17-27cef4b89e38"

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

@patch("routers.audit_logs.index_log_to_opensearch")
@patch("routers.audit_logs.send_log_to_sqs")
def test_search_log_after_create(mock_send_log_to_sqs, mock_index_log_to_opensearch):
    # Create a new record
    resp = client.post("/api/v1/logs/", json=JWT_LOG, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    log_id = created["id"]
    # Assert send_log_to_sqs were called
    mock_send_log_to_sqs.assert_called_once()
    mock_index_log_to_opensearch.assert_called_once()

    # Search for newly created log
    resp2 = client.get("/api/v1/logs/", headers=headers)
    data = resp2.json()["data"]
    assert (item["id"] == log_id for item in data)

@patch("routers.audit_logs.index_log_to_opensearch")
@patch("routers.audit_logs.send_log_to_sqs")
def test_get_log_stats(mock_send_log_to_sqs, mock_index_log_to_opensearch):
    # Create a new log
    resp1 = client.post("/api/v1/logs/", json=JWT_LOG, headers=headers)
    assert resp1.status_code == 201, resp1.text
    created = resp1.json()
    # Assert utility functions were called
    mock_send_log_to_sqs.assert_called_once()
    mock_index_log_to_opensearch.assert_called_once()

    # Retrieve the log stats after the created log
    resp2 = client.get("/api/v1/logs/stats", headers=headers)
    assert resp2.status_code == 200

def test_tenant_id_mismatch_when_creating_log():
    # Create a new log
    resp = client.post("/api/v1/logs/", json=SAMPLE_LOG, headers=headers)
    assert resp.status_code == 403, resp.text # http status 403 for unauthorized access

@patch("routers.audit_logs.index_log_to_opensearch")
@patch("routers.audit_logs.send_log_to_sqs")
def test_create_new_log(mock_send_log_to_sqs, mock_index_log_to_opensearch):
    test_log = SAMPLE_LOG.copy()
    test_log["tenant_id"] = test_tenant_id

    # Create a new log
    resp = client.post("/api/v1/logs/", json=JWT_LOG, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()

    # Assert AWS SQS and OpenSearch function are called
    mock_send_log_to_sqs.assert_called_once()
    mock_index_log_to_opensearch.assert_called_once()

    # Assert that the new log has a auto-generated id and created_at date
    assert "id" in created
    assert "created_at" in created

@patch("routers.audit_logs.index_log_to_opensearch")
@patch("routers.audit_logs.send_log_to_sqs")
def test_search_log_by_id_success(mock_send_log_to_sqs, mock_index_log_to_opensearch):
    test_log = SAMPLE_LOG.copy()
    test_log["tenant_id"] = test_tenant_id

    # Create a new log
    resp = client.post("/api/v1/logs/", json=JWT_LOG, headers=headers)
    assert resp.status_code == 201, resp.text
    log_id = resp.json()["id"]

    # Search log by id
    resp2 = client.get(f"/api/v1/logs/{log_id}", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["id"] == log_id

def test_get_log_by_id_not_found():
    random_id = str(uuid4())
    resp = client.get(f"/api/v1/logs/{random_id}", headers=headers)
    assert resp.status_code == 404

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

@patch("routers.audit_logs.index_log_to_opensearch")
@patch("routers.audit_logs.send_log_to_sqs")
def test_export_logs_to_csv(mock_send_log_to_sqs, mock_index_log_to_opensearch):
    # Create new log
    test_log = SAMPLE_LOG.copy()
    test_log["tenant_id"] = test_tenant_id

    # Create a new log
    resp = client.post("/api/v1/logs/", json=JWT_LOG, headers=headers)
    assert resp.status_code == 201, resp.text

    # Assert AWS SQS and OpenSearch function are called
    mock_send_log_to_sqs.assert_called_once()
    mock_index_log_to_opensearch.assert_called_once()

    # Test export new log
    resp2 = client.get("/api/v1/logs/export", headers=headers)
    assert resp2.status_code == 200
    assert resp2.headers["content-type"] == "text/csv; charset=utf-8" # charset is auto append by FastAPI
    assert "resource_id" in resp.text

@patch("routers.audit_logs.index_log_to_opensearch")
@patch("routers.audit_logs.send_log_to_sqs")
def test_delete_log_after_create(mock_send_log_to_sqs, mock_index_log_to_opensearch):
    # Create a new record
    resp = client.post("/api/v1/logs/", json=JWT_LOG, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    log_id = created["id"]
    # Assert send_log_to_sqs were called
    mock_send_log_to_sqs.assert_called_once()
    mock_index_log_to_opensearch.assert_called_once()

    # Delete logs
    resp2 = client.delete("/api/v1/logs/cleanup", headers=headers)
    assert resp2.status_code == 204

@patch("routers.audit_logs.send_log_to_sqs")
@patch("routers.audit_logs.index_log_to_opensearch")
def test_delete_log_by_id(mock_send_log_to_sqs, mock_index_log_to_opensearch):
    # Create log
    resp = client.post("/api/v1/logs/", json=JWT_LOG, headers=headers)
    log_id = resp.json()["id"]

    # Assert send_log_to_sqs were called
    mock_send_log_to_sqs.assert_called_once()
    mock_index_log_to_opensearch.assert_called_once()

    # Delete by id
    resp2 = client.delete(f"/api/v1/logs/cleanup/{log_id}", headers=headers)
    assert resp2.status_code == 204

def test_delete_log_by_id_not_found():
    random_id = str(uuid4())
    resp = client.delete(f"/api/v1/logs/cleanup/{random_id}", headers=headers)
    assert resp.status_code == 404

def test_websocket_log_stream():
    try:
        with client.websocket_connect(f"/api/v1/logs/stream?tenant_id={test_tenant_id}", timeout=5) as ws:
            # Simulate ping to keep connection alive
            ws.send_text("ping")
    except Exception as e:
        print(f"WebSocket error: {e}")
        assert False, f"Websocket timeout or connection error: {e}"
