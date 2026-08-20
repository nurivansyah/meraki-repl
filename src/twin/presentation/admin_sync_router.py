"""Admin endpoint for triggering ES→Neo4j graph sync."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse

from twin.application.graph_sync import graph_sync
from twin.application.ports import CypherStatement
from twin.application.state_store import StateStore
from twin.domain.tokens import Token
from twin.presentation.bearer import require_bearer
from twin.presentation.dependencies import get_state_store

AuthenticatedToken = Annotated[Token, Depends(require_bearer)]
State = Annotated[StateStore, Depends(get_state_store)]

router = APIRouter(prefix="/admin", tags=["admin-sync"])


@router.post("/sync/neo4j")
async def sync_neo4j(
    _token: AuthenticatedToken,
    store: State,
    request: Request,
) -> JSONResponse:
    """Trigger a full ES→Neo4j topology sync.

    For each network, compares ``topology.@timestamp`` against
    ``Network.last_synced_at`` in Neo4j and rebuilds the subgraph
    only when ES is newer.
    """
    graph_store = getattr(request.app.state, "graph_store", None)
    if graph_store is None:
        return JSONResponse(
            content={"error": "graph store unavailable"},
            status_code=503,
        )

    topo_docs = await store.list_topology_documents()
    networks_rebuilt = 0
    total = len(topo_docs)
    as_of_max = ""

    for doc in topo_docs:
        # Fetch current last_synced_at from Neo4j
        check_rows = await graph_store.execute(
            [
                CypherStatement(
                    query="MATCH (n:Network {id: $id}) RETURN n.last_synced_at AS last_synced_at",
                    params={"id": doc.network_id},
                )
            ]
        )
        from datetime import datetime

        last_synced_at = None
        if check_rows and check_rows[0].get("last_synced_at"):
            raw = check_rows[0]["last_synced_at"]
            if isinstance(raw, datetime):
                last_synced_at = raw
            else:
                iso = str(raw).replace("Z", "+00:00")
                last_synced_at = datetime.fromisoformat(iso)

        rebuilt, stmts, new_as_of = graph_sync(doc, last_synced_at)
        if rebuilt:
            await graph_store.execute(stmts)
            networks_rebuilt += 1
        as_of_max = max(as_of_max, new_as_of)

    return JSONResponse(
        content={
            "networks_rebuilt": networks_rebuilt,
            "total_networks": total,
            "as_of_max": as_of_max,
        }
    )
