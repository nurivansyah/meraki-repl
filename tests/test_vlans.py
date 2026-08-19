"""REST read-mirror tests for VLANs (ticket 04)."""

from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import FakeElasticsearch, auth_header

ORG_ID = ""

VLAN_DOC = {
    "network_id": "N_642828",
    "vlan_id": "10",
    "name": "users",
    "subnet": "10.0.10.0/24",
    "applianceIp": "10.0.10.1",
    "dhcpHandling": "Run a DHCP server",
    "enabled": True,
    "network_name": "HQ Office",
    "meraki_org_id": ORG_ID,
    "@timestamp": "2026-01-02T03:04:05.000Z",
}


def seed_vlan(fake_es: FakeElasticsearch, doc: dict, network_id: str, vlan_id: str) -> None:
    fake_es.seed("meraki-vlan-metrics", {f"{network_id}-{vlan_id}": doc})


def test_list_vlans_requires_auth(client: TestClient):
    resp = client.get("/vlans")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_list_vlans_empty(client: TestClient, bearer: str):
    resp = client.get("/vlans", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_vlans_returns_projections(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_vlan(fake_es, VLAN_DOC, "N_642828", "10")
    resp = client.get("/vlans", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    v = data[0]
    assert v["network_id"] == "N_642828"
    assert v["vlan_id"] == "10"
    assert v["name"] == "users"
    assert v["subnet"] == "10.0.10.0/24"
    assert v["appliance_ip"] == "10.0.10.1"
    assert v["dhcp_handling"] == "Run a DHCP server"
    assert v["enabled"] is True
    assert v["network_name"] == "HQ Office"
    assert v["as_of"] == "2026-01-02T03:04:05.000Z"


def test_list_vlans_filters_network_id(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_vlan(fake_es, VLAN_DOC, "N_642828", "10")
    other = dict(VLAN_DOC, network_id="N_BRANCH", vlan_id="20")
    seed_vlan(fake_es, other, "N_BRANCH", "20")
    resp = client.get("/vlans", params={"network_id": "N_BRANCH"}, headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    vlans = resp.json()
    assert len(vlans) == 1
    assert vlans[0]["vlan_id"] == "20"


def test_get_vlan_by_network_and_id(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_vlan(fake_es, VLAN_DOC, "N_642828", "10")
    resp = client.get("/vlans/N_642828/10", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["name"] == "users"


def test_get_vlan_not_found(client: TestClient, bearer: str):
    resp = client.get("/vlans/N_642828/99", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_404_NOT_FOUND
