"""MCP server surface — a thin adapter over the shared read core.

Exposes one tool per core read operation (get/list per state domain, events
search, changes list), mirroring the REST surface over an SSE/HTTP MCP
transport.  The whole surface is protected by the same bearer tokens as the
REST endpoints.

The ``ReadMirror`` and ``TokenService`` come from a runtime context that the
FastAPI lifespan (or tests) binds via ``configure_runtime``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import HTTPException, status
from mcp.server.mcpserver import MCPServer
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from twin.application.read_mirror import GraphUnavailableError, ReadMirror
from twin.application.token_service import TokenService
from twin.presentation.bearer import WWW_AUTHENTICATE, validate_bearer_header

_server = MCPServer("MerakiNetworkTwin", version="0.1.0")


class _Context:
    """Mutable runtime context binding the core services to the MCP tools."""

    def __init__(self) -> None:
        self.mirror: ReadMirror | None = None
        self.token_service: TokenService | None = None


_context = _Context()


def configure_runtime(mirror: ReadMirror, token_service: TokenService) -> None:
    """Bind the core mirror and token service the MCP tools delegate to."""
    _context.mirror = mirror
    _context.token_service = token_service


def _mirror() -> ReadMirror:
    if _context.mirror is None:
        raise RuntimeError("MCP runtime is not configured")
    return _context.mirror


@_server.tool()
async def list_networks() -> list[dict]:
    """List every network in the current organisation with its as-of timestamp."""
    return [asdict(network) for network in await _mirror().list_networks()]


@_server.tool()
async def get_network(network_id: str) -> dict:
    """Return a single network by its id."""
    network = await _mirror().get_network(network_id)
    if network is None:
        raise ValueError(f"network not found: {network_id}")
    return asdict(network)


@_server.tool()
async def list_devices(
    network_id: str | None = None,
    product_type: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """List devices, optionally filtered by network id, product type or status."""
    devices = await _mirror().list_devices(network_id, product_type, status)
    return [asdict(device) for device in devices]


@_server.tool()
async def get_device(serial: str) -> dict:
    """Return a single device by its serial number."""
    device = await _mirror().get_device(serial)
    if device is None:
        raise ValueError(f"device not found: {serial}")
    return asdict(device)


@_server.tool()
async def list_uplinks(
    network_id: str | None = None,
    serial: str | None = None,
) -> list[dict]:
    """List uplinks, optionally filtered by network id or device serial."""
    return [asdict(uplink) for uplink in await _mirror().list_uplinks(network_id, serial)]


@_server.tool()
async def get_uplink(serial: str, interface: str) -> dict:
    """Return a single uplink by device serial and interface."""
    uplink = await _mirror().get_uplink(serial, interface)
    if uplink is None:
        raise ValueError(f"uplink not found: {serial}/{interface}")
    return asdict(uplink)


@_server.tool()
async def list_switchports(
    network_id: str | None = None,
    serial: str | None = None,
) -> list[dict]:
    """List switchports, optionally filtered by network id or device serial."""
    return [asdict(sp) for sp in await _mirror().list_switchports(network_id, serial)]


@_server.tool()
async def get_switchport(serial: str, port_id: str) -> dict:
    """Return a single switchport by device serial and port id."""
    switchport = await _mirror().get_switchport(serial, port_id)
    if switchport is None:
        raise ValueError(f"switchport not found: {serial}/{port_id}")
    return asdict(switchport)


@_server.tool()
async def list_vlans(network_id: str | None = None) -> list[dict]:
    """List VLANs, optionally filtered by network id."""
    return [asdict(vlan) for vlan in await _mirror().list_vlans(network_id)]


@_server.tool()
async def get_vlan(network_id: str, vlan_id: str) -> dict:
    """Return a single VLAN by network id and vlan id."""
    vlan = await _mirror().get_vlan(network_id, vlan_id)
    if vlan is None:
        raise ValueError(f"vlan not found: {network_id}/{vlan_id}")
    return asdict(vlan)


@_server.tool()
async def list_topologies() -> list[dict]:
    """List the topology of every network in the current organisation."""
    return [asdict(topology) for topology in await _mirror().list_topologies()]


@_server.tool()
async def get_topology(network_id: str) -> dict:
    """Return a single network's topology."""
    topology = await _mirror().get_topology(network_id)
    if topology is None:
        raise ValueError(f"topology not found: {network_id}")
    return asdict(topology)


@_server.tool()
async def list_clients(
    network_id: str | None = None,
    switchport: str | None = None,
    ip: str | None = None,
    vlan: str | None = None,
    user: str | None = None,
) -> list[dict]:
    """List recently-seen clients, optionally filtered by network id, switchport,
    ip, vlan or user."""
    clients = await _mirror().list_clients(network_id, switchport, ip, vlan, user)
    return [asdict(client) for client in clients]


@_server.tool()
async def get_client(mac: str) -> dict:
    """Return a single client by its normalized MAC address."""
    client = await _mirror().get_client(mac)
    if client is None:
        raise ValueError(f"client not found: {mac}")
    return asdict(client)


@_server.tool()
async def list_events(  # noqa: PLR0913, PLR0917
    start: str | None = None,
    end: str | None = None,
    q: str | None = None,
    device: str | None = None,
    network_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Search syslog events over a time range with optional free-text and
    device or network filters.  ``limit`` is clamped to 1-1000."""
    events = await _mirror().search_events(start, end, q, device, network_id, limit)
    return [asdict(event) for event in events]


@_server.tool()
async def list_changes(
    device: str | None = None,
    network_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List changelog entries for a device or network over a time window.
    ``limit`` is clamped to 1-1000."""
    changes = await _mirror().list_changes(device, network_id, start, end, limit)
    return [asdict(change) for change in changes]


@_server.tool()
async def impact(
    device: str | None = None,
    uplink_serial: str | None = None,
    uplink_interface: str | None = None,
    depth: int | None = None,
) -> dict:
    """Compute impact analysis from a device serial or uplink seed.

    Seed must be either ``device`` (a serial) or both ``uplink_serial`` and
    ``uplink_interface``.  Returns the reachable and masked device sets.
    Raises ``GraphUnavailableError`` if the graph store is not configured.
    """
    try:
        result = await _mirror().impact(
            device=device,
            uplink_serial=uplink_serial,
            uplink_interface=uplink_interface,
            depth=depth,
        )
    except GraphUnavailableError:
        return {"error": "graph store unavailable"}
    if result is None:
        return {"error": "not found"}
    return {
        "seed_id": result.seed_id,
        "reachable": [asdict(d) for d in result.reachable],
        "masked": [asdict(d) for d in result.masked],
        "as_of": result.as_of,
    }


def _bearer_wrap(app: ASGIApp) -> ASGIApp:
    """Enforce the same bearer-token scheme as the REST surface on an ASGI app."""

    async def wrapper(scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in scope["headers"]
            }
            authorization = headers.get("authorization")
            token_service = _context.token_service
            if token_service is None:
                response = JSONResponse(
                    {"detail": "Token validation is not configured"},
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    headers=WWW_AUTHENTICATE,
                )
                await response(scope, receive, send)
                return
            try:
                await validate_bearer_header(authorization, token_service)
            except HTTPException as exc:
                response = JSONResponse(
                    {"detail": exc.detail},
                    status_code=exc.status_code,
                    headers=exc.headers or WWW_AUTHENTICATE,
                )
                await response(scope, receive, send)
                return
        await app(scope, receive, send)

    return wrapper


def mcp_app() -> ASGIApp:
    """Return the bearer-protected MCP SSE application to mount at ``/mcp``."""
    sse = _server.sse_app(sse_path="/sse", message_path="/messages/", host="0.0.0.0")
    return _bearer_wrap(sse)
