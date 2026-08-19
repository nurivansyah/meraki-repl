"""REST read-mirror endpoints for the state mirror.

All endpoints are bearer-token protected; unauthenticated requests receive
``401`` with ``WWW-Authenticate: Bearer``.

The ``StateStore`` comes from the ``get_state_store`` dependency (bound to the
Elasticsearch client); projection uses the module-level functions from
``twin.application.state_projector``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from twin.application.state_projector import (
    project_client,
    project_device,
    project_devices,
    project_network,
    project_switchport,
    project_topology,
    project_uplink,
    project_vlan,
)
from twin.application.state_store import NetworkDocument, StateStore
from twin.domain.tokens import Token
from twin.presentation.bearer import require_bearer
from twin.presentation.dependencies import get_state_store

AuthenticatedToken = Annotated[Token, Depends(require_bearer)]
Store = Annotated[StateStore, Depends(get_state_store)]

router = APIRouter(prefix="/networks", tags=["network"])


@router.get("", status_code=200)
async def list_networks(_token: AuthenticatedToken, store: Store) -> list[dict]:
    """Return every network as a flat array; each item carries ``as_of``."""
    docs = await store.list_network_documents()
    return [asdict(project_network(d)) for d in docs]


@router.get("/{network_id}", status_code=200)
async def get_network(
    network_id: str,
    _token: AuthenticatedToken,
    store: Store,
) -> dict:
    """Return a single network by its id."""
    doc = await store.get_network_document(network_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="network not found")
    return asdict(project_network(doc))


router_devices = APIRouter(prefix="/devices", tags=["devices"])


@router_devices.get("", status_code=200)
async def list_devices(
    _token: AuthenticatedToken,
    store: Store,
    network_id: str | None = None,
    product_type: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """Return devices; optional filters ``network_id``, ``product_type``, ``status``."""
    inventory_docs = await store.list_device_inventory_documents(network_id, product_type)
    metrics_docs = await store.list_device_metrics_documents(network_id, status)
    net_docs = await store.list_network_documents()
    net_map = {d.id: d for d in net_docs}
    primary = "metrics" if status else ("inventory" if product_type else None)
    devices = project_devices(inventory_docs, metrics_docs, net_map, primary)
    return [asdict(d) for d in devices]


@router_devices.get("/{serial}", status_code=200)
async def get_device(
    serial: str,
    _token: AuthenticatedToken,
    store: Store,
) -> dict:
    """Return a single device by its serial number."""
    inv = await store.get_device_inventory_document(serial)
    met = await store.get_device_metrics_document(serial)
    if inv is None and met is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="device not found")
    net_docs = await store.list_network_documents()
    net_map = {d.id: d for d in net_docs}
    return asdict(project_device(inv, met, net_map))


async def _network_map(store: StateStore) -> dict[str, NetworkDocument]:
    """Return a map of network id → NetworkDocument for cross-index joins."""
    docs = await store.list_network_documents()
    return {d.id: d for d in docs}


router_uplinks = APIRouter(prefix="/uplinks", tags=["uplinks"])


@router_uplinks.get("", status_code=200)
async def list_uplinks(
    _token: AuthenticatedToken,
    store: Store,
    network_id: str | None = None,
    serial: str | None = None,
) -> list[dict]:
    """Return uplinks; optional filters ``network_id``, ``serial``."""
    docs = await store.list_uplink_documents(network_id, serial)
    return [asdict(project_uplink(d)) for d in docs]


@router_uplinks.get("/{serial}/{interface}", status_code=200)
async def get_uplink(
    serial: str,
    interface: str,
    _token: AuthenticatedToken,
    store: Store,
) -> dict:
    """Return a single uplink by device serial and interface."""
    doc = await store.get_uplink_document(serial, interface)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="uplink not found")
    return asdict(project_uplink(doc))


router_switchports = APIRouter(prefix="/switchports", tags=["switchports"])


@router_switchports.get("", status_code=200)
async def list_switchports(
    _token: AuthenticatedToken,
    store: Store,
    network_id: str | None = None,
    serial: str | None = None,
) -> list[dict]:
    """Return switchports; optional filters ``network_id``, ``serial``."""
    docs = await store.list_switchport_documents(network_id, serial)
    net_map = await _network_map(store)
    return [asdict(project_switchport(d, net_map)) for d in docs]


@router_switchports.get("/{serial}/{port_id}", status_code=200)
async def get_switchport(
    serial: str,
    port_id: str,
    _token: AuthenticatedToken,
    store: Store,
) -> dict:
    """Return a single switchport by device serial and port id."""
    doc = await store.get_switchport_document(serial, port_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="switchport not found")
    net_map = await _network_map(store)
    return asdict(project_switchport(doc, net_map))


router_vlans = APIRouter(prefix="/vlans", tags=["vlans"])


@router_vlans.get("", status_code=200)
async def list_vlans(
    _token: AuthenticatedToken,
    store: Store,
    network_id: str | None = None,
) -> list[dict]:
    """Return VLANs; optional filter ``network_id``."""
    docs = await store.list_vlan_documents(network_id)
    return [asdict(project_vlan(d)) for d in docs]


@router_vlans.get("/{network_id}/{vlan_id}", status_code=200)
async def get_vlan(
    network_id: str,
    vlan_id: str,
    _token: AuthenticatedToken,
    store: Store,
) -> dict:
    """Return a single VLAN by network id and vlan id."""
    doc = await store.get_vlan_document(network_id, vlan_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="vlan not found")
    return asdict(project_vlan(doc))


router_topology = APIRouter(prefix="/topology", tags=["topology"])


@router_topology.get("", status_code=200)
async def list_topologies(_token: AuthenticatedToken, store: Store) -> list[dict]:
    """Return the topology of every network as a flat array."""
    docs = await store.list_topology_documents()
    return [asdict(project_topology(d)) for d in docs]


@router_topology.get("/{network_id}", status_code=200)
async def get_topology(
    network_id: str,
    _token: AuthenticatedToken,
    store: Store,
) -> dict:
    """Return a single network's topology."""
    doc = await store.get_topology_document(network_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="topology not found")
    return asdict(project_topology(doc))


router_clients = APIRouter(prefix="/clients", tags=["clients"])


@router_clients.get("", status_code=200)
async def list_clients(  # noqa: PLR0913, PLR0917
    _token: AuthenticatedToken,
    store: Store,
    network_id: str | None = None,
    switchport: str | None = None,
    ip: str | None = None,
    vlan: str | None = None,
    user: str | None = None,
) -> list[dict]:
    """Return recently-seen clients; optional filters ``network_id``, ``switchport``,
    ``ip``, ``vlan``, ``user``."""
    docs = await store.list_client_documents(network_id, switchport, ip, vlan, user)
    net_map = await _network_map(store)
    return [asdict(project_client(d, net_map)) for d in docs]


@router_clients.get("/{mac}", status_code=200)
async def get_client(
    mac: str,
    _token: AuthenticatedToken,
    store: Store,
) -> dict:
    """Return a single client by its normalized MAC address."""
    doc = await store.get_client_document(mac)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="client not found")
    net_map = await _network_map(store)
    return asdict(project_client(doc, net_map))
