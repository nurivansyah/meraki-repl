"""REST read-mirror tests for switchports (ticket 04)."""

from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import FakeElasticsearch, auth_header

ORG_ID = ""

NETWORK_DOC = {
    "name": "HQ Office",
    "timeZone": "America/Los_Angeles",
    "tags": ["prod"],
    "productTypes": ["switch"],
    "meraki_org_id": ORG_ID,
    "network_id": "N_642828",
    "@timestamp": "2026-01-02T03:04:05.000Z",
}

SWITCHPORT_DOC = {
    "serial": "Q2HP-ABCD-1234",
    "portId": "1",
    "network_id": "N_642828",
    "status": "Connected",
    "speed": "1 Gbps",
    "duplex": "Full duplex",
    "enabled": True,
    "errors": 0,
    "clientCount": 3,
    "meraki_org_id": ORG_ID,
    "@timestamp": "2026-01-02T03:04:05.000Z",
}


def seed_switchport(fake_es: FakeElasticsearch, doc: dict, serial: str, port_id: str) -> None:
    fake_es.seed("meraki-switchport-metrics", {f"{serial}-{port_id}": doc})


def test_list_switchports_requires_auth(client: TestClient):
    resp = client.get("/switchports")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_list_switchports_empty(client: TestClient, bearer: str):
    resp = client.get("/switchports", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_switchports_returns_projections_with_network_name(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    fake_es.seed("meraki-network-metrics", {"N_642828": NETWORK_DOC})
    seed_switchport(fake_es, SWITCHPORT_DOC, "Q2HP-ABCD-1234", "1")
    resp = client.get("/switchports", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    sp = data[0]
    assert sp["serial"] == "Q2HP-ABCD-1234"
    assert sp["port_id"] == "1"
    assert sp["network_id"] == "N_642828"
    assert sp["network_name"] == "HQ Office"
    assert sp["status"] == "Connected"
    assert sp["speed"] == "1 Gbps"
    assert sp["duplex"] == "Full duplex"
    assert sp["enabled"] is True
    assert sp["errors"] == 0
    assert sp["client_count"] == SWITCHPORT_DOC["clientCount"]
    assert sp["as_of"] == "2026-01-02T03:04:05.000Z"


def test_list_switchports_filters_network_id(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_switchport(fake_es, SWITCHPORT_DOC, "Q2HP-ABCD-1234", "1")
    other = dict(SWITCHPORT_DOC, network_id="N_BRANCH", serial="Q2HP-ABCD-9999")
    seed_switchport(fake_es, other, "Q2HP-ABCD-9999", "1")
    resp = client.get(
        "/switchports", params={"network_id": "N_BRANCH"}, headers=auth_header(bearer)
    )
    assert resp.status_code == status.HTTP_200_OK
    sps = resp.json()
    assert len(sps) == 1
    assert sps[0]["serial"] == "Q2HP-ABCD-9999"


def test_list_switchports_filters_serial(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_switchport(fake_es, SWITCHPORT_DOC, "Q2HP-ABCD-1234", "1")
    other = dict(SWITCHPORT_DOC, serial="Q2HP-ABCD-9999", portId="2")
    seed_switchport(fake_es, other, "Q2HP-ABCD-9999", "2")
    resp = client.get(
        "/switchports", params={"serial": "Q2HP-ABCD-9999"}, headers=auth_header(bearer)
    )
    assert resp.status_code == status.HTTP_200_OK
    sps = resp.json()
    assert len(sps) == 1
    assert sps[0]["port_id"] == "2"


def test_get_switchport_by_serial_port(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_switchport(fake_es, SWITCHPORT_DOC, "Q2HP-ABCD-1234", "1")
    resp = client.get("/switchports/Q2HP-ABCD-1234/1", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["status"] == "Connected"


def test_get_switchport_not_found(client: TestClient, bearer: str):
    resp = client.get("/switchports/Q2HP-ABCD-1234/99", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_404_NOT_FOUND
