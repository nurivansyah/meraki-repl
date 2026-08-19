"""Projection functions — compose raw Elasticsearch documents into domain entities."""

from __future__ import annotations

from twin.application.state_store import (
    ChangeDocument,
    ClientDocument,
    DeviceInventoryDocument,
    DeviceMetricsDocument,
    EventDocument,
    NetworkDocument,
    SwitchportDocument,
    TopologyDocument,
    UplinkDocument,
    VlanDocument,
)
from twin.domain.changes import Change
from twin.domain.clients import Client
from twin.domain.devices import Device
from twin.domain.events import Event
from twin.domain.networks import Network
from twin.domain.switchports import Switchport
from twin.domain.topology import Topology, TopologyLink, TopologyNode
from twin.domain.uplinks import Uplink
from twin.domain.vlans import Vlan


def _parse_as_of(ts: str) -> str:
    """Return the ISO-8601 timestamp as-is (already from ES ``@timestamp``)."""
    return ts


def project_network(doc: NetworkDocument) -> Network:
    """Convert a ``NetworkDocument`` into a domain ``Network``."""
    return Network(
        id=doc.id,
        name=doc.name,
        time_zone=doc.time_zone,
        product_types=doc.product_types,
        tags=doc.tags,
        as_of=_parse_as_of(doc.as_of),
    )


def project_device(
    inv: DeviceInventoryDocument | None,
    metrics: DeviceMetricsDocument | None,
    network_docs_map: dict[str, NetworkDocument],
) -> Device:
    """Compose a domain ``Device`` from optional inventory and metrics docs.

    Liberal merge: the device is materialised if *either* side exists.  Identity
    comes from inventory where available, falling back to metrics.  The network
    name is resolved from ``network_docs_map`` keyed by ``network_id``.
    """
    if inv is None and metrics is None:
        raise ValueError("project_device requires at least one of inventory or metrics")

    serial = inv.serial if inv else metrics.serial  # type: ignore[union-attr]
    name = (inv.name if inv else None) or (metrics.name if metrics else None)
    model = inv.model if inv else None
    mac = inv.mac if inv else None
    network_id = (inv.network_id if inv else None) or (metrics.network_id if metrics else None)
    product_type = inv.product_type if inv else None
    status = metrics.status if metrics else None
    firmware = inv.firmware if inv else None
    lan_ip = inv.lan_ip if inv else None
    wan_ip = inv.wan_ip if inv else None

    network_doc = network_docs_map.get(network_id) if network_id else None
    network_name = network_doc.name if network_doc else None

    if metrics and metrics.as_of:
        as_of = metrics.as_of
    elif inv and inv.as_of:
        as_of = inv.as_of
    else:
        as_of = ""

    return Device(
        serial=serial,
        name=name,
        model=model,
        mac=mac,
        network_id=network_id,
        network_name=network_name,
        product_type=product_type,
        status=status,
        firmware=firmware,
        lan_ip=lan_ip,
        wan_ip=wan_ip,
        as_of=_parse_as_of(as_of),
    )


def project_devices(
    inventory_docs: list[DeviceInventoryDocument],
    metrics_docs: list[DeviceMetricsDocument],
    network_docs_map: dict[str, NetworkDocument],
    primary: str | None = None,
) -> list[Device]:
    """Build a ``Device`` for every relevant serial.

    ``primary`` selects the side that defines membership:
      - ``"metrics"``   → a status filter was applied; only status-matching devices.
      - ``"inventory"`` → a product-type (or other inventory-only) filter was applied.
      - ``None``        → no restrictive filter; the full union of both sides.

    The non-primary side enriches devices rather than expanding the result set.
    Results are sorted by serial for a deterministic order.
    """
    inv_by_serial = {doc.serial: doc for doc in inventory_docs}
    met_by_serial = {doc.serial: doc for doc in metrics_docs}
    if primary == "metrics":
        serials = met_by_serial
    elif primary == "inventory":
        serials = inv_by_serial
    else:
        serials = set(inv_by_serial) | set(met_by_serial)
    return [
        project_device(inv_by_serial.get(serial), met_by_serial.get(serial), network_docs_map)
        for serial in sorted(serials)
    ]


def project_uplink(doc: UplinkDocument) -> Uplink:
    """Convert an ``UplinkDocument`` into a domain ``Uplink``."""
    return Uplink(
        serial=doc.serial,
        interface=doc.interface,
        network_id=doc.network_id,
        network_name=doc.network_name,
        public_ip=doc.public_ip,
        ip=doc.ip,
        gateway=doc.gateway,
        addressing=doc.addressing,
        status=doc.status,
        enabled=doc.enabled,
        primary=doc.primary,
        dns=doc.dns,
        as_of=_parse_as_of(doc.as_of),
    )


def project_switchport(
    doc: SwitchportDocument,
    network_docs_map: dict[str, NetworkDocument],
) -> Switchport:
    """Convert a ``SwitchportDocument`` into a domain ``Switchport``."""
    network_doc = network_docs_map.get(doc.network_id) if doc.network_id else None
    return Switchport(
        serial=doc.serial,
        port_id=doc.port_id,
        network_id=doc.network_id,
        network_name=network_doc.name if network_doc else None,
        status=doc.status,
        speed=doc.speed,
        duplex=doc.duplex,
        enabled=doc.enabled,
        errors=doc.errors,
        client_count=doc.client_count,
        as_of=_parse_as_of(doc.as_of),
    )


def project_vlan(doc: VlanDocument) -> Vlan:
    """Convert a ``VlanDocument`` into a domain ``Vlan``."""
    return Vlan(
        network_id=doc.network_id,
        vlan_id=doc.vlan_id,
        name=doc.name,
        subnet=doc.subnet,
        appliance_ip=doc.appliance_ip,
        dhcp_handling=doc.dhcp_handling,
        enabled=doc.enabled,
        network_name=doc.network_name,
        as_of=_parse_as_of(doc.as_of),
    )


def _project_topology_node(node: dict) -> TopologyNode:
    return TopologyNode(
        id=str(node.get("id", "")),
        name=node.get("name"),
        status=node.get("status"),
        product_type=node.get("productType"),
    )


def _project_topology_link(link: dict) -> TopologyLink:
    ends = link.get("ends") or []
    if len(ends) > 1:
        source = str(ends[0].get("nodeId", ""))
        source_port = ends[0].get("portId")
        target = str(ends[1].get("nodeId", ""))
        target_port = ends[1].get("portId")
    else:
        source, source_port, target, target_port = "", None, "", None
    return TopologyLink(
        source=source,
        source_port=source_port,
        target=target,
        target_port=target_port,
    )


def project_topology(doc: TopologyDocument) -> Topology:
    """Convert a ``TopologyDocument`` into a domain ``Topology``."""
    return Topology(
        network_id=doc.network_id,
        network_name=doc.network_name,
        node_count=doc.node_count,
        link_count=doc.link_count,
        offline_nodes=doc.offline_nodes,
        nodes=[_project_topology_node(n) for n in (doc.nodes or [])],
        links=[_project_topology_link(link) for link in (doc.links or [])],
        as_of=_parse_as_of(doc.as_of),
    )


def project_client(
    doc: ClientDocument,
    network_docs_map: dict[str, NetworkDocument],
) -> Client:
    """Convert a ``ClientDocument`` into a domain ``Client``.

    Clients are always flagged ephemeral; device fields reflect the device that
    most recently reported the client.
    """
    network_doc = network_docs_map.get(doc.network_id) if doc.network_id else None
    return Client(
        mac=doc.mac,
        network_id=doc.network_id,
        network_name=network_doc.name if network_doc else None,
        serial=doc.serial,
        ip=doc.ip,
        ip6=doc.ip6,
        description=doc.description,
        user=doc.user,
        vlan=doc.vlan,
        switchport=doc.switchport,
        ssid=doc.ssid,
        status=doc.status,
        last_seen=doc.last_seen,
        ephemeral=True,
        as_of=_parse_as_of(doc.as_of),
    )


def project_event(doc: EventDocument) -> Event:
    """Convert an ``EventDocument`` into a domain ``Event``."""
    return Event(
        timestamp=doc.timestamp,
        message=doc.message,
        device=doc.device,
        network_id=doc.network_id,
        raw=doc.raw,
    )


def project_change(doc: ChangeDocument) -> Change:
    """Convert a ``ChangeDocument`` into a domain ``Change``."""
    return Change(
        timestamp=doc.timestamp,
        index=doc.index,
        entity_type=doc.entity_type,
        entity_id=doc.entity_id,
        network_id=doc.network_id,
        serial=doc.serial,
        previous=doc.previous,
        current=doc.current,
        as_of=_parse_as_of(doc.as_of),
    )
