"""Domain entity for a Meraki switchport, projected from Elasticsearch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Switchport:
    """Projected switchport state, carries explicit freshness."""

    serial: str
    port_id: str
    network_id: str | None
    network_name: str | None
    status: str | None  # Connected|Disconnected
    speed: str | None
    duplex: str | None
    enabled: bool | None
    errors: int | None
    client_count: int | None
    as_of: str  # ISO-8601; the @timestamp of the switchport document
