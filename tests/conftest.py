"""Pytest configuration and fixtures."""

import fnmatch
import os
import re

os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from tests.fakes.fake_token_repository import FakeTokenRepository
from twin.adapters.elasticsearch import get_es_client
from twin.application.token_service import TokenService
from twin.main import app
from twin.presentation.dependencies import get_token_repository


def _compare(value, bound, op) -> bool:
    """Compare a doc value against a range bound (string or numeric aware)."""
    try:
        value_f, bound_f = float(value), float(bound)
        cmp = value_f - bound_f
    except (TypeError, ValueError):
        cmp = (str(value) > str(bound)) - (str(value) < str(bound))
    if op == "gte":
        return cmp >= 0
    if op == "lte":
        return cmp <= 0
    if op == "gt":
        return cmp > 0
    if op == "lt":
        return cmp < 0
    return True


class FakeElasticsearch:
    """In-memory fake for Elasticsearch client at the repository boundary."""

    def __init__(self):
        self._indices: dict[str, dict[str, dict]] = {}

    @staticmethod
    def _matches(doc: dict, clause: dict) -> bool:
        """Apply a single query clause to a document."""
        if "term" in clause:
            field, value = next(iter(clause["term"].items()))
            result = doc.get(field) == value
        elif "range" in clause:
            field, limits = next(iter(clause["range"].items()))
            value = doc.get(field)
            if value is None:
                result = False
            else:
                result = all(_compare(value, bound, op) for op, bound in limits.items())
        elif "match" in clause:
            field, value = next(iter(clause["match"].items()))
            if isinstance(value, dict):
                value = value.get("query", value)
            result = str(value).lower() in str(doc.get(field, "")).lower()
        elif "query_string" in clause:
            qs = clause["query_string"]
            field = qs.get("default_field", "*")
            needle = str(qs.get("query", "")).lower()
            hay = doc.get(field, "")
            result = needle in str(hay).lower()
        elif "constant_score" in clause:
            inner = clause["constant_score"].get("filter", {})
            result = FakeElasticsearch._matches(doc, inner)
        elif "match_all" in clause:
            result = True
        elif "bool" in clause:
            sub_filters = clause["bool"].get("filter", [])
            must = clause["bool"].get("must", [])
            must_not = clause["bool"].get("must_not", [])
            result = all(
                FakeElasticsearch._matches(doc, f) for f in sub_filters
            ) and all(FakeElasticsearch._matches(doc, f) for f in must) and all(
                not FakeElasticsearch._matches(doc, f) for f in must_not
            )
        else:
            result = True
        return result

    def _resolve_indices(self, pattern: str) -> dict[str, dict[str, dict]]:
        """Expand an index name or wildcard pattern to {index: {doc_id: doc}}."""
        if "*" not in pattern:
            return {pattern: self._indices.get(pattern, {})}
        regex = re.compile(fnmatch.translate(pattern))
        matched = {}
        for name, docs in self._indices.items():
            if regex.fullmatch(name):
                matched[name] = docs
        return matched

    async def search(
        self, index: str, body: dict | None = None, **kwargs
    ) -> dict:
        """Mock search - filters seeded docs by the query body."""
        resolved = self._resolve_indices(index)
        query = (body or {}).get("query", {})
        hits = []
        for idx_name, docs in resolved.items():
            for doc_id, doc in docs.items():
                if query and not FakeElasticsearch._matches(doc, query):
                    continue
                hits.append({"_source": doc, "_id": doc_id, "_index": idx_name})
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
        """Seed (or add to) an index with documents."""
        self._indices.setdefault(index, {}).update(docs.copy())


@pytest.fixture
def fake_es() -> FakeElasticsearch:
    """Provide a fresh in-memory Elasticsearch fake."""
    return FakeElasticsearch()


@pytest.fixture
def token_repo() -> FakeTokenRepository:
    """Provide a fresh in-memory fake token repository."""
    return FakeTokenRepository()


@pytest.fixture
async def bearer(token_repo: FakeTokenRepository) -> str:
    """Issue a valid token on the fake repo and return its raw value."""
    service = TokenService(token_repo)
    _, raw = await service.issue_token("reader")
    return raw


def auth_header(bearer: str) -> dict[str, str]:
    """Return the ``Authorization`` header for a bearer token."""
    return {"Authorization": f"Bearer {bearer}"}


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
