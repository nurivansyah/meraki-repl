"""GraphSync — transforms an ES TopologyDocument into Cypher statements.

The transform is a pure function: it receives the current topology doc and
the last-synced-at timestamp and returns the list of ``CypherStatement``
objects to execute against the graph, plus a flag indicating whether a
rebuild was needed.

The caller orchestrates execution through the ``GraphPort``.
"""

from __future__ import annotations

from datetime import datetime

from twin.application.ports import CypherStatement
from twin.application.state_store import TopologyDocument


def graph_sync(
    doc: TopologyDocument,
    last_synced_at: datetime | None,
) -> tuple[bool, list[CypherStatement], str]:
    """Return ``(rebuilt, statements, new_as_of)``.

    *rebuilt* is ``True`` when the topology is newer than the current
    ``last_synced_at`` and Cypher statements were emitted; ``False`` when
    no work was needed (topology is already current).
    """
    topology_as_of = doc.as_of

    if last_synced_at is not None and _parse_iso(topology_as_of) <= last_synced_at:
        return False, [], topology_as_of

    stmts = _rebuild(doc, topology_as_of)
    return True, stmts, topology_as_of


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 string, stripping trailing ``Z`` for Python 3.14."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _rebuild(
    doc: TopologyDocument,
    topology_as_of: str,
) -> list[CypherStatement]:
    """Emit the full set of Cypher statements to rebuild a network subgraph."""
    stmts: list[CypherStatement] = []

    # 1. MERGE the Network node and set its name + last_synced_at
    stmts.append(
        CypherStatement(
            query=(
                "MERGE (n:Network {id: $id}) "
                "SET n.name = $name, n.last_synced_at = datetime($last_synced_at)"
            ),
            params={
                "id": doc.network_id,
                "name": doc.network_name or doc.network_id,
                "last_synced_at": topology_as_of,
            },
        )
    )

    # 2. Delete existing IN_NETWORK edges for this network (clean-slate for
    #    the device subgraph under this network).
    stmts.append(
        CypherStatement(
            query=(
                "MATCH (d:Device)-[r:IN_NETWORK]->(n:Network {id: $id}) "
                "DELETE r"
            ),
            params={"id": doc.network_id},
        )
    )

    # 3. Merge Device nodes for each topology node
    for node in doc.nodes:
        stmts.append(
            CypherStatement(
                query=(
                    "MERGE (d:Device {id: $id}) "
                    "SET d.name = $name, d.status = $status, "
                    "d.product_type = $product_type, d.network_id = $network_id"
                ),
                params={
                    "id": node["id"],
                    "name": node.get("name"),
                    "status": node.get("status"),
                    "product_type": node.get("productType"),
                    "network_id": doc.network_id,
                },
            )
        )

    # 4. Link each device to its network
    for node in doc.nodes:
        stmts.append(
            CypherStatement(
                query=(
                    "MATCH (n:Network {id: $n_id}), (d:Device {id: $d_id}) "
                    "MERGE (d)-[:IN_NETWORK]->(n)"
                ),
                params={"n_id": doc.network_id, "d_id": node["id"]},
            )
        )

    # 5. Merge LINKED_TO edges
    for link in doc.links:
        stmts.append(
            CypherStatement(
                query=(
                    "MERGE (d1:Device {id: $d1_id})-[:LINKED_TO "
                    "{sourcePort: $source_port, targetPort: $target_port}]->"
                    "(d2:Device {id: $d2_id})"
                ),
                params={
                    "d1_id": link["source"],
                    "d2_id": link["target"],
                    "source_port": link.get("sourcePort"),
                    "target_port": link.get("targetPort"),
                },
            )
        )

    # 6. Detach-delete orphaned devices (those with no IN_NETWORK edge left)
    stmts.append(
        CypherStatement(
            query=(
                "MATCH (d:Device) WHERE NOT (d)-[:IN_NETWORK]->() "
                "DETACH DELETE d"
            ),
        )
    )

    return stmts
