"""Neo4j adapter — translates ``CypherStatement`` objects into Bolt driver calls.

The ``Neo4jGraphStore`` opens an ``AsyncGraphDatabase.driver`` and exposes the
``GraphPort`` protocol so the application core can execute structured Cypher
statements without depending on the ``neo4j`` package directly.

Under ``TESTING=1`` the adapter yields ``None`` and no driver is opened —
the lifespan skips graph wiring entirely.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from twin.application.ports import CypherStatement

logger = logging.getLogger(__name__)


class Neo4jGraphStore:
    """Real Neo4j adapter implementing ``GraphPort``."""

    def __init__(self, driver: object) -> None:
        self._driver = driver

    async def execute(self, statements: list[CypherStatement]) -> list[dict]:
        """Execute a batch of Cypher statements and return result rows.

        Each statement is executed in its own transaction.
        """
        results: list[dict] = []
        async with self._driver.session() as session:  # type: ignore[union-attr]
            for stmt in statements:
                cursor = await session.run(stmt.query, **stmt.params)
                async for record in cursor:
                    results.append(dict(record))
        return results


@asynccontextmanager
async def neo4j_lifespan():
    """Yield a ``Neo4jGraphStore`` (or ``None`` when ``TESTING=1``) as a
    context manager compatible with FastAPI lifespan.
    """
    if os.environ.get("TESTING") == "1":
        yield None
        return

    from twin.config import settings

    try:
        from neo4j import AsyncGraphDatabase
    except ImportError:
        logger.warning("neo4j package not installed — graph projection disabled")
        yield None
        return

    auth = (settings.neo4j_username, settings.neo4j_password) if settings.neo4j_auth else None
    try:
        driver = AsyncGraphDatabase.driver(settings.neo4j_uri, auth=auth)
        yield Neo4jGraphStore(driver)
    except Exception:
        logger.warning(
            "Failed to connect to Neo4j at %s — graph projection disabled",
            settings.neo4j_uri,
            exc_info=True,
        )
        yield None
