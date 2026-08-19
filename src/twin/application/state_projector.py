"""Projection functions — compose raw Elasticsearch documents into domain entities."""

from __future__ import annotations

from twin.application.state_store import (
    DeviceInventoryDocument,
    DeviceMetricsDocument,
    NetworkDocument,
)
from twin.domain.devices import Device
from twin.domain.networks import Network


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
