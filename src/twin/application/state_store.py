"""Raw Elasticsearch document shapes used by the StateStore port.

These are not domain entities; they carry the ``@timestamp`` as ``as_of``
and are composed into domain entities by ``twin.application.state_projector``.
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


@dataclass
class UplinkDocument:
    """Raw ES document from ``meraki-uplink-metrics`` (doc id ``serial-interface``)."""
    serial: str
    interface: str
    network_id: str | None
    network_name: str | None
    public_ip: str | None  # publicIp
    ip: str | None
    gateway: str | None
    addressing: str | None
    status: str | None
    enabled: bool | None
    primary: bool | None
    dns: str | None
    as_of: str  # ISO-8601 @timestamp


@dataclass
class SwitchportDocument:
    """Raw ES document from ``meraki-switchport-metrics`` (doc id ``serial-portId``)."""
    serial: str
    port_id: str
    network_id: str | None
    status: str | None  # Connected|Disconnected
    speed: str | None
    duplex: str | None
    enabled: bool | None
    errors: int | None
    client_count: int | None  # clientCount
    as_of: str  # ISO-8601 @timestamp


@dataclass
class VlanDocument:
    """Raw ES document from ``meraki-vlan-metrics`` (doc id ``network_id-vlan_id``)."""
    network_id: str
    vlan_id: str
    name: str | None
    subnet: str | None
    appliance_ip: str | None  # applianceIp
    dhcp_handling: str | None  # dhcpHandling
    enabled: bool | None
    network_name: str | None
    as_of: str  # ISO-8601 @timestamp


@dataclass
class TopologyDocument:
    """Raw ES document from ``meraki-topology-metrics`` (doc id ``network_id``)."""
    network_id: str
    network_name: str | None
    node_count: int
    link_count: int
    offline_nodes: list[dict]
    nodes: list[dict]
    links: list[dict]
    as_of: str  # ISO-8601 @timestamp


@dataclass
class ClientDocument:
    """Raw ES document from ``meraki-client-metrics`` (doc id ``mac``)."""
    mac: str
    network_id: str | None
    serial: str | None
    ip: str | None
    ip6: str | None
    description: str | None
    user: str | None
    vlan: str | None
    switchport: str | None
    ssid: str | None
    status: str | None
    last_seen: str | None  # lastSeen
    as_of: str  # ISO-8601 @timestamp


@dataclass
class EventDocument:
    """Raw ES document from the ``meraki-syslog-*`` stream (append-only)."""
    timestamp: str  # ISO-8601 @timestamp
    message: str  # the raw syslog message line
    device: str | None  # reporting syslog host
    network_id: str | None  # present only when a parser has populated it
    raw: dict  # full source document


@dataclass
class ChangeDocument:
    """Raw ES document from the day-partitioned ``*-history-*`` changelog indices."""
    timestamp: str  # ISO-8601 @timestamp
    index: str  # the concrete history index the doc was read from
    entity_type: str  # derived from the history index name
    entity_id: str  # serial, network id, or combined key
    network_id: str | None
    serial: str | None
    previous: dict  # history.previous
    current: dict  # current top-level values
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

    async def list_uplink_documents(
        self,
        network_id: str | None = None,
        serial: str | None = None,
    ) -> list[UplinkDocument]: ...

    async def get_uplink_document(
        self, serial: str, interface: str
    ) -> UplinkDocument | None: ...

    async def list_switchport_documents(
        self,
        network_id: str | None = None,
        serial: str | None = None,
    ) -> list[SwitchportDocument]: ...

    async def get_switchport_document(
        self, serial: str, port_id: str
    ) -> SwitchportDocument | None: ...

    async def list_vlan_documents(
        self, network_id: str | None = None
    ) -> list[VlanDocument]: ...

    async def get_vlan_document(
        self, network_id: str, vlan_id: str
    ) -> VlanDocument | None: ...

    async def list_topology_documents(self) -> list[TopologyDocument]: ...

    async def get_topology_document(self, network_id: str) -> TopologyDocument | None: ...

    async def list_client_documents(
        self,
        network_id: str | None = None,
        switchport: str | None = None,
        ip: str | None = None,
        vlan: str | None = None,
        user: str | None = None,
    ) -> list[ClientDocument]: ...

    async def get_client_document(self, mac: str) -> ClientDocument | None: ...

    async def search_event_documents(  # noqa: PLR0913, PLR0917
        self,
        start: str | None = None,
        end: str | None = None,
        q: str | None = None,
        device: str | None = None,
        network_id: str | None = None,
        limit: int = 100,
    ) -> list[EventDocument]: ...

    async def list_change_documents(
        self,
        device: str | None = None,
        network_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[ChangeDocument]: ...
