from fastapi.testclient import TestClient
from unittest.mock import patch

from auth import generate_mock_jwt, generate_mock_user_jwt
from main import app

client = TestClient(app)

SAMPLE_TENANT = {
    "name": "tenant-01",
    "status": "active"
}

token = generate_mock_jwt()
user_token = generate_mock_user_jwt()
headers = {"Authorization": f"Bearer {token}"}
headers_user = {"Authorization": f"Bearer {user_token}"}

# Tenant related tests
def test_search_tenants_empty():
    """
    Should return {"data": []} when table is empty
    :return: status_code = 200, list = []
    """
    resp = client.get("/api/v1/tenants/", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)

def test_search_tenant_fail_unauthorized():
    resp = client.get("/api/v1/tenants/", headers=headers_user)
    assert resp.status_code == 403, resp.text

@patch("routers.audit_logs.index_log_to_opensearch")
@patch("routers.tenants.send_log_to_sqs")
def test_search_tenant_after_create(mock_send_log_to_sqs, mock_index_log_to_opensearch):
    # Create a new record
    resp = client.post("/api/v1/tenants/", json=SAMPLE_TENANT, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    tenant_id = created["id"]

    # Assert send_log_to_sqs was called
    mock_send_log_to_sqs.assert_called_once()
    mock_index_log_to_opensearch.assert_called_once()

    # Search for newly created log
    resp2 = client.get("/api/v1/tenants/", headers=headers)
    data = resp2.json()["data"]
    assert (item["id"] == tenant_id for item in data)

@patch("routers.tenants.index_log_to_opensearch")
@patch("routers.tenants.send_log_to_sqs")
def test_create_tenant(mock_send_log_to_sqs, mock_index_log_to_opensearch):
    resp = client.post("/api/v1/tenants/", json=SAMPLE_TENANT, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()

    # Assert send_log_to_sqs was called
    mock_send_log_to_sqs.assert_called_once()
    mock_index_log_to_opensearch.assert_called_once()

    # Assert id and created_at is generated
    assert "id" in created
    assert "created_at" in created

def test_create_tenant_fail():
    resp = client.post("/api/v1/tenants/", json=SAMPLE_TENANT, headers=headers_user)
    assert resp.status_code == 403, resp.text
