"""Domain entity for a Meraki uplink, projected from Elasticsearch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Uplink:
    """Projected uplink address state, carries explicit freshness."""

    serial: str
    interface: str  # wan1, wan2, cellular
    network_id: str | None
    network_name: str | None
    public_ip: str | None
    ip: str | None
    gateway: str | None
    addressing: str | None
    status: str | None
    enabled: bool | None
    primary: bool | None
    dns: str | None
    as_of: str  # ISO-8601; the @timestamp of the uplink document
