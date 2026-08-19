"""Tests for healthcheck endpoint."""

from fastapi.testclient import TestClient
from starlette import status


def test_health(client: TestClient):
    """Health endpoint returns ok status."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_root(client: TestClient):
    """Root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["service"] == "Meraki Network Twin"
    assert data["version"] == "0.1.0"
