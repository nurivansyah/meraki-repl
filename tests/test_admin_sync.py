"""Tests for the admin sync endpoint."""

from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import FakeElasticsearch
from tests.fakes.fake_graph_store import FakeGraphStore
from tests.fakes.fake_token_repository import FakeTokenRepository
from twin.presentation.admin_sync_router import router as admin_sync_router

BEARER = {"Authorization": "Bearer test-token"}


def _seed_es(es: FakeElasticsearch) -> None:
    es.seed(
        "meraki-topology-metrics",
        {
            "N_1": {
                "network_id": "N_1",
                "name": "Acme",
                "meraki_org_id": "",
                "node_count": 2,
                "link_count": 1,
                "offline_nodes": [],
                "topology": {
                    "nodes": [
                        {"id": "SW1", "name": "Switch 1",
                         "status": "online", "productType": "switch"},
                        {"id": "SW2", "name": "Switch 2",
                         "status": "down", "productType": "switch"},
                    ],
                    "links": [
                        {"source": "SW1", "sourcePort": "1",
                         "target": "SW2", "targetPort": "1"},
                    ],
                },
                "@timestamp": "2026-01-15T10:30:00Z",
            },
        },
    )


def _make_app(*, include_graph: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_sync_router)
    es = FakeElasticsearch()
    _seed_es(es)
    app.state.es = es
    app.state.token_repo = FakeTokenRepository()
    graph_store = FakeGraphStore() if include_graph else None
    app.state.graph_store = graph_store
    app.state.impact_default_depth = 10

    from twin.adapters.elasticsearch import get_es_client
    from twin.application.token_service import TokenService
    from twin.domain.tokens import Token, now_utc
    from twin.presentation.dependencies import get_token_repository, get_token_service

    app.dependency_overrides[get_es_client] = lambda: es
    app.dependency_overrides[get_token_repository] = lambda: app.state.token_repo

    async def _mock_validate(raw: str) -> Token:
        return Token(id=uuid.uuid4(), name="test", hashed_value="", created_at=now_utc())

    mock_service = TokenService(app.state.token_repo)
    mock_service.validate_bearer = _mock_validate  # type: ignore[attr-defined]
    app.dependency_overrides[get_token_service] = lambda: mock_service
    return app


class TestAdminSyncNeo4j:
    def test_requires_bearer(self) -> None:
        with TestClient(_make_app()) as client:
            resp = client.post("/admin/sync/neo4j")
            assert resp.status_code == 401

    def test_200_on_sync(self) -> None:
        with TestClient(_make_app()) as client:
            resp = client.post("/admin/sync/neo4j", headers=BEARER)
            assert resp.status_code == 200
            data = resp.json()
            assert data["networks_rebuilt"] == 1
            assert data["total_networks"] == 1
            assert data["as_of_max"] != ""

    def test_503_when_graph_missing(self) -> None:
        with TestClient(_make_app(include_graph=False)) as client:
            resp = client.post("/admin/sync/neo4j", headers=BEARER)
            assert resp.status_code == 503

    def test_idempotent_on_second_sync(self) -> None:
        with TestClient(_make_app()) as client:
            resp1 = client.post("/admin/sync/neo4j", headers=BEARER)
            assert resp1.json()["networks_rebuilt"] == 1

            resp2 = client.post("/admin/sync/neo4j", headers=BEARER)
            assert resp2.json()["networks_rebuilt"] == 0

    def test_rebuilds_with_newer_timestamp(self) -> None:
        with TestClient(_make_app()) as client:
            resp1 = client.post("/admin/sync/neo4j", headers=BEARER)
            assert resp1.json()["networks_rebuilt"] == 1

        # Create new app with newer timestamp
        app2 = _make_app()
        es2 = app2.state.es
        es2.seed(
            "meraki-topology-metrics",
            {
                "N_1": {
                    "network_id": "N_1",
                    "name": "Acme",
                    "meraki_org_id": "",
                    "node_count": 2,
                    "link_count": 1,
                    "offline_nodes": [],
                    "topology": {
                        "nodes": [
                            {"id": "SW1", "name": "Switch 1",
                             "status": "online", "productType": "switch"},
                            {"id": "SW2", "name": "Switch 2",
                             "status": "down", "productType": "switch"},
                        ],
                        "links": [
                            {"source": "SW1", "sourcePort": "1",
                             "target": "SW2", "targetPort": "1"},
                        ],
                    },
                    "@timestamp": "2026-01-15T11:00:00Z",
                },
            },
        )
        with TestClient(app2) as client:
            resp2 = client.post("/admin/sync/neo4j", headers=BEARER)
            assert resp2.json()["networks_rebuilt"] == 1

    def test_no_topology_documents(self) -> None:
        app = _make_app()
        app.state.es.clear()
        with TestClient(app) as client:
            resp = client.post("/admin/sync/neo4j", headers=BEARER)
            assert resp.status_code == 200
            data = resp.json()
            assert data["networks_rebuilt"] == 0
            assert data["total_networks"] == 0
