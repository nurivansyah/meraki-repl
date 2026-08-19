"""REST read-mirror tests for change-list search (ticket 05)."""

from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import FakeElasticsearch, auth_header

ORG_ID = ""

CHANGE_DOC = {
    "serial": "Q2HP-ABCD-1234",
    "network_id": "N_642828",
    "name": "core-switch-01",
    "status": "offline",
    "history": {"previous": {"status": "online", "name": "core-switch-01"}, "changed": True},
    "meraki_org_id": ORG_ID,
    "@timestamp": "2026-01-02T03:04:05.000Z",
}

NETWORK_CHANGE_DOC = {
    "network_id": "N_642828",
    "name": "HQ Office",
    "tags": ["prod"],
    "history": {
        "previous": {"name": "HQ Office", "tags": ["prod", "office"]},
        "changed": True,
    },
    "meraki_org_id": ORG_ID,
    "@timestamp": "2026-01-02T04:00:00.000Z",
}


def seed_change(fake_es: FakeElasticsearch, doc: dict, doc_id: str, index: str) -> None:
    fake_es.seed(index, {doc_id: doc})


def test_list_changes_requires_auth(client: TestClient):
    resp = client.get("/twin/changes")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_list_changes_empty(client: TestClient, bearer: str):
    resp = client.get("/twin/changes", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_changes_returns_projection(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_change(fake_es, CHANGE_DOC, "entry1", "meraki-inventory-history-2026.01.02")
    resp = client.get("/twin/changes", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    change = data[0]
    assert change["timestamp"] == "2026-01-02T03:04:05.000Z"
    assert change["as_of"] == "2026-01-02T03:04:05.000Z"
    assert change["index"] == "meraki-inventory-history-2026.01.02"
    assert change["entity_type"] == "inventory"
    assert change["entity_id"] == "Q2HP-ABCD-1234"
    assert change["serial"] == "Q2HP-ABCD-1234"
    assert change["network_id"] == "N_642828"
    assert change["previous"] == {"status": "online", "name": "core-switch-01"}
    assert change["current"]["status"] == "offline"


def test_list_changes_filters_device(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    other = dict(CHANGE_DOC, serial="Q2HP-ABCD-9999")
    seed_change(fake_es, other, "entry1", "meraki-device-history-2026.01.02")
    seed_change(fake_es, CHANGE_DOC, "entry2", "meraki-device-history-2026.01.02")
    resp = client.get(
        "/twin/changes",
        params={"device": "Q2HP-ABCD-1234"},
        headers=auth_header(bearer),
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["entity_id"] == "Q2HP-ABCD-1234"


def test_list_changes_filters_network(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_change(fake_es, NETWORK_CHANGE_DOC, "entry1", "meraki-network-history-2026.01.02")
    resp = client.get(
        "/twin/changes",
        params={"network_id": "N_642828"},
        headers=auth_header(bearer),
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    change = data[0]
    assert change["entity_type"] == "network"
    assert change["entity_id"] == "N_642828"


def test_list_changes_sorts_newest_first(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    older = dict(CHANGE_DOC, **{"@timestamp": "2026-01-02T02:00:00.000Z"})
    newer = dict(CHANGE_DOC, **{"@timestamp": "2026-01-02T03:00:00.000Z"})
    seed_change(fake_es, older, "entry1", "meraki-inventory-history-2026.01.02")
    seed_change(fake_es, newer, "entry2", "meraki-inventory-history-2026.01.02")
    resp = client.get("/twin/changes", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert [c["timestamp"] for c in data] == [
        "2026-01-02T03:00:00.000Z",
        "2026-01-02T02:00:00.000Z",
    ]


def test_list_changes_respects_window(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    # e1 in window [03:00, 06:00]
    # e2 BEFORE window (02:00)
    seed_change(
        fake_es,
        dict(CHANGE_DOC, **{"@timestamp": "2026-01-02T05:00:00.000Z"}),
        "e1",
        "meraki-device-history-2026.01.02",
    )
    seed_change(
        fake_es,
        dict(CHANGE_DOC, **{"@timestamp": "2026-01-02T02:00:00.000Z"}),
        "e2",
        "meraki-device-history-2026.01.02",
    )
    resp = client.get(
        "/twin/changes",
        params={"start": "2026-01-02T03:00:00.000Z", "end": "2026-01-02T06:00:00.000Z"},
        headers=auth_header(bearer),
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert [c["timestamp"] for c in data] == ["2026-01-02T05:00:00.000Z"]


def test_list_changes_excludes_other_orgs(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    other = dict(CHANGE_DOC, meraki_org_id="ORG_2")
    seed_change(fake_es, other, "entry1", "meraki-device-history-2026.01.02")
    seed_change(fake_es, CHANGE_DOC, "entry2", "meraki-device-history-2026.01.02")
    resp = client.get("/twin/changes", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert [c["serial"] for c in data] == ["Q2HP-ABCD-1234"]

