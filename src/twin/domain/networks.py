"""Domain entity for a Meraki network, projected from Elasticsearch."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Network:
    """Projected network state from Elasticsearch, carries explicit freshness."""

    id: str
    name: str
    time_zone: str | None
    product_types: list[str] | None
    tags: list[str] | None
    as_of: str  # ISO-8601 string; the @timestamp of the network document
