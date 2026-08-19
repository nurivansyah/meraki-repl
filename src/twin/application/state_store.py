"""Raw Elasticsearch document shapes used by the StateStore port.

These are not domain entities; they carry the ``@timestamp`` as ``as_of``
and are composed into ``Network`` / ``Device`` by the ``StateProjector``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class NetworkDocument:
    """Raw ES document from ``meraki-network-metrics``."""
    id: str
    name: str
    time_zone: str | None
    tags: list[str] | None
    product_types: list[str] | None
    meraki_org_id: str
    network_id: str
    as_of: str  # ISO-8601 @timestamp


@dataclass
class DeviceInventoryDocument:
    """Raw ES document from ``meraki-device-inventory``."""
    serial: str
    name: str | None
    model: str | None
    mac: str | None
    network_id: str | None
    product_type: str | None
    firmware: str | None
    lan_ip: str | None  # lanIp
    wan_ip: str | None  # wan1Ip
    as_of: str  # ISO-8601 @timestamp


@dataclass
class DeviceMetricsDocument:
    """Raw ES document from ``meraki-device-metrics``."""
    serial: str
    name: str | None
    status: str | None  # online|offline|alerting|dormant
    network_id: str
    as_of: str  # ISO-8601 @timestamp

"""Port for the state mirror — interfaces the application depends on."""


class StateStore(Protocol):
    """Storage boundary for Meraki state projections."""

    async def list_network_documents(self) -> list[NetworkDocument]: ...

    async def get_network_document(self, network_id: str) -> NetworkDocument | None: ...

    async def list_device_inventory_documents(
        self,
        network_id: str | None = None,
        product_type: str | None = None,
    ) -> list[DeviceInventoryDocument]: ...

    async def list_device_metrics_documents(
        self,
        network_id: str | None = None,
        status: str | None = None,
    ) -> list[DeviceMetricsDocument]: ...

    async def get_device_inventory_document(
        self, serial: str
    ) -> DeviceInventoryDocument | None: ...

    async def get_device_metrics_document(self, serial: str) -> DeviceMetricsDocument | None: ...
