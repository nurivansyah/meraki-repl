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
    DeviceInventoryDocument,
    DeviceMetricsDocument,
    NetworkDocument,
)
from twin.config import settings


def _org_filter() -> dict[str, Any]:
    """Return a constant_score query wrapping the configured org id."""
    return {
        "constant_score": {
            "filter": {"term": {"meraki_org_id": settings.meraki_org_id}}
        }
    }


class ElasticsearchStateStore:
    """Concrete ``StateStore`` over an ``AsyncElasticsearch`` client."""

    def __init__(self, es_client: Any) -> None:
        self._es = es_client

    # ------------------------------------------------------------------
    # Networks
    # ------------------------------------------------------------------

    async def list_network_documents(self) -> list[NetworkDocument]:
        """Return every network document (match-all)."""
        resp = await self._es.search(
            index="meraki-network-metrics",
            body={"query": {"match_all": {}}, "size": 10000},
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
