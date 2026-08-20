"""REST endpoints for chronology: events search + changes list.

All endpoints are bearer-token protected; unauthenticated requests receive
``401`` with ``WWW-Authenticate: Bearer``.  Endpoints are thin adapters over
the shared ``ReadMirror`` core.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from twin.application.read_mirror import ReadMirror
from twin.domain.tokens import Token
from twin.presentation.bearer import require_bearer
from twin.presentation.dependencies import get_read_mirror

AuthenticatedToken = Annotated[Token, Depends(require_bearer)]
Mirror = Annotated[ReadMirror, Depends(get_read_mirror)]

router = APIRouter(prefix="/twin", tags=["chronology"])


@router.get("/events", status_code=200)
async def list_events(  # noqa: PLR0913, PLR0917
    _token: AuthenticatedToken,
    mirror: Mirror,
    start: str | None = Query(None, description="ISO-8601 start time (inclusive)"),
    end: str | None = Query(None, description="ISO-8601 end time (inclusive)"),
    q: str | None = Query(None, description="Free-text query on the syslog message"),
    device: str | None = Query(None, description="Filter by reporting device (logsource/host)"),
    network_id: str | None = Query(None, description="Filter by network id"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
) -> list[dict]:
    """Search syslog events with time-range, free-text, and optional filters.

    The raw syslog shape is surfaced in ``raw``; structured fields depend on
    future Logstash parsing.
    """
    events = await mirror.search_events(start, end, q, device, network_id, limit)
    return [asdict(event) for event in events]


@router.get("/changes", status_code=200)
async def list_changes(  # noqa: PLR0913, PLR0917
    _token: AuthenticatedToken,
    mirror: Mirror,
    device: str | None = Query(None, description="Filter by device serial"),
    network_id: str | None = Query(None, description="Filter by network id"),
    start: str | None = Query(None, description="ISO-8601 start time (inclusive)"),
    end: str | None = Query(None, description="ISO-8601 end time (inclusive)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
) -> list[dict]:
    """List changelog entries for a device or network over a time window.

    At least one of ``device`` or ``network_id`` is recommended for a meaningful
    result.  Returns ``previous`` and ``current`` snapshots plus the index and
    entity identity.
    """
    changes = await mirror.list_changes(device, network_id, start, end, limit)
    return [asdict(change) for change in changes]
