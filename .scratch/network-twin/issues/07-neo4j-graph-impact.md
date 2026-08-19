# 07 — ES→Neo4j sync + impact analysis

**What to build:** the graph projection: a job that reads topology state from Elasticsearch and rebuilds each network's subgraph in Neo4j (`Network` and `Device` nodes; `(Device)-[:IN_NETWORK]->(Network)`; `(Device)-[:LINKED_TO {sourcePort,targetPort}]->(Device)` from topology links), refreshed when a network's poll timestamp changes. Plus `/twin/impact`: a bearer-protected Cypher query that walks `LINKED_TO` from a device, masks down/offline devices, and returns the affected set — deterministic, no capacity claims.

**Blocked by:** 04 — state read mirror: uplinks, switchports, vlans, topology, clients.

**Status:** ready-for-agent

- [ ] The translation job rebuilds a network's subgraph from its topology state in ES.
- [ ] A changed poll timestamp triggers a rebuild of that network's subgraph.
- [ ] `/twin/impact` returns the affected set for a device/uplink via Cypher over Neo4j, masking down/offline devices.
- [ ] The transform logic is tested as a pure function with a fake Neo4j client at the boundary.
- [ ] The endpoint is bearer-protected and carries freshness.
