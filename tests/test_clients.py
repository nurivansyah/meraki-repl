"""REST read-mirror tests for clients (ticket 04).

Clients are ephemeral: responses always carry ``ephemeral: true`` and device
fields reflect the device that most recently reported the client.
"""

from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import FakeElasticsearch, auth_header

ORG_ID = ""

NETWORK_DOC = {
    "name": "HQ Office",
    "timeZone": "America/Los_Angeles",
    "tags": ["prod"],
    "productTypes": ["wireless"],
    "meraki_org_id": ORG_ID,
    "network_id": "N_642828",
    "@timestamp": "2026-01-02T03:04:05.000Z",
}

CLIENT_DOC = {
    "mac": "aabbccddeeff",
    "network_id": "N_642828",
    "serial": "Q2HP-ABCD-1234",
    "ip": "10.0.0.42",
    "ip6": "fe80::1",
    "description": "laptop-01",
    "user": "alice",
    "vlan": "10",
    "switchport": "1",
    "ssid": "corp",
    "status": "Online",
    "lastSeen": "2026-01-02T03:00:00.000Z",
    "meraki_org_id": ORG_ID,
    "@timestamp": "2026-01-02T03:04:05.000Z",
}


def seed_client(fake_es: FakeElasticsearch, doc: dict, mac: str) -> None:
    fake_es.seed("meraki-client-metrics", {mac: doc})


def test_list_clients_requires_auth(client: TestClient):
    resp = client.get("/clients")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_list_clients_empty(client: TestClient, bearer: str):
    resp = client.get("/clients", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_clients_returns_projection_with_ephemeral_flag(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    fake_es.seed("meraki-network-metrics", {"N_642828": NETWORK_DOC})
    seed_client(fake_es, CLIENT_DOC, "aabbccddeeff")
    resp = client.get("/clients", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    c = data[0]
    assert c["mac"] == "aabbccddeeff"
    assert c["network_id"] == "N_642828"
    assert c["network_name"] == "HQ Office"
    assert c["serial"] == "Q2HP-ABCD-1234"
    assert c["ip"] == "10.0.0.42"
    assert c["ip6"] == "fe80::1"
    assert c["description"] == "laptop-01"
    assert c["user"] == "alice"
    assert c["vlan"] == "10"
    assert c["switchport"] == "1"
    assert c["ssid"] == "corp"
    assert c["status"] == "Online"
    assert c["last_seen"] == "2026-01-02T03:00:00.000Z"
    assert c["ephemeral"] is True
    assert c["as_of"] == "2026-01-02T03:04:05.000Z"


def test_list_clients_filters_network_id(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_client(fake_es, CLIENT_DOC, "aabbccddeeff")
    other = dict(CLIENT_DOC, network_id="N_BRANCH", mac="112233445566")
    seed_client(fake_es, other, "112233445566")
    resp = client.get("/clients", params={"network_id": "N_BRANCH"}, headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    clients = resp.json()
    assert len(clients) == 1
    assert clients[0]["mac"] == "112233445566"


def test_list_clients_filters_switchport(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_client(fake_es, CLIENT_DOC, "aabbccddeeff")
    other = dict(CLIENT_DOC, switchport="24", mac="112233445566")
    seed_client(fake_es, other, "112233445566")
    resp = client.get("/clients", params={"switchport": "24"}, headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    clients = resp.json()
    assert len(clients) == 1
    assert clients[0]["mac"] == "112233445566"


def test_list_clients_filters_ip(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_client(fake_es, CLIENT_DOC, "aabbccddeeff")
    other = dict(CLIENT_DOC, ip="10.0.0.99", mac="112233445566")
    seed_client(fake_es, other, "112233445566")
    resp = client.get("/clients", params={"ip": "10.0.0.99"}, headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    clients = resp.json()
    assert len(clients) == 1
    assert clients[0]["mac"] == "112233445566"


def test_list_clients_filters_vlan(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_client(fake_es, CLIENT_DOC, "aabbccddeeff")
    other = dict(CLIENT_DOC, vlan="20", mac="112233445566")
    seed_client(fake_es, other, "112233445566")
    resp = client.get("/clients", params={"vlan": "20"}, headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    clients = resp.json()
    assert len(clients) == 1
    assert clients[0]["mac"] == "112233445566"


def test_list_clients_filters_user(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_client(fake_es, CLIENT_DOC, "aabbccddeeff")
    other = dict(CLIENT_DOC, user="bob", mac="112233445566")
    seed_client(fake_es, other, "112233445566")
    resp = client.get("/clients", params={"user": "bob"}, headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    clients = resp.json()
    assert len(clients) == 1
    assert clients[0]["mac"] == "112233445566"


def test_get_client_by_mac(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    fake_es.seed("meraki-network-metrics", {"N_642828": NETWORK_DOC})
    seed_client(fake_es, CLIENT_DOC, "aabbccddeeff")
    resp = client.get("/clients/aabbccddeeff", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["user"] == "alice"
    assert resp.json()["ephemeral"] is True


def test_get_client_not_found(client: TestClient, bearer: str):
    resp = client.get("/clients/ffffffffffff", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_404_NOT_FOUND
