"""Domain entity for a Meraki VLAN, projected from Elasticsearch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Vlan:
    """Projected VLAN state, carries explicit freshness."""

    network_id: str
    vlan_id: str
    name: str | None
    subnet: str | None
    appliance_ip: str | None
    dhcp_handling: str | None
    enabled: bool | None
    network_name: str | None
    as_of: str  # ISO-8601; the @timestamp of the VLAN document
