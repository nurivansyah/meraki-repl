"""REST read-mirror tests for topology (ticket 04)."""

from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import FakeElasticsearch, auth_header

ORG_ID = ""

TOPOLOGY_DOC = {
    "network_id": "N_642828",
    "name": "HQ Office",
    "node_count": 2,
    "link_count": 1,
    "offline_nodes": ["core-switch-02"],
    "topology": {
        "nodes": [
            {
                "id": "Q2HP-ABCD-1234",
                "name": "core-switch-01",
                "status": "online",
                "productType": "switch",
            },
            {
                "id": "Q2HP-ABCD-5678",
                "name": "core-switch-02",
                "status": "offline",
                "productType": "switch",
            },
        ],
        "links": [
            {
                "ends": [
                    {"nodeId": "Q2HP-ABCD-1234", "portId": "1"},
                    {"nodeId": "Q2HP-ABCD-5678", "portId": "2"},
                ]
            }
        ],
    },
    "meraki_org_id": ORG_ID,
    "@timestamp": "2026-01-02T03:04:05.000Z",
}


def seed_topology(fake_es: FakeElasticsearch, doc: dict, network_id: str) -> None:
    fake_es.seed("meraki-topology-metrics", {network_id: doc})


def test_list_topology_requires_auth(client: TestClient):
    resp = client.get("/topology")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_list_topology_empty(client: TestClient, bearer: str):
    resp = client.get("/topology", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_topology_returns_projections(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_topology(fake_es, TOPOLOGY_DOC, "N_642828")
    resp = client.get("/topology", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    t = data[0]
    assert t["network_id"] == "N_642828"
    assert t["network_name"] == "HQ Office"
    assert t["node_count"] == TOPOLOGY_DOC["node_count"]
    assert t["link_count"] == TOPOLOGY_DOC["link_count"]
    assert t["offline_nodes"] == ["core-switch-02"]
    assert t["as_of"] == "2026-01-02T03:04:05.000Z"


def test_list_topology_excludes_other_orgs(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    other = dict(TOPOLOGY_DOC, meraki_org_id="ORG_2")
    seed_topology(fake_es, other, "N_OTHER")
    seed_topology(fake_es, TOPOLOGY_DOC, "N_642828")
    resp = client.get("/topology", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert [t["network_id"] for t in data] == ["N_642828"]


def test_get_topology_by_network(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_topology(fake_es, TOPOLOGY_DOC, "N_642828")
    resp = client.get("/topology/N_642828", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    t = resp.json()
    nodes = t["nodes"]
    assert len(nodes) == len(TOPOLOGY_DOC["topology"]["nodes"])
    assert nodes[0]["id"] == "Q2HP-ABCD-1234"
    assert nodes[0]["name"] == "core-switch-01"
    assert nodes[0]["status"] == "online"
    assert nodes[0]["product_type"] == "switch"
    links = t["links"]
    assert len(links) == 1
    assert links[0]["source"] == "Q2HP-ABCD-1234"
    assert links[0]["source_port"] == "1"
    assert links[0]["target"] == "Q2HP-ABCD-5678"
    assert links[0]["target_port"] == "2"


def test_get_topology_not_found(client: TestClient, bearer: str):
    resp = client.get("/topology/N_MISSING", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_404_NOT_FOUND
