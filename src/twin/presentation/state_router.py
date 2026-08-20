"""REST read-mirror endpoints for the state mirror.

All endpoints are bearer-token protected; unauthenticated requests receive
``401`` with ``WWW-Authenticate: Bearer``.

Endpoints are thin adapters over the shared ``ReadMirror`` core; projection
and cross-index joins live there, not in this router.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from twin.application.read_mirror import ReadMirror
from twin.domain.tokens import Token
from twin.presentation.bearer import require_bearer
from twin.presentation.dependencies import get_read_mirror

AuthenticatedToken = Annotated[Token, Depends(require_bearer)]
Mirror = Annotated[ReadMirror, Depends(get_read_mirror)]

router = APIRouter(prefix="/networks", tags=["network"])


@router.get("", status_code=200)
async def list_networks(_token: AuthenticatedToken, mirror: Mirror) -> list[dict]:
    """Return every network as a flat array; each item carries ``as_of``."""
    return [asdict(network) for network in await mirror.list_networks()]


@router.get("/{network_id}", status_code=200)
async def get_network(network_id: str, _token: AuthenticatedToken, mirror: Mirror) -> dict:
    """Return a single network by its id."""
    network = await mirror.get_network(network_id)
    if network is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="network not found")
    return asdict(network)


router_devices = APIRouter(prefix="/devices", tags=["devices"])


@router_devices.get("", status_code=200)
async def list_devices(
    _token: AuthenticatedToken,
    mirror: Mirror,
    network_id: str | None = None,
    product_type: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """Return devices; optional filters ``network_id``, ``product_type``, ``status``."""
    devices = await mirror.list_devices(network_id, product_type, status)
    return [asdict(device) for device in devices]


@router_devices.get("/{serial}", status_code=200)
async def get_device(serial: str, _token: AuthenticatedToken, mirror: Mirror) -> dict:
    """Return a single device by its serial number."""
    device = await mirror.get_device(serial)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="device not found")
    return asdict(device)


router_uplinks = APIRouter(prefix="/uplinks", tags=["uplinks"])


@router_uplinks.get("", status_code=200)
async def list_uplinks(
    _token: AuthenticatedToken,
    mirror: Mirror,
    network_id: str | None = None,
    serial: str | None = None,
) -> list[dict]:
    """Return uplinks; optional filters ``network_id``, ``serial``."""
    return [asdict(uplink) for uplink in await mirror.list_uplinks(network_id, serial)]


@router_uplinks.get("/{serial}/{interface}", status_code=200)
async def get_uplink(
    serial: str,
    interface: str,
    _token: AuthenticatedToken,
    mirror: Mirror,
) -> dict:
    """Return a single uplink by device serial and interface."""
    uplink = await mirror.get_uplink(serial, interface)
    if uplink is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="uplink not found")
    return asdict(uplink)


router_switchports = APIRouter(prefix="/switchports", tags=["switchports"])


@router_switchports.get("", status_code=200)
async def list_switchports(
    _token: AuthenticatedToken,
    mirror: Mirror,
    network_id: str | None = None,
    serial: str | None = None,
) -> list[dict]:
    """Return switchports; optional filters ``network_id``, ``serial``."""
    return [asdict(sp) for sp in await mirror.list_switchports(network_id, serial)]


@router_switchports.get("/{serial}/{port_id}", status_code=200)
async def get_switchport(
    serial: str,
    port_id: str,
    _token: AuthenticatedToken,
    mirror: Mirror,
) -> dict:
    """Return a single switchport by device serial and port id."""
    switchport = await mirror.get_switchport(serial, port_id)
    if switchport is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="switchport not found")
    return asdict(switchport)


router_vlans = APIRouter(prefix="/vlans", tags=["vlans"])


@router_vlans.get("", status_code=200)
async def list_vlans(
    _token: AuthenticatedToken,
    mirror: Mirror,
    network_id: str | None = None,
) -> list[dict]:
    """Return VLANs; optional filter ``network_id``."""
    return [asdict(vlan) for vlan in await mirror.list_vlans(network_id)]


@router_vlans.get("/{network_id}/{vlan_id}", status_code=200)
async def get_vlan(
    network_id: str,
    vlan_id: str,
    _token: AuthenticatedToken,
    mirror: Mirror,
) -> dict:
    """Return a single VLAN by network id and vlan id."""
    vlan = await mirror.get_vlan(network_id, vlan_id)
    if vlan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="vlan not found")
    return asdict(vlan)


router_topology = APIRouter(prefix="/topology", tags=["topology"])


@router_topology.get("", status_code=200)
async def list_topologies(_token: AuthenticatedToken, mirror: Mirror) -> list[dict]:
    """Return the topology of every network as a flat array."""
    return [asdict(topology) for topology in await mirror.list_topologies()]


@router_topology.get("/{network_id}", status_code=200)
async def get_topology(network_id: str, _token: AuthenticatedToken, mirror: Mirror) -> dict:
    """Return a single network's topology."""
    topology = await mirror.get_topology(network_id)
    if topology is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="topology not found")
    return asdict(topology)


router_clients = APIRouter(prefix="/clients", tags=["clients"])


@router_clients.get("", status_code=200)
async def list_clients(  # noqa: PLR0913, PLR0917
    _token: AuthenticatedToken,
    mirror: Mirror,
    network_id: str | None = None,
    switchport: str | None = None,
    ip: str | None = None,
    vlan: str | None = None,
    user: str | None = None,
) -> list[dict]:
    """Return recently-seen clients; optional filters ``network_id``, ``switchport``,
    ``ip``, ``vlan``, ``user``."""
    clients = await mirror.list_clients(network_id, switchport, ip, vlan, user)
    return [asdict(client) for client in clients]


@router_clients.get("/{mac}", status_code=200)
async def get_client(mac: str, _token: AuthenticatedToken, mirror: Mirror) -> dict:
    """Return a single client by its normalized MAC address."""
    client = await mirror.get_client(mac)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="client not found")
    return asdict(client)
