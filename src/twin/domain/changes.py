"""Domain entity for a changelog entry, projected from Elasticsearch.

Change entries come from the day-partitioned ``*-history-*`` indices
populated by the Logstash pipelines.  Each entry records the previous
and current values of the watched fields plus the entity identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Change:
    """A single changelog entry for a device or network."""

    timestamp: str  # ISO-8601 @timestamp of the detected change
    index: str  # the history index the entry was read from
    entity_type: str  # e.g. network, device, inventory, uplink, switchport, vlan, topology
    entity_id: str  # serial, network id, or combined key
    network_id: str | None
    serial: str | None
    previous: dict[str, Any] = field(default_factory=dict)  # history.previous
    current: dict[str, Any] = field(default_factory=dict)  # current top-level values
    as_of: str = ""  # ISO-8601 @timestamp; same value as ``timestamp``

