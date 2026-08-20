"""Tests for the impact REST endpoint."""

from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import FakeElasticsearch
from tests.fakes.fake_graph_store import FakeGraphStore
from tests.fakes.fake_token_repository import FakeTokenRepository
from twin.application.graph_sync import graph_sync
from twin.application.state_store import TopologyDocument
from twin.presentation.impact_router import router as impact_router

BEARER = {"Authorization": "Bearer test-token"}


def _seed_graph() -> FakeGraphStore:
    """Seed a FakeGraphStore with a 3-device linear topology."""
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
        as_of="2026-01-15T10:30:00Z",
    )
    rebuilt, stmts, _ = graph_sync(doc, last_synced_at=None)
    assert rebuilt is True
    # Seed store synchronously (FakeGraphStore._apply is sync)
    for stmt in stmts:
        store._apply(stmt.query, stmt.params)
    return store


def _make_app(*, include_graph: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(impact_router)
    es = FakeElasticsearch()
    app.state.es = es
    app.state.token_repo = FakeTokenRepository()
    graph_store = _seed_graph() if include_graph else None
    app.state.graph_store = graph_store
    app.state.impact_default_depth = 10

    from twin.adapters.elasticsearch import get_es_client
    from twin.application.token_service import TokenService
    from twin.domain.tokens import Token, now_utc
    from twin.presentation.dependencies import get_token_repository, get_token_service

    app.dependency_overrides[get_es_client] = lambda: es
    app.dependency_overrides[get_token_repository] = lambda: app.state.token_repo

    # Create a mock token service that always validates
    async def _mock_validate(raw: str) -> Token:
        return Token(id=uuid.uuid4(), name="test", hashed_value="", created_at=now_utc())

    mock_service = TokenService(app.state.token_repo)
    mock_service.validate_bearer = _mock_validate  # type: ignore[attr-defined]
    app.dependency_overrides[get_token_service] = lambda: mock_service
    return app


class TestImpactEndpoint:
    def test_requires_bearer(self) -> None:
        with TestClient(_make_app()) as client:
            resp = client.get("/twin/impact?device=SW1")
            assert resp.status_code == 401

    def test_200_on_valid_seed(self) -> None:
        with TestClient(_make_app()) as client:
            resp = client.get("/twin/impact?device=SW1", headers=BEARER)
            assert resp.status_code == 200
            data = resp.json()
            assert data["seed_id"] == "SW1"
            assert len(data["reachable"]) >= 1
            assert "as_of" in data

    def test_404_on_unknown_device(self) -> None:
        with TestClient(_make_app()) as client:
            resp = client.get("/twin/impact?device=NONEXISTENT", headers=BEARER)
            assert resp.status_code == 404

    def test_503_when_graph_missing(self) -> None:
        with TestClient(_make_app(include_graph=False)) as client:
            resp = client.get("/twin/impact?device=SW1", headers=BEARER)
            assert resp.status_code == 503

    def test_uplink_seed(self) -> None:
        with TestClient(_make_app()) as client:
            resp = client.get(
                "/twin/impact?uplink_serial=SW1&uplink_interface=1",
                headers=BEARER,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["seed_id"] == "SW1:1"
            total = len(data["reachable"]) + len(data["masked"])
            assert total >= 2

    def test_depth_limits(self) -> None:
        with TestClient(_make_app()) as client:
            resp = client.get(
                "/twin/impact?uplink_serial=SW1&uplink_interface=1&depth=1",
                headers=BEARER,
            )
            assert resp.status_code == 200
            data = resp.json()
            total = len(data["reachable"]) + len(data["masked"])
            assert total == 2

    def test_no_params_returns_404(self) -> None:
        with TestClient(_make_app()) as client:
            resp = client.get("/twin/impact", headers=BEARER)
            assert resp.status_code == 404

    def test_result_has_masked(self) -> None:
        with TestClient(_make_app()) as client:
            resp = client.get("/twin/impact?device=SW1", headers=BEARER)
            data = resp.json()
            assert len(data["masked"]) == 1
            assert data["masked"][0]["id"] == "SW2"

    def test_as_of_populated(self) -> None:
        with TestClient(_make_app()) as client:
            resp = client.get("/twin/impact?device=SW1", headers=BEARER)
            data = resp.json()
            assert data["as_of"] != ""
