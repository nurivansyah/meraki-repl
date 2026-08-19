"""Domain entity for a syslog event, projected from Elasticsearch.

The twin surfaces the raw syslog shape: the ``message`` is the untrusted,
unstructured line as written by Meraki.  Structured fields (parsed
``client_mac``, ``serial``, etc.) depend on a future Logstash parsing
pipeline, so the access surface here is the stable contract and the
full source is preserved in ``raw``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    """A single syslog event, trimmed but carrying the full raw source."""

    timestamp: str  # ISO-8601 @timestamp
    message: str  # the raw syslog message line
    device: str | None  # the reporting syslog host (source)
    network_id: str | None  # present only when a parser has populated it
    raw: dict[str, Any] = field(default_factory=dict)  # full raw document

