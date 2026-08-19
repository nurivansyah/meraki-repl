"""Elasticsearch-backed StateStore implementing the ``StateStore`` protocol.

Uses the existing ``AsyncElasticsearch`` client (injected at the repository
boundary via ``get_es_client()``).  Queries issue term / match-all DSL against
the three Meraki indices.

The ``meraki_org_id`` filter is always appended server-side so that the twin
never crosses organisation boundaries.
"""

from __future__ import annotations

from typing import Any

from twin.application.state_store import (
    ClientDocument,
    DeviceInventoryDocument,
    DeviceMetricsDocument,
    NetworkDocument,
    SwitchportDocument,
    TopologyDocument,
    UplinkDocument,
    VlanDocument,
)
from twin.config import settings


def _org_filter() -> dict[str, Any]:
    """Return a constant_score query wrapping the configured org id."""
    return {
        "constant_score": {
            "filter": {"term": {"meraki_org_id": settings.meraki_org_id}}
        }
    }


def _term_filters(terms: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a list of ``term`` filter clauses from non-empty field values."""
    return [{"term": {field: value}} for field, value in terms.items() if value]


class ElasticsearchStateStore:
    """Concrete ``StateStore`` over an ``AsyncElasticsearch`` client."""

    def __init__(self, es_client: Any) -> None:
        self._es = es_client

    # ------------------------------------------------------------------
    # Networks
    # ------------------------------------------------------------------

    async def list_network_documents(self) -> list[NetworkDocument]:
        """Return every network document scoped to the current org."""
        resp = await self._es.search(
            index="meraki-network-metrics",
            body={"query": {"bool": {"filter": [_org_filter()]}}},
            size=10000,
        )
        hits = resp.get("hits", {}).get("hits", [])
        return [
            NetworkDocument(
                id=hit["_id"],
                name=hit["_source"].get("name", ""),
                time_zone=hit["_source"].get("timeZone"),
                tags=hit["_source"].get("tags"),
                product_types=hit["_source"].get("productTypes"),
                meraki_org_id=hit["_source"].get("meraki_org_id", ""),
                network_id=hit["_source"].get("network_id", ""),
                as_of=hit["_source"].get("@timestamp", ""),
            )
            for hit in hits
        ]

    async def get_network_document(self, network_id: str) -> NetworkDocument | None:
        resp = await self._es.get(index="meraki-network-metrics", id=network_id)
        if not resp.get("found"):
            return None
        src = resp.get("_source", {})
        return NetworkDocument(
            id=resp["_id"],
            name=src.get("name", ""),
            time_zone=src.get("timeZone"),
            tags=src.get("tags"),
            product_types=src.get("productTypes"),
            meraki_org_id=src.get("meraki_org_id", ""),
            network_id=src.get("network_id", ""),
            as_of=src.get("@timestamp", ""),
        )

    # ------------------------------------------------------------------
    # Device inventory
    # ------------------------------------------------------------------

    async def _inventory_query(
        self,
        network_id: str | None = None,
        product_type: str | None = None,
    ) -> dict[str, Any]:
        """Build the ``bool`` query for ``meraki-device-inventory``."""
        filters: list[dict[str, Any]] = []
        if network_id:
            filters.append({"term": {"network_id": network_id}})
        if product_type:
            filters.append({"term": {"product_type": product_type}})
        org = _org_filter()
        # Always AND the org filter with user filters.
        bool_query: dict[str, Any] = {"bool": {"filter": [org, *filters]}}
        return {"query": bool_query}

    async def list_device_inventory_documents(
        self,
        network_id: str | None = None,
        product_type: str | None = None,
    ) -> list[DeviceInventoryDocument]:
        query = await self._inventory_query(network_id, product_type)
        resp = await self._es.search(
            index="meraki-device-inventory",
            body=query,
            size=10000,
        )
        hits = resp.get("hits", {}).get("hits", [])
        return [
            DeviceInventoryDocument(
                serial=hit["_id"],
                name=hit["_source"].get("name"),
                model=hit["_source"].get("model"),
                mac=hit["_source"].get("mac"),
                network_id=hit["_source"].get("network_id"),
                product_type=hit["_source"].get("product_type"),
                firmware=hit["_source"].get("firmware"),
                lan_ip=hit["_source"].get("lanIp"),
                wan_ip=hit["_source"].get("wan1Ip"),
                as_of=hit["_source"].get("@timestamp", ""),
            )
            for hit in hits
        ]

    # ------------------------------------------------------------------
    # Device metrics
    # ------------------------------------------------------------------

    async def _metrics_query(
        self,
        network_id: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Build the ``bool`` query for ``meraki-device-metrics``."""
        filters: list[dict[str, Any]] = []
        if network_id:
            filters.append({"term": {"network_id": network_id}})
        if status:
            filters.append({"term": {"status": status}})
        org = _org_filter()
        bool_query: dict[str, Any] = {"bool": {"filter": [org, *filters]}}
        return {"query": bool_query}

    async def list_device_metrics_documents(
        self,
        network_id: str | None = None,
        status: str | None = None,
    ) -> list[DeviceMetricsDocument]:
        query = await self._metrics_query(network_id, status)
        resp = await self._es.search(
            index="meraki-device-metrics",
            body=query,
            size=10000,
        )
        hits = resp.get("hits", {}).get("hits", [])
        return [
            DeviceMetricsDocument(
                serial=hit["_id"],
                name=hit["_source"].get("name"),
                status=hit["_source"].get("status"),
                network_id=hit["_source"].get("network_id"),
                as_of=hit["_source"].get("@timestamp", ""),
            )
            for hit in hits
        ]

    # ------------------------------------------------------------------
    # Per-serial lookups
    # ------------------------------------------------------------------

    async def get_device_inventory_document(self, serial: str) -> DeviceInventoryDocument | None:
        resp = await self._es.get(index="meraki-device-inventory", id=serial)
        if not resp.get("found"):
            return None
        src = resp.get("_source", {})
        return DeviceInventoryDocument(
            serial=resp["_id"],
            name=src.get("name"),
            model=src.get("model"),
            mac=src.get("mac"),
            network_id=src.get("network_id"),
            product_type=src.get("product_type"),
            firmware=src.get("firmware"),
            lan_ip=src.get("lanIp"),
            wan_ip=src.get("wan1Ip"),
            as_of=src.get("@timestamp", ""),
        )

    async def get_device_metrics_document(self, serial: str) -> DeviceMetricsDocument | None:
        resp = await self._es.get(index="meraki-device-metrics", id=serial)
        if not resp.get("found"):
            return None
        src = resp.get("_source", {})
        return DeviceMetricsDocument(
            serial=resp["_id"],
            name=src.get("name"),
            status=src.get("status"),
            network_id=src.get("network_id"),
            as_of=src.get("@timestamp", ""),
        )

    # ------------------------------------------------------------------
    # Uplinks
    # ------------------------------------------------------------------

    async def list_uplink_documents(
        self,
        network_id: str | None = None,
        serial: str | None = None,
    ) -> list[UplinkDocument]:
        query = _term_filters({"network_id": network_id, "serial": serial})
        resp = await self._es.search(
            index="meraki-uplink-metrics",
            body={"query": {"bool": {"filter": [_org_filter(), *query]}}},
            size=10000,
        )
        hits = resp.get("hits", {}).get("hits", [])
        return [
            UplinkDocument(
                serial=hit["_source"].get("serial", hit["_id"].split("-", 1)[0]),
                interface=hit["_source"].get("interface", ""),
                network_id=hit["_source"].get("network_id"),
                network_name=hit["_source"].get("network_name"),
                public_ip=hit["_source"].get("publicIp"),
                ip=hit["_source"].get("ip"),
                gateway=hit["_source"].get("gateway"),
                addressing=hit["_source"].get("addressing"),
                status=hit["_source"].get("status"),
                enabled=hit["_source"].get("enabled"),
                primary=hit["_source"].get("primary"),
                dns=hit["_source"].get("dns"),
                as_of=hit["_source"].get("@timestamp", ""),
            )
            for hit in hits
        ]

    async def get_uplink_document(
        self, serial: str, interface: str
    ) -> UplinkDocument | None:
        resp = await self._es.get(index="meraki-uplink-metrics", id=f"{serial}-{interface}")
        if not resp.get("found"):
            return None
        src = resp.get("_source", {})
        return UplinkDocument(
            serial=src.get("serial", serial),
            interface=src.get("interface", interface),
            network_id=src.get("network_id"),
            network_name=src.get("network_name"),
            public_ip=src.get("publicIp"),
            ip=src.get("ip"),
            gateway=src.get("gateway"),
            addressing=src.get("addressing"),
            status=src.get("status"),
            enabled=src.get("enabled"),
            primary=src.get("primary"),
            dns=src.get("dns"),
            as_of=src.get("@timestamp", ""),
        )

    # ------------------------------------------------------------------
    # Switchports
    # ------------------------------------------------------------------

    async def list_switchport_documents(
        self,
        network_id: str | None = None,
        serial: str | None = None,
    ) -> list[SwitchportDocument]:
        query = _term_filters({"network_id": network_id, "serial": serial})
        resp = await self._es.search(
            index="meraki-switchport-metrics",
            body={"query": {"bool": {"filter": [_org_filter(), *query]}}},
            size=10000,
        )
        hits = resp.get("hits", {}).get("hits", [])
        return [
            SwitchportDocument(
                serial=hit["_source"].get("serial", ""),
                port_id=hit["_source"].get("portId", ""),
                network_id=hit["_source"].get("network_id"),
                status=hit["_source"].get("status"),
                speed=hit["_source"].get("speed"),
                duplex=hit["_source"].get("duplex"),
                enabled=hit["_source"].get("enabled"),
                errors=hit["_source"].get("errors"),
                client_count=hit["_source"].get("clientCount"),
                as_of=hit["_source"].get("@timestamp", ""),
            )
            for hit in hits
        ]

    async def get_switchport_document(
        self, serial: str, port_id: str
    ) -> SwitchportDocument | None:
        resp = await self._es.get(index="meraki-switchport-metrics", id=f"{serial}-{port_id}")
        if not resp.get("found"):
            return None
        src = resp.get("_source", {})
        return SwitchportDocument(
            serial=src.get("serial", serial),
            port_id=src.get("portId", port_id),
            network_id=src.get("network_id"),
            status=src.get("status"),
            speed=src.get("speed"),
            duplex=src.get("duplex"),
            enabled=src.get("enabled"),
            errors=src.get("errors"),
            client_count=src.get("clientCount"),
            as_of=src.get("@timestamp", ""),
        )

    # ------------------------------------------------------------------
    # VLANs
    # ------------------------------------------------------------------

    async def list_vlan_documents(
        self, network_id: str | None = None
    ) -> list[VlanDocument]:
        query = _term_filters({"network_id": network_id})
        resp = await self._es.search(
            index="meraki-vlan-metrics",
            body={"query": {"bool": {"filter": [_org_filter(), *query]}}},
            size=10000,
        )
        hits = resp.get("hits", {}).get("hits", [])
        return [
            VlanDocument(
                network_id=hit["_source"].get("network_id", ""),
                vlan_id=hit["_source"].get("vlan_id", ""),
                name=hit["_source"].get("name"),
                subnet=hit["_source"].get("subnet"),
                appliance_ip=hit["_source"].get("applianceIp"),
                dhcp_handling=hit["_source"].get("dhcpHandling"),
                enabled=hit["_source"].get("enabled"),
                network_name=hit["_source"].get("network_name"),
                as_of=hit["_source"].get("@timestamp", ""),
            )
            for hit in hits
        ]

    async def get_vlan_document(
        self, network_id: str, vlan_id: str
    ) -> VlanDocument | None:
        resp = await self._es.get(index="meraki-vlan-metrics", id=f"{network_id}-{vlan_id}")
        if not resp.get("found"):
            return None
        src = resp.get("_source", {})
        return VlanDocument(
            network_id=src.get("network_id", network_id),
            vlan_id=src.get("vlan_id", vlan_id),
            name=src.get("name"),
            subnet=src.get("subnet"),
            appliance_ip=src.get("applianceIp"),
            dhcp_handling=src.get("dhcpHandling"),
            enabled=src.get("enabled"),
            network_name=src.get("network_name"),
            as_of=src.get("@timestamp", ""),
        )

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    async def list_topology_documents(self) -> list[TopologyDocument]:
        resp = await self._es.search(
            index="meraki-topology-metrics",
            body={"query": {"bool": {"filter": [_org_filter()]}}},
            size=10000,
        )
        hits = resp.get("hits", {}).get("hits", [])
        return [self._topology_from_doc(hit) for hit in hits]

    async def get_topology_document(self, network_id: str) -> TopologyDocument | None:
        resp = await self._es.get(index="meraki-topology-metrics", id=network_id)
        if not resp.get("found"):
            return None
        return self._topology_from_doc(resp)

    @staticmethod
    def _topology_from_doc(doc: dict) -> TopologyDocument:
        src = doc.get("_source", {})
        topology = src.get("topology") or {}
        return TopologyDocument(
            network_id=src.get("network_id", doc["_id"]),
            network_name=src.get("name"),
            node_count=src.get("node_count", len(topology.get("nodes") or [])),
            link_count=src.get("link_count", len(topology.get("links") or [])),
            offline_nodes=src.get("offline_nodes") or [],
            nodes=topology.get("nodes") or [],
            links=topology.get("links") or [],
            as_of=src.get("@timestamp", ""),
        )

    # ------------------------------------------------------------------
    # Clients
    # ------------------------------------------------------------------

    async def list_client_documents(
        self,
        network_id: str | None = None,
        switchport: str | None = None,
        ip: str | None = None,
        vlan: str | None = None,
        user: str | None = None,
    ) -> list[ClientDocument]:
        query = _term_filters(
            {
                "network_id": network_id,
                "switchport": switchport,
                "ip": ip,
                "vlan": vlan,
                "user": user,
            }
        )
        resp = await self._es.search(
            index="meraki-client-metrics",
            body={"query": {"bool": {"filter": [_org_filter(), *query]}}},
            size=10000,
        )
        hits = resp.get("hits", {}).get("hits", [])
        return [self._client_from_doc(hit) for hit in hits]

    async def get_client_document(self, mac: str) -> ClientDocument | None:
        resp = await self._es.get(index="meraki-client-metrics", id=mac)
        if not resp.get("found"):
            return None
        return self._client_from_doc(resp)

    @staticmethod
    def _client_from_doc(doc: dict) -> ClientDocument:
        src = doc.get("_source", {})
        return ClientDocument(
            mac=src.get("mac", doc["_id"]),
            network_id=src.get("network_id"),
            serial=src.get("serial"),
            ip=src.get("ip"),
            ip6=src.get("ip6"),
            description=src.get("description"),
            user=src.get("user"),
            vlan=src.get("vlan"),
            switchport=src.get("switchport"),
            ssid=src.get("ssid"),
            status=src.get("status"),
            last_seen=src.get("lastSeen"),
            as_of=src.get("@timestamp", ""),
        )
