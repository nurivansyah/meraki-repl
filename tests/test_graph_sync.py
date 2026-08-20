"""Tests for the GraphSync transform — ES topology → Cypher statements."""

from datetime import UTC, datetime

import pytest

from twin.application.ports import CypherStatement
from twin.application.state_store import TopologyDocument

pytestmark = pytest.mark.unit


def _doc(
    *,
    network_id: str = "N_123",
    network_name: str = "Acme",
    as_of: str = "2026-01-15T10:30:00Z",
    nodes: list[dict] | None = None,
    links: list[dict] | None = None,
) -> TopologyDocument:
    if nodes is None:
        nodes = [
            {"id": "SW1", "name": "Switch 1", "status": "online", "productType": "switch"},
            {"id": "SW2", "name": "Switch 2", "status": "down", "productType": "switch"},
        ]
    if links is None:
        links = [{"source": "SW1", "sourcePort": "1", "target": "SW2", "targetPort": "2"}]
    return TopologyDocument(
        network_id=network_id,
        network_name=network_name,
        node_count=len(nodes),
        link_count=len(links),
        offline_nodes=[],
        nodes=nodes,
        links=links,
        as_of=as_of,
    )


class TestGraphSync:
    def test_returns_network_id_and_as_of(self) -> None:
        from twin.application.graph_sync import graph_sync

        doc = _doc(as_of="2026-01-15T10:30:00Z")
        rebuilt, stmts, new_as_of = graph_sync(doc, last_synced_at=None)
        assert rebuilt is True
        assert new_as_of == "2026-01-15T10:30:00Z"
        assert len(stmts) > 0

    def test_no_op_when_timestamp_equal(self) -> None:
        from twin.application.graph_sync import graph_sync

        doc = _doc(as_of="2026-01-15T10:30:00Z")
        rebuilt, stmts, _ = graph_sync(
            doc, last_synced_at=datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
        )
        assert rebuilt is False
        assert stmts == []

    def test_no_op_when_timestamp_older(self) -> None:
        from twin.application.graph_sync import graph_sync

        doc = _doc(as_of="2026-01-15T09:00:00Z")
        rebuilt, stmts, _ = graph_sync(
            doc, last_synced_at=datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
        )
        assert rebuilt is False
        assert stmts == []

    def test_rebuilds_when_newer(self) -> None:
        from twin.application.graph_sync import graph_sync

        doc = _doc(as_of="2026-01-15T11:00:00Z")
        rebuilt, stmts, _ = graph_sync(
            doc, last_synced_at=datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
        )
        assert rebuilt is True
        assert len(stmts) > 0

    def test_first_sync_always_rebuilds(self) -> None:
        from twin.application.graph_sync import graph_sync

        doc = _doc()
        rebuilt, stmts, _ = graph_sync(doc, last_synced_at=None)
        assert rebuilt is True
        assert len(stmts) > 0

    def test_statements_merge_network(self) -> None:
        from twin.application.graph_sync import graph_sync

        doc = _doc(network_id="N_ABC", network_name="Test Net")
        rebuilt, stmts, _ = graph_sync(doc, last_synced_at=None)
        assert rebuilt is True
        net_stmts = [s for s in stmts if "Network" in s.query and "MERGE" in s.query]
        assert len(net_stmts) >= 1
        params = net_stmts[0].params
        assert params["id"] == "N_ABC"
        assert params["name"] == "Test Net"

    def test_statements_merge_devices(self) -> None:
        from twin.application.graph_sync import graph_sync

        doc = _doc(
            nodes=[
                {"id": "SW1", "name": "Switch 1", "status": "online", "productType": "switch"},
                {"id": "SW2", "name": "Switch 2", "status": "down", "productType": "switch"},
            ]
        )
        rebuilt, stmts, _ = graph_sync(doc, last_synced_at=None)
        assert rebuilt is True
        dev_stmts = [s for s in stmts if "Device" in s.query and "SET d.name" in s.query]
        assert len(dev_stmts) >= 2
        dev_ids = {s.params["id"] for s in dev_stmts}
        assert "SW1" in dev_ids
        assert "SW2" in dev_ids

    def test_statements_merge_links(self) -> None:
        from twin.application.graph_sync import graph_sync

        doc = _doc(
            links=[{"source": "SW1", "sourcePort": "1", "target": "SW2", "targetPort": "2"}]
        )
        rebuilt, stmts, _ = graph_sync(doc, last_synced_at=None)
        assert rebuilt is True
        link_stmts = [s for s in stmts if "LINKED_TO" in s.query]
        assert len(link_stmts) == 1
        assert link_stmts[0].params["d1_id"] == "SW1"
        assert link_stmts[0].params["d2_id"] == "SW2"
        assert link_stmts[0].params["source_port"] == "1"
        assert link_stmts[0].params["target_port"] == "2"

    def test_empty_topology_no_device_merges(self) -> None:
        from twin.application.graph_sync import graph_sync

        doc = _doc(nodes=[], links=[])
        rebuilt, stmts, _ = graph_sync(doc, last_synced_at=None)
        assert rebuilt is True
        dev_merge_stmts = [s for s in stmts if "Device" in s.query and "SET d.name" in s.query]
        assert len(dev_merge_stmts) == 0

    def test_cypher_statement_is_frozen(self) -> None:
        from twin.application.graph_sync import graph_sync

        doc = _doc()
        _, stmts, _ = graph_sync(doc, last_synced_at=None)
        for s in stmts:
            assert isinstance(s, CypherStatement)
            with pytest.raises(AttributeError):
                s.query = "nope"  # type: ignore[misc]


class TestGraphSyncViaFake:
    """Integration: apply statements against FakeGraphStore and inspect state."""

    async def test_full_sync_populates_store(self) -> None:
        from tests.fakes.fake_graph_store import FakeGraphStore
        from twin.application.graph_sync import graph_sync

        store = FakeGraphStore()
        doc = _doc(
            network_id="N_1",
            network_name="Acme",
            nodes=[
                {"id": "SW1", "name": "Switch 1", "status": "online", "productType": "switch"},
                {"id": "SW2", "name": "Switch 2", "status": "down", "productType": "switch"},
            ],
            links=[{"source": "SW1", "sourcePort": "1", "target": "SW2", "targetPort": "2"}],
        )
        rebuilt, stmts, _ = graph_sync(doc, last_synced_at=None)
        assert rebuilt is True
        await store.execute(stmts)

        assert "N_1" in store.nodes.get("Network", {})
        assert "SW1" in store.nodes.get("Device", {})
        assert "SW2" in store.nodes.get("Device", {})
        link_edges = [e for e in store.edges if e["label"] == "LINKED_TO"]
        assert len(link_edges) == 1

    async def test_network_timestamp_recorded(self) -> None:
        from tests.fakes.fake_graph_store import FakeGraphStore
        from twin.application.graph_sync import graph_sync

        store = FakeGraphStore()
        doc = _doc(network_id="N_1", as_of="2026-03-01T12:00:00Z")
        rebuilt, stmts, _ = graph_sync(doc, last_synced_at=None)
        assert rebuilt is True
        await store.execute(stmts)
        net = store.nodes["Network"]["N_1"]
        assert net["last_synced_at"] is not None

    async def test_idempotent_sync(self) -> None:
        from tests.fakes.fake_graph_store import FakeGraphStore
        from twin.application.graph_sync import graph_sync

        store = FakeGraphStore()
        doc = _doc(network_id="N_1", as_of="2026-03-01T12:00:00Z")
        rebuilt, stmts, _ = graph_sync(doc, last_synced_at=None)
        assert rebuilt is True
        await store.execute(stmts)

        # Second sync with same timestamp — should be no-op
        last = store.nodes["Network"]["N_1"]["last_synced_at"]
        rebuilt2, stmts2, _ = graph_sync(doc, last_synced_at=last)
        assert rebuilt2 is False
        assert stmts2 == []

    async def test_rebuild_with_newer_timestamp(self) -> None:
        from tests.fakes.fake_graph_store import FakeGraphStore
        from twin.application.graph_sync import graph_sync

        store = FakeGraphStore()
        doc1 = _doc(network_id="N_1", as_of="2026-03-01T12:00:00Z")
        rebuilt, stmts, _ = graph_sync(doc1, last_synced_at=None)
        assert rebuilt is True
        await store.execute(stmts)

        last = store.nodes["Network"]["N_1"]["last_synced_at"]
        doc2 = _doc(network_id="N_1", as_of="2026-03-01T13:00:00Z")
        rebuilt2, stmts2, _ = graph_sync(doc2, last_synced_at=last)
        assert rebuilt2 is True
        assert len(stmts2) > 0
        await store.execute(stmts2)
        assert store.nodes["Network"]["N_1"]["last_synced_at"] > last

    async def test_device_status_recorded(self) -> None:
        from tests.fakes.fake_graph_store import FakeGraphStore
        from twin.application.graph_sync import graph_sync

        store = FakeGraphStore()
        doc = _doc(
            nodes=[
                {"id": "SW1", "name": "Switch 1", "status": "online", "productType": "switch"},
                {"id": "SW2", "name": "Switch 2", "status": "down", "productType": "switch"},
            ]
        )
        _, stmts, _ = graph_sync(doc, last_synced_at=None)
        await store.execute(stmts)
        assert store.nodes["Device"]["SW1"]["status"] == "online"
        assert store.nodes["Device"]["SW2"]["status"] == "down"
