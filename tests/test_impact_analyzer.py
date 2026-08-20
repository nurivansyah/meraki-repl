"""Tests for the ImpactAnalyzer — reachability analysis against the graph."""


import pytest

from twin.domain.graph import ImpactResult

pytestmark = pytest.mark.unit


async def _make_store(
    *, as_of: str = "2026-01-15T10:30:00Z",
) -> FakeGraphStore:  # noqa: F821
    from tests.fakes.fake_graph_store import FakeGraphStore
    from twin.application.graph_sync import graph_sync
    from twin.application.state_store import TopologyDocument

    store = FakeGraphStore()
    doc = TopologyDocument(
        network_id="N_1",
        network_name="Acme",
        node_count=3,
        link_count=2,
        offline_nodes=[],
        nodes=[
            {"id": "SW1", "name": "Switch 1", "status": "online", "productType": "switch"},
            {"id": "SW2", "name": "Switch 2", "status": "down", "productType": "switch"},
            {"id": "SW3", "name": "Switch 3", "status": "online", "productType": "switch"},
        ],
        links=[
            {"source": "SW1", "sourcePort": "1", "target": "SW2", "targetPort": "1"},
            {"source": "SW2", "sourcePort": "2", "target": "SW3", "targetPort": "1"},
        ],
        as_of=as_of,
    )
    _, stmts, _ = graph_sync(doc, last_synced_at=None)
    await store.execute(stmts)
    return store


async def _analyze(store, serial: str, *, depth: int | None = None) -> ImpactResult | None:
    from twin.application.impact_analyzer import ImpactAnalyzer

    analyzer = ImpactAnalyzer(graph=store, default_depth=10)
    return await analyzer.impact_from_device(serial, depth=depth)


async def _analyze_uplink(
    store,
    serial: str,
    interface: str,
    *,
    depth: int | None = None,
) -> ImpactResult | None:
    from twin.application.impact_analyzer import ImpactAnalyzer

    analyzer = ImpactAnalyzer(graph=store, default_depth=10)
    return await analyzer.impact_from_uplink(serial, interface, depth=depth)


class TestImpactFromDevice:
    async def test_returns_reachable_and_masked(self) -> None:
        store = await _make_store()
        result = await _analyze(store, "SW1")
        assert result is not None
        assert result.seed_id == "SW1"
        assert len(result.reachable) == 1  # SW3 is reachable
        assert len(result.masked) == 1  # SW2 is down (masked)
        assert result.masked[0].id == "SW2"

    async def test_seed_down_still_walks(self) -> None:
        """When the seed itself is down, traversal still starts from it —
        the seed is excluded from results (it's the trigger, not the impact).
        Neighbors are still reachable."""
        from tests.fakes.fake_graph_store import FakeGraphStore
        from twin.application.graph_sync import graph_sync
        from twin.application.state_store import TopologyDocument

        store = FakeGraphStore()
        doc = TopologyDocument(
            network_id="N_1",
            network_name="Acme",
            node_count=2,
            link_count=1,
            offline_nodes=[],
            nodes=[
                {"id": "SW1", "name": "Switch 1", "status": "down", "productType": "switch"},
                {"id": "SW2", "name": "Switch 2", "status": "online", "productType": "switch"},
            ],
            links=[{"source": "SW1", "sourcePort": "1", "target": "SW2", "targetPort": "1"}],
            as_of="2026-01-15T10:30:00Z",
        )
        _, stmts, _ = graph_sync(doc, last_synced_at=None)
        await store.execute(stmts)

        result = await _analyze(store, "SW1")
        assert result is not None
        assert result.seed_id == "SW1"
        # Seed (SW1) not in reachable/masked — it's the trigger, not the impact
        assert all(d.id != "SW1" for d in result.reachable)
        assert all(d.id != "SW1" for d in result.masked)
        # SW2 is reachable
        assert len(result.reachable) == 1

    async def test_unknown_seed_returns_none(self) -> None:
        store = await _make_store()
        result = await _analyze(store, "NONEXISTENT")
        assert result is None

    async def test_depth_limits_reachable(self) -> None:
        store = await _make_store()
        # depth=1 from SW1: only SW2 (masked), not SW3
        result = await _analyze(store, "SW1", depth=1)
        assert result is not None
        assert len(result.reachable) == 0
        assert len(result.masked) == 1

    async def test_as_of_populated(self) -> None:
        store = await _make_store(as_of="2026-06-01T08:00:00Z")
        result = await _analyze(store, "SW1")
        assert result is not None
        assert result.as_of == "2026-06-01T08:00:00Z"

    async def test_seed_self_not_in_reachable(self) -> None:
        store = await _make_store()
        result = await _analyze(store, "SW1")
        assert result is not None
        reachable_ids = [d.id for d in result.reachable]
        assert "SW1" not in reachable_ids


class TestImpactFromUplink:
    async def test_returns_reachable(self) -> None:
        store = await _make_store()
        result = await _analyze_uplink(store, "SW1", "1")
        assert result is not None
        assert result.seed_id == "SW1:1"
        total = len(result.reachable) + len(result.masked)
        assert total >= 2

    async def test_unknown_port_returns_none(self) -> None:
        store = await _make_store()
        result = await _analyze_uplink(store, "SW1", "99")
        assert result is None

    async def test_depth_limits(self) -> None:
        store = await _make_store()
        # Uplink SW1:1 → neighbor SW2, depth=1 from SW2: SW1 + SW3 = 2
        result = await _analyze_uplink(store, "SW1", "1", depth=1)
        assert result is not None
        total = len(result.reachable) + len(result.masked)
        assert total == 2
