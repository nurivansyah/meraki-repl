"""Read core service — the single projection + join path every surface uses.

REST, MCP and dashboard views are thin adapters over this service.  It owns
the cross-index joins (network name onto devices, switchports, clients) and
the device inventory/metrics merge, so no surface re-implements them.
"""

from __future__ import annotations

from twin.application.impact_analyzer import ImpactAnalyzer
from twin.application.state_projector import (
    project_change,
    project_client,
    project_device,
    project_devices,
    project_event,
    project_network,
    project_switchport,
    project_topology,
    project_uplink,
    project_vlan,
)
from twin.application.state_store import NetworkDocument, StateStore
from twin.domain.changes import Change
from twin.domain.clients import Client
from twin.domain.devices import Device
from twin.domain.events import Event
from twin.domain.graph import ImpactResult
from twin.domain.networks import Network
from twin.domain.switchports import Switchport
from twin.domain.topology import Topology
from twin.domain.uplinks import Uplink
from twin.domain.vlans import Vlan

MIN_LIMIT = 1
MAX_LIMIT = 1000


class GraphUnavailableError(Exception):
    """Raised when the graph store is not available for impact analysis."""


def _bounded(limit: int) -> int:
    """Clamp a result limit to the supported range."""
    return max(MIN_LIMIT, min(limit, MAX_LIMIT))


class ReadMirror:
    """Application service composing the ``StateStore`` and projectors."""

    def __init__(self, store: StateStore, impact_analyzer: ImpactAnalyzer | None = None) -> None:
        self._store = store
        self._impact_analyzer = impact_analyzer

    async def _network_map(self) -> dict[str, NetworkDocument]:
        return {d.id: d for d in await self._store.list_network_documents()}

    async def list_networks(self) -> list[Network]:
        """Return every network in the current organisation."""
        return [project_network(d) for d in await self._store.list_network_documents()]

    async def get_network(self, network_id: str) -> Network | None:
        """Return a single network by its id, or ``None`` when absent."""
        doc = await self._store.get_network_document(network_id)
        return project_network(doc) if doc else None

    async def list_devices(
        self,
        network_id: str | None = None,
        product_type: str | None = None,
        status: str | None = None,
    ) -> list[Device]:
        """List devices, merging inventory and metrics for each serial.

        A status filter makes metrics the defining side; a product-type filter
        makes inventory the defining side; otherwise the full union is used.
        """
        inventory = await self._store.list_device_inventory_documents(network_id, product_type)
        metrics = await self._store.list_device_metrics_documents(network_id, status)
        network_map = await self._network_map()
        primary = "metrics" if status else ("inventory" if product_type else None)
        return project_devices(inventory, metrics, network_map, primary)

    async def get_device(self, serial: str) -> Device | None:
        """Return a single device by its serial number, or ``None`` when absent."""
        inv = await self._store.get_device_inventory_document(serial)
        met = await self._store.get_device_metrics_document(serial)
        if inv is None and met is None:
            return None
        return project_device(inv, met, await self._network_map())

    async def list_uplinks(
        self,
        network_id: str | None = None,
        serial: str | None = None,
    ) -> list[Uplink]:
        """List uplinks, optionally filtered by network id or device serial."""
        docs = await self._store.list_uplink_documents(network_id, serial)
        return [project_uplink(d) for d in docs]

    async def get_uplink(self, serial: str, interface: str) -> Uplink | None:
        """Return a single uplink by device serial and interface, or ``None``."""
        doc = await self._store.get_uplink_document(serial, interface)
        return project_uplink(doc) if doc else None

    async def list_switchports(
        self,
        network_id: str | None = None,
        serial: str | None = None,
    ) -> list[Switchport]:
        """List switchports, optionally filtered by network id or device serial."""
        docs = await self._store.list_switchport_documents(network_id, serial)
        network_map = await self._network_map()
        return [project_switchport(d, network_map) for d in docs]

    async def get_switchport(self, serial: str, port_id: str) -> Switchport | None:
        """Return a single switchport by device serial and port id, or ``None``."""
        doc = await self._store.get_switchport_document(serial, port_id)
        if doc is None:
            return None
        return project_switchport(doc, await self._network_map())

    async def list_vlans(self, network_id: str | None = None) -> list[Vlan]:
        """List VLANs, optionally filtered by network id."""
        docs = await self._store.list_vlan_documents(network_id)
        return [project_vlan(d) for d in docs]

    async def get_vlan(self, network_id: str, vlan_id: str) -> Vlan | None:
        """Return a single VLAN by network id and vlan id, or ``None``."""
        doc = await self._store.get_vlan_document(network_id, vlan_id)
        return project_vlan(doc) if doc else None

    async def list_topologies(self) -> list[Topology]:
        """Return the topology of every network in the current organisation."""
        docs = await self._store.list_topology_documents()
        return [project_topology(d) for d in docs]

    async def get_topology(self, network_id: str) -> Topology | None:
        """Return a single network's topology, or ``None`` when absent."""
        doc = await self._store.get_topology_document(network_id)
        return project_topology(doc) if doc else None

    async def list_clients(
        self,
        network_id: str | None = None,
        switchport: str | None = None,
        ip: str | None = None,
        vlan: str | None = None,
        user: str | None = None,
    ) -> list[Client]:
        """List recently-seen clients, optionally filtered by network id,
        switchport, ip, vlan or user."""
        docs = await self._store.list_client_documents(network_id, switchport, ip, vlan, user)
        network_map = await self._network_map()
        return [project_client(d, network_map) for d in docs]

    async def get_client(self, mac: str) -> Client | None:
        """Return a single client by its normalized MAC address, or ``None``."""
        doc = await self._store.get_client_document(mac)
        if doc is None:
            return None
        return project_client(doc, await self._network_map())

    async def search_events(  # noqa: PLR0913, PLR0917
        self,
        start: str | None = None,
        end: str | None = None,
        q: str | None = None,
        device: str | None = None,
        network_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Search syslog events over a time range with optional filters."""
        docs = await self._store.search_event_documents(
            start=start, end=end, q=q, device=device, network_id=network_id, limit=_bounded(limit)
        )
        return [project_event(d) for d in docs]

    async def list_changes(
        self,
        device: str | None = None,
        network_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> list[Change]:
        """List changelog entries for a device or network over a time window."""
        docs = await self._store.list_change_documents(
            device=device, network_id=network_id, start=start, end=end, limit=_bounded(limit)
        )
        return [project_change(d) for d in docs]

    async def impact(
        self,
        device: str | None = None,
        uplink_serial: str | None = None,
        uplink_interface: str | None = None,
        depth: int | None = None,
    ) -> ImpactResult | None:
        """Compute the impact analysis from a device serial or uplink seed.

        Returns ``None`` when the seed does not exist in the graph.
        Raises ``GraphUnavailableError`` when the graph store is not wired.
        """
        if self._impact_analyzer is None:
            raise GraphUnavailableError()
        if device is not None:
            return await self._impact_analyzer.impact_from_device(device, depth=depth)
        if uplink_serial is not None and uplink_interface is not None:
            return await self._impact_analyzer.impact_from_uplink(
                uplink_serial, uplink_interface, depth=depth
            )
        return None
