"""REST endpoint for impact analysis — GET /twin/impact."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from twin.application.read_mirror import GraphUnavailableError, ReadMirror
from twin.domain.tokens import Token
from twin.presentation.bearer import require_bearer
from twin.presentation.dependencies import get_read_mirror

AuthenticatedToken = Annotated[Token, Depends(require_bearer)]
Mirror = Annotated[ReadMirror, Depends(get_read_mirror)]

router = APIRouter(prefix="/twin", tags=["impact"])


@router.get("/impact")
async def impact(
    _token: AuthenticatedToken,
    mirror: Mirror,
    device: str | None = Query(default=None),
    uplink_serial: str | None = Query(default=None),
    uplink_interface: str | None = Query(default=None),
    depth: int | None = Query(default=None),
) -> dict:
    """Compute the impact analysis from a device or uplink seed."""
    try:
        result = await mirror.impact(
            device=device,
            uplink_serial=uplink_serial,
            uplink_interface=uplink_interface,
            depth=depth,
        )
    except GraphUnavailableError:
        from starlette.responses import JSONResponse

        return JSONResponse(
            content={"error": "graph store unavailable"},
            status_code=503,
        )
    if result is None:
        from starlette.responses import JSONResponse

        return JSONResponse(content={"error": "not found"}, status_code=404)
    return {
        "seed_id": result.seed_id,
        "reachable": [
            {"id": d.id, "name": d.name, "status": d.status, "network_id": d.network_id}
            for d in result.reachable
        ],
        "masked": [
            {"id": d.id, "name": d.name, "status": d.status, "network_id": d.network_id}
            for d in result.masked
        ],
        "as_of": result.as_of,
    }
