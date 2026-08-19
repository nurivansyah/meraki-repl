"""Domain entity for a Meraki device, projected from Elasticsearch.

Merges inventory (serial, model, mac, firmware, etc.) with availability
(status, network_id) and enriches with the network name from the
corresponding network document. Every device carries an ``as_of`` freshness
timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Device:
    """Projected device state from Elasticsearch, carries explicit freshness."""

    serial: str
    name: str
    model: str | None
    mac: str | None
    network_id: str | None
    network_name: str | None
    product_type: str | None  # Meraki productType from inventory
    status: str | None  # online|offline|alerting|dormant|None if metrics missing
    firmware: str | None
    lan_ip: str | None  # from inventory (e.g. 10.0.0.1)
    wan_ip: str | None  # from inventory (e.g. 10.1.0.1)
    as_of: str  # ISO-8601; aggregated from inventory + metrics timestamps
