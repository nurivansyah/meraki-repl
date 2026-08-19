"""REST read-mirror tests for networks and devices (ticket 03).

These exercise the real ``ElasticsearchStateStore`` adapter + projector against
the in-memory ``FakeElasticsearch`` seeded with Meraki-shaped documents, with
bearer-token auth through ``require_bearer``.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import FakeElasticsearch
from tests.fakes.fake_token_repository import FakeTokenRepository
from twin.application.token_service import TokenService

ORG_ID = ""

NETWORK_DOC = {
    "name": "HQ Office",
    "timeZone": "America/Los_Angeles",
    "tags": ["prod", "office"],
    "productTypes": ["switch", "wireless"],
    "meraki_org_id": ORG_ID,
    "network_id": "N_642828",
    "@timestamp": "2026-01-02T03:04:05.000Z",
}

INVENTORY_DOC = {
    "name": "core-switch-01",
    "model": "MS425-32",
    "mac": "aa:bb:cc:dd:ee:01",
    "network_id": "N_642828",
    "product_type": "switch",
    "firmware": "16.16.5",
    "lanIp": "10.0.0.2",
    "wan1Ip": "10.1.0.2",
    "meraki_org_id": ORG_ID,
    "@timestamp": "2026-01-02T03:04:05.000Z",
}

METRICS_DOC = {
    "name": "core-switch-01",
    "status": "online",
    "network_id": "N_642828",
    "meraki_org_id": ORG_ID,
    "@timestamp": "2026-01-02T03:04:05.000Z",
}


@pytest.fixture
async def bearer(token_repo: FakeTokenRepository) -> str:
    """Issue a valid token on the fake repo and return its raw value."""
    service = TokenService(token_repo)
    _, raw = await service.issue_token("reader")
    return raw


def seed_network(fake_es: FakeElasticsearch, doc: dict, network_id: str) -> None:
    fake_es.seed("meraki-network-metrics", {network_id: doc})


def seed_inventory(fake_es: FakeElasticsearch, doc: dict, serial: str) -> None:
    fake_es.seed("meraki-device-inventory", {serial: doc})


def seed_metrics(fake_es: FakeElasticsearch, doc: dict, serial: str) -> None:
    fake_es.seed("meraki-device-metrics", {serial: doc})


def auth(bearer: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {bearer}"}


# ---------------------------------------------------------------------------
# Networks
# ---------------------------------------------------------------------------


def test_list_networks_requires_auth(client: TestClient):
    resp = client.get("/networks")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_list_networks_empty(client: TestClient, bearer: str):
    resp = client.get("/networks", headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_networks_returns_projections(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_network(fake_es, NETWORK_DOC, "N_642828")
    resp = client.get("/networks", headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["id"] == "N_642828"
    assert item["name"] == "HQ Office"
    assert item["time_zone"] == "America/Los_Angeles"
    assert item["tags"] == ["prod", "office"]
    assert item["product_types"] == ["switch", "wireless"]
    assert item["as_of"] == "2026-01-02T03:04:05.000Z"


def test_get_network_by_id(client: TestClient, fake_es: FakeElasticsearch, bearer: str):
    seed_network(fake_es, NETWORK_DOC, "N_642828")
    resp = client.get("/networks/N_642828", headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["name"] == "HQ Office"


def test_get_network_not_found(client: TestClient, bearer: str):
    resp = client.get("/networks/N_MISSING", headers=auth(bearer))
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_network_requires_auth(client: TestClient, fake_es: FakeElasticsearch):
    seed_network(fake_es, NETWORK_DOC, "N_642828")
    resp = client.get("/networks/N_642828")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.headers["WWW-Authenticate"] == "Bearer"


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------


def test_list_devices_requires_auth(client: TestClient):
    resp = client.get("/devices")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_devices_empty(client: TestClient, bearer: str):
    resp = client.get("/devices", headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_devices_merges_inventory_metrics_and_network(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_network(fake_es, NETWORK_DOC, "N_642828")
    seed_inventory(fake_es, INVENTORY_DOC, "Q2HP-ABCD-1234")
    seed_metrics(fake_es, METRICS_DOC, "Q2HP-ABCD-1234")
    resp = client.get("/devices", headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    dev = data[0]
    assert dev["serial"] == "Q2HP-ABCD-1234"
    assert dev["name"] == "core-switch-01"
    assert dev["model"] == "MS425-32"
    assert dev["mac"] == "aa:bb:cc:dd:ee:01"
    assert dev["network_id"] == "N_642828"
    assert dev["network_name"] == "HQ Office"
    assert dev["product_type"] == "switch"
    assert dev["status"] == "online"
    assert dev["firmware"] == "16.16.5"
    assert dev["lan_ip"] == "10.0.0.2"
    assert dev["wan_ip"] == "10.1.0.2"
    assert dev["as_of"] == "2026-01-02T03:04:05.000Z"


def test_list_devices_liberal_merge_inventory_only(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_network(fake_es, NETWORK_DOC, "N_642828")
    seed_inventory(fake_es, INVENTORY_DOC, "Q2HP-ABCD-1234")
    resp = client.get("/devices", headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    dev = resp.json()[0]
    assert dev["status"] is None


def test_list_devices_liberal_merge_metrics_only(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_metrics(fake_es, METRICS_DOC, "Q2HP-ABCD-1234")
    resp = client.get("/devices", headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    dev = resp.json()[0]
    assert dev["serial"] == "Q2HP-ABCD-1234"
    assert dev["status"] == "online"
    assert dev["model"] is None


def test_list_devices_filters_network_id(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_inventory(fake_es, INVENTORY_DOC, "Q2HP-ABCD-1234")
    other = dict(INVENTORY_DOC, name="branch-switch-01", network_id="N_BRANCH")
    seed_inventory(fake_es, other, "Q2HP-ABCD-9999")
    resp = client.get("/devices", params={"network_id": "N_BRANCH"}, headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    devs = resp.json()
    assert len(devs) == 1
    assert devs[0]["serial"] == "Q2HP-ABCD-9999"


def test_list_devices_filters_product_type_and_status(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_inventory(fake_es, INVENTORY_DOC, "Q2HP-ABCD-1234")
    seed_metrics(fake_es, METRICS_DOC, "Q2HP-ABCD-1234")
    other = dict(METRICS_DOC, name="ap-01", network_id="N_OTHER")
    other_inv = dict(INVENTORY_DOC, name="ap-01", network_id="N_OTHER", product_type="wireless")
    seed_metrics(fake_es, other, "Q2HP-ABCD-8888")
    seed_inventory(fake_es, other_inv, "Q2HP-ABCD-8888")

    resp = client.get("/devices", params={"product_type": "switch"}, headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert [d["serial"] for d in resp.json()] == ["Q2HP-ABCD-1234"]

    resp = client.get("/devices", params={"status": "online"}, headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert {d["serial"] for d in resp.json()} == {"Q2HP-ABCD-1234", "Q2HP-ABCD-8888"}

    resp = client.get("/devices", params={"status": "offline"}, headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_get_device_by_serial(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_network(fake_es, NETWORK_DOC, "N_642828")
    seed_inventory(fake_es, INVENTORY_DOC, "Q2HP-ABCD-1234")
    seed_metrics(fake_es, METRICS_DOC, "Q2HP-ABCD-1234")
    resp = client.get("/devices/Q2HP-ABCD-1234", headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    dev = resp.json()
    assert dev["name"] == "core-switch-01"
    assert dev["network_name"] == "HQ Office"
    assert dev["status"] == "online"


def test_get_device_metrics_only(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_metrics(fake_es, METRICS_DOC, "Q2HP-ABCD-1234")
    resp = client.get("/devices/Q2HP-ABCD-1234", headers=auth(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["status"] == "online"


def test_get_device_not_found(client: TestClient, bearer: str):
    resp = client.get("/devices/Q2HP-ABCD-0000", headers=auth(bearer))
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_device_requires_auth(client: TestClient, fake_es: FakeElasticsearch):
    seed_metrics(fake_es, METRICS_DOC, "Q2HP-ABCD-1234")
    resp = client.get("/devices/Q2HP-ABCD-1234")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
