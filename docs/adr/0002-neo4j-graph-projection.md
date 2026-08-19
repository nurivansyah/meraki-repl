# The topology graph lives in Neo4j, rebuilt from ES

The graph projection is stored in an external Neo4j, rebuilt per-network by the twin from the `topology` object in `meraki-topology-metrics` (which already contains nodes and links), and queried via Cypher for impact analysis. Considered alternative: computing graph traversals in memory over ES documents at query time. Rejected because the graph is a durable, queryable projection that impact analysis queries against repeatedly, and Neo4j gives fast multi-hop traversal without re-joining ES docs per query.
