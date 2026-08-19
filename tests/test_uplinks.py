"""REST read-mirror tests for uplinks (ticket 04)."""

from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import FakeElasticsearch, auth_header

ORG_ID = ""

UPLINK_DOC = {
    "serial": "Q2HP-ABCD-1234",
    "interface": "wan1",
    "network_id": "N_642828",
    "network_name": "HQ Office",
    "publicIp": "203.0.113.10",
    "ip": "10.0.0.1",
    "gateway": "10.0.0.254",
    "addressing": "static",
    "status": "Active",
    "enabled": True,
    "primary": True,
    "dns": "1.1.1.1",
    "meraki_org_id": ORG_ID,
    "@timestamp": "2026-01-02T03:04:05.000Z",
}


def seed_uplink(fake_es: FakeElasticsearch, doc: dict, serial: str, interface: str) -> None:
    fake_es.seed("meraki-uplink-metrics", {f"{serial}-{interface}": doc})


def test_list_uplinks_requires_auth(client: TestClient):
    resp = client.get("/uplinks")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_list_uplinks_empty(client: TestClient, bearer: str):
    resp = client.get("/uplinks", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_uplinks_returns_projections(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_uplink(fake_es, UPLINK_DOC, "Q2HP-ABCD-1234", "wan1")
    resp = client.get("/uplinks", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    up = data[0]
    assert up["serial"] == "Q2HP-ABCD-1234"
    assert up["interface"] == "wan1"
    assert up["network_id"] == "N_642828"
    assert up["network_name"] == "HQ Office"
    assert up["public_ip"] == "203.0.113.10"
    assert up["ip"] == "10.0.0.1"
    assert up["gateway"] == "10.0.0.254"
    assert up["addressing"] == "static"
    assert up["status"] == "Active"
    assert up["enabled"] is True
    assert up["primary"] is True
    assert up["dns"] == "1.1.1.1"
    assert up["as_of"] == "2026-01-02T03:04:05.000Z"


def test_list_uplinks_filters_network_id(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_uplink(fake_es, UPLINK_DOC, "Q2HP-ABCD-1234", "wan1")
    other = dict(UPLINK_DOC, network_id="N_BRANCH", serial="Q2HP-ABCD-9999")
    seed_uplink(fake_es, other, "Q2HP-ABCD-9999", "wan1")
    resp = client.get("/uplinks", params={"network_id": "N_BRANCH"}, headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    ups = resp.json()
    assert len(ups) == 1
    assert ups[0]["serial"] == "Q2HP-ABCD-9999"


def test_list_uplinks_filters_serial(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_uplink(fake_es, UPLINK_DOC, "Q2HP-ABCD-1234", "wan1")
    other = dict(UPLINK_DOC, serial="Q2HP-ABCD-9999")
    seed_uplink(fake_es, other, "Q2HP-ABCD-9999", "wan1")
    resp = client.get("/uplinks", params={"serial": "Q2HP-ABCD-9999"}, headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    ups = resp.json()
    assert len(ups) == 1
    assert ups[0]["interface"] == "wan1"


def test_get_uplink_by_serial_interface(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_uplink(fake_es, UPLINK_DOC, "Q2HP-ABCD-1234", "wan1")
    resp = client.get("/uplinks/Q2HP-ABCD-1234/wan1", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["public_ip"] == "203.0.113.10"


def test_get_uplink_not_found(client: TestClient, bearer: str):
    resp = client.get("/uplinks/Q2HP-ABCD-1234/wan2", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_404_NOT_FOUND
