"""Pytest configuration and fixtures."""

import os

os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from tests.fakes.fake_token_repository import FakeTokenRepository
from twin.adapters.elasticsearch import get_es_client
from twin.main import app
from twin.presentation.dependencies import get_token_repository


class FakeElasticsearch:
    """In-memory fake for Elasticsearch client at the repository boundary."""

    def __init__(self):
        self._indices: dict[str, dict[str, dict]] = {}

    async def search(
        self, index: str, body: dict | None = None, **kwargs
    ) -> dict:
        """Mock search - returns empty hits by default."""
        idx = self._indices.get(index, {})
        hits = [
            {"_source": doc, "_id": doc_id} for doc_id, doc in idx.items()
        ]
        return {
            "hits": {"hits": hits, "total": {"value": len(hits)}},
            "took": 1,
        }

    async def get(self, index: str, id: str, **kwargs) -> dict | None:
        """Mock get by id."""
        idx = self._indices.get(index, {})
        doc = idx.get(id)
        if doc:
            return {"_source": doc, "_id": id, "found": True}
        return {"found": False}

    async def index(self, index: str, id: str, document: dict, **kwargs) -> dict:
        """Mock index document."""
        if index not in self._indices:
            self._indices[index] = {}
        self._indices[index][id] = document
        return {"_id": id, "result": "created"}

    async def delete(self, index: str, id: str, **kwargs) -> dict:
        """Mock delete document."""
        idx = self._indices.get(index, {})
        if id in idx:
            del idx[id]
            return {"result": "deleted"}
        return {"result": "not_found"}

    async def bulk(self, operations: list, **kwargs) -> dict:
        """Mock bulk operation."""
        return {"errors": False, "items": []}

    def clear(self):
        """Clear all indices."""
        self._indices.clear()

    def seed(self, index: str, docs: dict[str, dict]):
        """Seed an index with documents."""
        self._indices[index] = docs.copy()


@pytest.fixture
def fake_es() -> FakeElasticsearch:
    """Provide a fresh in-memory Elasticsearch fake."""
    return FakeElasticsearch()


@pytest.fixture
def token_repo() -> FakeTokenRepository:
    """Provide a fresh in-memory fake token repository."""
    return FakeTokenRepository()


@pytest.fixture
def client(fake_es: FakeElasticsearch, token_repo: FakeTokenRepository) -> TestClient:
    """FastAPI TestClient with ES and token repo dependencies overridden."""
    app.dependency_overrides[get_es_client] = lambda: fake_es
    app.dependency_overrides[get_token_repository] = lambda: token_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(fake_es: FakeElasticsearch, token_repo: FakeTokenRepository):
    """Async test client for async endpoints."""
    app.dependency_overrides[get_es_client] = lambda: fake_es
    app.dependency_overrides[get_token_repository] = lambda: token_repo
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
