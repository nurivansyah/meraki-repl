"""In-memory fake for the GraphPort, scoped to the patterns emitted by the
transform and analyzer.
"""

from __future__ import annotations

from datetime import datetime

from twin.application.ports import CypherStatement


class FakeGraphStore:
    """Minimal in-memory graph store for testing."""

    def __init__(self) -> None:
        # {label: {id: {field: value}}}
        self.nodes: dict[str, dict[str, dict]] = {}
        self.edges: list[dict] = []

    async def execute(self, statements: list[CypherStatement]) -> list[dict]:
        results: list[dict] = []
        for stmt in statements:
            results.extend(self._apply(stmt.query, stmt.params))
        return results

    def _apply(self, query: str, params: dict) -> list[dict]:  # noqa: PLR0911, PLR0912, PLR0915
        q = " ".join(query.split()).strip()

        # Device: RETURN n.last_synced_at via IN_NETWORK
        if "RETURN n.last_synced_at AS as_of" in q:
            did = params.get("seed_id", "")
            dev = self.nodes.get("Device", {}).get(did, {})
            nid = dev.get("network_id")
            net = self.nodes.get("Network", {}).get(nid, {}) if nid else {}
            return [{"as_of": net.get("last_synced_at")}]

        # Network: RETURN last_synced_at
        if "RETURN n.last_synced_at" in q:
            nid = params.get("id", "")
            net = self.nodes.get("Network", {}).get(nid)
            return [{"last_synced_at": net.get("last_synced_at") if net else None}]

        # Network: MERGE + SET name, last_synced_at
        if "MERGE (n:Network" in q and "SET n.name" in q:
            nid = params["id"]
            nets = self.nodes.setdefault("Network", {})
            net = nets.get(nid, {})
            net["id"] = nid
            net["name"] = params.get("name", net.get("name"))
            last = params.get("last_synced_at")
            if last is not None:
                net["last_synced_at"] = (
                    datetime.fromisoformat(last) if isinstance(last, str) else last
                )
            nets[nid] = net
            return []

        # Network: delete IN_NETWORK relationships
        if "DELETE r" in q and "IN_NETWORK" in q:
            nid = params.get("id", "")
            self.edges = [
                e
                for e in self.edges
                if not (
                    e["label"] == "IN_NETWORK"
                    and e["end_node"] == nid
                    and e["end_label"] == "Network"
                )
            ]
            return []

        # Device: DETACH DELETE orphan (no IN_NETWORK left)
        if "DETACH DELETE d" in q:
            did = params.get("id", "")
            has_network = any(
                e["label"] == "IN_NETWORK"
                and e["start_node"] == did
                and e["start_label"] == "Device"
                for e in self.edges
            )
            if not has_network:
                self.nodes.get("Device", {}).pop(did, None)
                self.edges = [
                    e
                    for e in self.edges
                    if not (
                        e["start_label"] == "Device" and e["start_node"] == did
                    )
                    and not (
                        e["end_label"] == "Device" and e["end_node"] == did
                    )
                ]
            return []

        # Device: MERGE + SET name/status/product_type
        if "MERGE (d:Device" in q and "SET d.name" in q:
            did = params["id"]
            devs = self.nodes.setdefault("Device", {})
            dev = devs.get(did, {})
            dev["id"] = did
            dev["name"] = params.get("name", dev.get("name"))
            dev["status"] = params.get("status", dev.get("status"))
            dev["product_type"] = params.get("product_type", dev.get("product_type"))
            dev["network_id"] = params.get("network_id", dev.get("network_id"))
            devs[did] = dev
            return []

        # Device: MERGE name/status/product_type without network_id
        if "MERGE (d:Device" in q and "SET d.name" in q:
            did = params["id"]
            devs = self.nodes.setdefault("Device", {})
            dev = devs.get(did, {})
            dev["id"] = did
            dev["name"] = params.get("name", dev.get("name"))
            dev["status"] = params.get("status", dev.get("status"))
            dev["product_type"] = params.get("product_type", dev.get("product_type"))
            devs[did] = dev
            return []

        # IN_NETWORK relationship
        if "MERGE (d)-[:IN_NETWORK]->(n)" in q:
            self.edges.append(
                {
                    "start_label": "Device",
                    "start_node": params["d_id"],
                    "label": "IN_NETWORK",
                    "end_label": "Network",
                    "end_node": params["n_id"],
                }
            )
            return []

        # LINKED_TO relationship
        if "LINKED_TO" in q and "MERGE" in q:
            self.edges.append(
                {
                    "start_label": "Device",
                    "start_node": params["d1_id"],
                    "label": "LINKED_TO",
                    "end_label": "Device",
                    "end_node": params["d2_id"],
                    "props": {
                        "sourcePort": params.get("source_port"),
                        "targetPort": params.get("target_port"),
                    },
                }
            )
            return []

        # Impact: MATCH where LINKED_TO then walk — handle both device and uplink
        if "LINKED_TO" in q and "RETURN" in q:
            # Uplink: find neighbor across a specific port
            if "peer.id AS neighbor_id" in q:
                return self._find_neighbor(params)
            return self._impact_walk(params)

        # Cleanup: all remaining — no-op for the fake
        return []

    def _find_neighbor(self, params: dict) -> list[dict]:
        """Find the peer device connected to seed_id via a matching port."""
        seed_id = params.get("seed_id", "")
        interface = params.get("interface", "")
        for e in self.edges:
            if e["label"] != "LINKED_TO":
                continue
            props = e.get("props", {})
            source_port = props.get("sourcePort")
            target_port = props.get("targetPort")
            if e["start_node"] == seed_id and source_port == interface:
                return [{"neighbor_id": e["end_node"]}]
            if e["end_node"] == seed_id and target_port == interface:
                return [{"neighbor_id": e["start_node"]}]
        return []

    def _impact_walk(self, params: dict) -> list[dict]:
        """Walk LINKED_TO edges from a seed device and return the reachable
        and masked device rows, applying the depth limit from the query."""
        seed = params.get("seed_id", "")
        depth = params.get("depth", 10)
        devices = self.nodes.get("Device", {})

        # Seed exists?
        seed_dev = devices.get(seed)
        if seed_dev is None:
            return []

        # BFS from seed up to depth hops
        visited: set[str] = {seed}
        frontier = {seed}
        all_reachable: list[str] = []
        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                for e in self.edges:
                    if e["label"] != "LINKED_TO":
                        continue
                    neighbor = None
                    if e["start_node"] == node:
                        neighbor = e["end_node"]
                    elif e["end_node"] == node:
                        neighbor = e["start_node"]
                    if neighbor and neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.add(neighbor)
                        all_reachable.append(neighbor)
            frontier = next_frontier
            if not frontier:
                break

        # Filter masked (down/offline) and collect reachable
        masked = []
        reachable = []
        for did in all_reachable:
            dev = devices.get(did, {})
            status = dev.get("status", "")
            is_masked = status in ("down", "offline")
            row = {
                "id": did,
                "name": dev.get("name"),
                "status": status,
                "network_id": dev.get("network_id"),
                "masked": is_masked,
            }
            if is_masked:
                masked.append(row)
            else:
                reachable.append(row)

        return reachable + masked
