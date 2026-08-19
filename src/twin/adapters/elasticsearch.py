"""Elasticsearch adapter - provides async ES client."""

import os
from contextlib import asynccontextmanager

from elasticsearch import AsyncElasticsearch

from twin.config import settings

_es_client: AsyncElasticsearch | None = None


@asynccontextmanager
async def es_lifespan():
    """Lifespan manager for ES client. Skips real connection in test mode."""
    # ruff: noqa: PLW0603
    global _es_client
    if os.getenv("TESTING") == "1":
        # In test mode, don't create real ES client - tests will inject fake
        yield None
        return

    _es_client = AsyncElasticsearch(
        hosts=settings.es_hosts.split(","),
        basic_auth=(settings.es_username, settings.es_password),
        request_timeout=30,
    )
    try:
        yield _es_client
    finally:
        await _es_client.close()
        _es_client = None


def get_es_client() -> AsyncElasticsearch:
    """Dependency injector for Elasticsearch client."""
    if _es_client is None:
        raise RuntimeError("ES client not initialized. Use es_lifespan().")
    return _es_client
