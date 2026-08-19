"""Domain entity for a Meraki client, projected from Elasticsearch.

Clients are inherently ephemeral: a client document's presence only means the
client was recently seen (the pipeline's ~1h30m poll window).  Device fields on
a client (``serial``, ``network_id``) represent the device that most recently
reported the client, not a definitive home.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Client:
    """Projected recently-seen client state, explicitly flagged as ephemeral."""

    mac: str  # normalized lowercase, no separators
    network_id: str | None
    network_name: str | None
    serial: str | None  # device that most recently reported this client
    ip: str | None
    ip6: str | None
    description: str | None
    user: str | None
    vlan: str | None
    switchport: str | None
    ssid: str | None
    status: str | None
    last_seen: str | None
    ephemeral: bool  # always True: recently-seen window, not authoritative
    as_of: str  # ISO-8601; the @timestamp of the client document
