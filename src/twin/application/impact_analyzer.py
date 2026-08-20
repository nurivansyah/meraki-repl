"""ImpactAnalyzer — reachability analysis against the Neo4j graph.

The analyzer walks ``LINKED_TO`` edges from a seed device (or uplink port)
and partitions the reachable set into devices that are reachable (online)
and devices that are masked (down/offline).
"""

from __future__ import annotations

from twin.application.ports import CypherStatement, GraphPort
from twin.domain.graph import ImpactedDevice, ImpactResult


class ImpactAnalyzer:
    """Read-only graph analysis: walk from a seed, mask down/offline devices."""

    def __init__(self, graph: GraphPort, default_depth: int = 10) -> None:
        self._graph = graph
        self._default_depth = default_depth

    async def impact_from_device(
        self,
        serial: str,
        *,
        depth: int | None = None,
    ) -> ImpactResult | None:
        """Return the reachable set from a device serial, or ``None`` if the
        seed device does not exist in the graph.
        """
        depth_val = depth or self._default_depth
        impact_rows = await self._graph.execute(
            [self._impact_cypher(serial, depth=depth_val)]
        )
        if not impact_rows:
            return None
        # Fetch the freshness marker from the Network node
        as_of_rows = await self._graph.execute(
            [
                CypherStatement(
                    query=(
                        "MATCH (d:Device {id: $seed_id})-[:IN_NETWORK]->(n:Network) "
                        "RETURN n.last_synced_at AS as_of"
                    ),
                    params={"seed_id": serial},
                )
            ]
        )
        as_of = _as_of_to_iso(as_of_rows)
        return self._build_result(seed_id=serial, rows=impact_rows, as_of=as_of)

    async def impact_from_uplink(
        self,
        serial: str,
        interface: str,
        *,
        depth: int | None = None,
    ) -> ImpactResult | None:
        """Return the reachable set seeded by an uplink port.

        First finds the neighbor connected to ``serial`` on ``interface``,
        then walks from that neighbor.
        """
        depth_val = depth or self._default_depth
        # Step 1: find the neighbor across the port
        find_neighbor = CypherStatement(
            query=(
                "MATCH (seed:Device {id: $seed_id})-[e:LINKED_TO]-(peer:Device) "
                "WHERE e.sourcePort = $interface OR e.targetPort = $interface "
                "RETURN peer.id AS neighbor_id"
            ),
            params={"seed_id": serial, "interface": interface},
        )
        rows = await self._graph.execute([find_neighbor])
        if not rows:
            return None
        neighbor_id = rows[0]["neighbor_id"]

        # Step 2: walk from the neighbor (same as device walk)
        walk = self._impact_cypher(neighbor_id, depth=depth_val)
        walk_rows = await self._graph.execute([walk])
        if not walk_rows:
            return None
        # Fetch freshness from the Network node
        as_of_rows = await self._graph.execute(
            [
                CypherStatement(
                    query=(
                        "MATCH (d:Device {id: $seed_id})-[:IN_NETWORK]->(n:Network) "
                        "RETURN n.last_synced_at AS as_of"
                    ),
                    params={"seed_id": neighbor_id},
                )
            ]
        )
        as_of = _as_of_to_iso(as_of_rows)
        return self._build_result(
            seed_id=f"{serial}:{interface}", rows=walk_rows, as_of=as_of
        )

    def _impact_cypher(self, seed_id: str, *, depth: int) -> CypherStatement:
        """Build a Cypher statement that walks from a seed device.

        The statement pattern matches what ``FakeGraphStore._impact_walk``
        interprets and what the real Neo4j adapter will run.
        """
        return CypherStatement(
            query=(
                "MATCH (seed:Device {id: $seed_id}) "
                f"MATCH (seed)-[:LINKED_TO*1..{depth}]-(neighbor:Device) "
                "WHERE NOT (neighbor)<-[:LINKED_TO]-(seed) "
                "OPTIONAL MATCH (n:Network)<-[:IN_NETWORK]-(neighbor) "
                "RETURN neighbor.id AS id, neighbor.name AS name, "
                "neighbor.status AS status, n.id AS network_id, "
                "neighbor.status IN ['down','offline'] AS masked"
            ),
            params={"seed_id": seed_id, "depth": depth},
        )

    @staticmethod
    def _build_result(
        seed_id: str,
        rows: list[dict],
        *,
        as_of: str = "",
    ) -> ImpactResult:
        reachable: list[ImpactedDevice] = []
        masked: list[ImpactedDevice] = []
        for row in rows:
            dev = ImpactedDevice(
                id=row["id"],
                name=row.get("name"),
                status=row.get("status"),
                network_id=row.get("network_id"),
            )
            if row.get("masked"):
                masked.append(dev)
            else:
                reachable.append(dev)
        return ImpactResult(
            seed_id=seed_id,
            reachable=reachable,
            masked=masked,
            as_of=as_of,
        )


def _as_of_to_iso(rows: list[dict]) -> str:
    """Extract the ``as_of`` value from query results and normalize to ISO-8601 ``Z``."""
    if not rows or not rows[0].get("as_of"):
        return ""
    raw = rows[0]["as_of"]
    iso = raw.isoformat() if hasattr(raw, "isoformat") else str(raw)
    # Normalize timezone suffix to Z for consistency with ES.
    return iso.replace("+00:00", "Z").replace("+00:00:00", "Z")
