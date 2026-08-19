"""Domain entities for Meraki topology, projected from Elasticsearch."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TopologyNode:
    """A node in a network's link-layer topology."""

    id: str
    name: str | None
    status: str | None  # online|offline|alerting|dormant
    product_type: str | None


@dataclass
class TopologyLink:
    """An edge between two nodes in a network's topology."""

    source: str
    source_port: str | None
    target: str
    target_port: str | None


@dataclass
class Topology:
    """Projected link-layer topology for a network, carries explicit freshness."""

    network_id: str
    network_name: str | None
    node_count: int
    link_count: int
    offline_nodes: list[dict] = field(default_factory=list)
    nodes: list[TopologyNode] = field(default_factory=list)
    links: list[TopologyLink] = field(default_factory=list)
    as_of: str = ""
