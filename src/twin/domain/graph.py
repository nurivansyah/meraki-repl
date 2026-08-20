"""Domain entities for the Neo4j graph projection and impact analysis.

These live in the graph layer — distinct from the REST-mirror entities in
``twin.domain.networks``/``twin.domain.devices`` which are the ES → projector
output.  ``GraphNetwork.last_synced_at`` tracks the latest topology
``@timestamp`` that was successfully projected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GraphNetwork:
    """A network as projected into the Neo4j graph."""

    id: str
    name: str | None = None
    last_synced_at: datetime | None = None


@dataclass
class ImpactedDevice:
    """A device surfaced in an impact analysis result."""

    id: str
    name: str | None
    status: str | None
    network_id: str | None


@dataclass
class ImpactResult:
    """The output of an impact query: seed identity, reachable devices, and
    the masked (down/offline) set, plus the freshness marker."""

    seed_id: str
    reachable: list[ImpactedDevice] = field(default_factory=list)
    masked: list[ImpactedDevice] = field(default_factory=list)
    as_of: str = ""
