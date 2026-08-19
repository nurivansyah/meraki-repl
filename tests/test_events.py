"""REST read-mirror tests for syslog event search (ticket 05)."""

from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import FakeElasticsearch, auth_header

ORG_ID = ""

EVENT_DOC = {
    "message": (
        "events type=association user=alice "
        "client_mac=aa:bb:cc:dd:ee:01 serial=Q2HP-ABCD-1234"
    ),
    "host": "10.0.0.2",
    "logsource": "Q2HP-ABCD-1234",
    "severity": 6,
    "facility": 4,
    "logstash.instance": "meraki",
    "@timestamp": "2026-01-02T03:04:05.000Z",
}


def seed_event(fake_es: FakeElasticsearch, doc: dict, doc_id: str) -> None:
    fake_es.seed("meraki-syslog-2026.01.02", {doc_id: doc})


def test_list_events_requires_auth(client: TestClient):
    resp = client.get("/twin/events")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_list_events_empty(client: TestClient, bearer: str):
    resp = client.get("/twin/events", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_list_events_returns_projection(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    seed_event(fake_es, EVENT_DOC, "abc123")
    resp = client.get("/twin/events", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    event = data[0]
    assert event["timestamp"] == "2026-01-02T03:04:05.000Z"
    assert event["message"] == EVENT_DOC["message"]
    assert event["device"] == "10.0.0.2"
    assert event["network_id"] is None
    assert event["raw"]["severity"] == EVENT_DOC["severity"]


def test_list_events_sorts_newest_first(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    older = dict(EVENT_DOC, **{"@timestamp": "2026-01-02T02:00:00.000Z"})
    newer = dict(EVENT_DOC, **{"@timestamp": "2026-01-02T03:00:00.000Z"})
    seed_event(fake_es, older, "older")
    seed_event(fake_es, newer, "newer")
    resp = client.get("/twin/events", headers=auth_header(bearer))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data[0]["timestamp"] == "2026-01-02T03:00:00.000Z"
    assert data[1]["timestamp"] == "2026-01-02T02:00:00.000Z"


def test_list_events_filters_time_range(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    older = dict(EVENT_DOC, **{"@timestamp": "2026-01-02T02:00:00.000Z"})
    newer = dict(EVENT_DOC, **{"@timestamp": "2026-01-02T03:00:00.000Z"})
    seed_event(fake_es, older, "older")
    seed_event(fake_es, newer, "newer")
    resp = client.get(
        "/twin/events",
        params={"start": "2026-01-02T02:30:00.000Z", "end": "2026-01-02T03:30:00.000Z"},
        headers=auth_header(bearer),
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert [e["timestamp"] for e in data] == ["2026-01-02T03:00:00.000Z"]


def test_list_events_filters_free_text(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    disassoc = dict(
        EVENT_DOC,
        message="events type=disassociation client_mac=aa:bb:cc:dd:ee:99 serial=Q2HP-ABCD-1234",
    )
    seed_event(fake_es, EVENT_DOC, "assoc")
    seed_event(fake_es, disassoc, "disassoc")
    resp = client.get(
        "/twin/events", params={"q": "disassociation"}, headers=auth_header(bearer)
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert "disassociation" in data[0]["message"]


def test_list_events_filters_device(
    client: TestClient, fake_es: FakeElasticsearch, bearer: str
):
    other = dict(EVENT_DOC, logsource="Q2HP-ABCD-9999")
    seed_event(fake_es, EVENT_DOC, "this")
    seed_event(fake_es, other, "other")
    resp = client.get(
        "/twin/events",
        params={"device": "Q2HP-ABCD-1234"},
        headers=auth_header(bearer),
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["raw"]["logsource"] == "Q2HP-ABCD-1234"

