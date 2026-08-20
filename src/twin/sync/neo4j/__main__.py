"""CLI for one-shot ES→Neo4j graph sync.

Usage::

    python -m twin.sync.neo4j

Env vars (all optional, same names as the app):
    TESTING=1            Use fake ES and FakeGraphStore (for tests)
    NEO4J_URI            bolt://...
    NEO4J_USERNAME        neo4j
    NEO4J_PASSWORD        changeme
    NEO4J_AUTH            true|false
    ELASTICSEARCH_HOSTS   http://localhost:9200
"""

from __future__ import annotations

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


async def _run() -> None:
    if os.environ.get("TESTING") == "1":
        await _run_fake()
    else:
        await _run_real()


async def _run_fake() -> None:
    """Run against in-memory fakes (for subprocess tests)."""
    from datetime import datetime

    from tests.conftest import FakeElasticsearch
    from tests.fakes.fake_graph_store import FakeGraphStore
    from twin.adapters.elasticsearch_state_store import ElasticsearchStateStore
    from twin.application.graph_sync import graph_sync
    from twin.application.ports import CypherStatement

    es = FakeElasticsearch()
    graph = FakeGraphStore()

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
                        {"source": "SW1", "sourcePort": "1", "target": "SW2", "targetPort": "1"},
                    ],
                },
                "@timestamp": "2026-01-15T10:30:00Z",
            },
        },
    )

    store = ElasticsearchStateStore(es)
    topo_docs = await store.list_topology_documents()

    rebuilt = 0
    for doc in topo_docs:
        check_rows = await graph.execute(
            [
                CypherStatement(
                    query="MATCH (n:Network {id: $id}) RETURN n.last_synced_at AS last_synced_at",
                    params={"id": doc.network_id},
                )
            ]
        )
        last_synced_at = None
        if check_rows and check_rows[0].get("last_synced_at"):
            raw = check_rows[0]["last_synced_at"]
            last_synced_at = (
                raw if isinstance(raw, datetime)
                else datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            )

        did_rebuild, stmts, new_as_of = graph_sync(doc, last_synced_at)
        if did_rebuild:
            await graph.execute(stmts)
            rebuilt += 1
        log.info("Network %s: rebuilt=%s as_of=%s", doc.network_id, did_rebuild, new_as_of)

    log.info("Done: %d/%d networks rebuilt", rebuilt, len(topo_docs))


async def _run_real() -> None:
    """Run against real ES + real Neo4j."""
    from elasticsearch import AsyncElasticsearch
    from neo4j import AsyncGraphDatabase

    from twin.config import settings

    es = AsyncElasticsearch(
        hosts=settings.es_hosts.split(","),
        basic_auth=(settings.es_username, settings.es_password),
        request_timeout=30,
    )
    auth = (settings.neo4j_username, settings.neo4j_password) if settings.neo4j_auth else None
    driver = AsyncGraphDatabase.driver(settings.neo4j_uri, auth=auth)

    try:
        from datetime import datetime

        from twin.adapters.elasticsearch_state_store import ElasticsearchStateStore
        from twin.adapters.neo4j_graph_store import Neo4jGraphStore
        from twin.application.graph_sync import graph_sync
        from twin.application.ports import CypherStatement

        store = ElasticsearchStateStore(es)
        graph = Neo4jGraphStore(driver)
        topo_docs = await store.list_topology_documents()

        rebuilt = 0
        for doc in topo_docs:
            check_rows = await graph.execute(
                [
                    CypherStatement(
                        query=(
                            "MATCH (n:Network {id: $id}) "
                            "RETURN n.last_synced_at AS last_synced_at"
                        ),
                        params={"id": doc.network_id},
                    )
                ]
            )
            last_synced_at = None
            if check_rows and check_rows[0].get("last_synced_at"):
                raw = check_rows[0]["last_synced_at"]
                last_synced_at = (
                    raw if isinstance(raw, datetime)
                    else datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                )

            did_rebuild, stmts, new_as_of = graph_sync(doc, last_synced_at)
            if did_rebuild:
                await graph.execute(stmts)
                rebuilt += 1
            log.info("Network %s: rebuilt=%s as_of=%s", doc.network_id, did_rebuild, new_as_of)

        log.info("Done: %d/%d networks rebuilt", rebuilt, len(topo_docs))
    finally:
        await driver.close()
        await es.close()


if __name__ == "__main__":
    asyncio.run(_run())
