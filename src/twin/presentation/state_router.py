"""REST read-mirror endpoints for networks and devices.

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

from twin.application.state_projector import project_device, project_devices, project_network
from twin.application.state_store import StateStore
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
