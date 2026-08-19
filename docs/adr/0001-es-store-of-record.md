# ES is the store of record; the twin is a stateless read-only projection

Elasticsearch (fed by Logstash polling the Meraki API) is the sole source of truth for the twin. The twin is a stateless projection and translation layer: it reads ES, exposes a REST read mirror and MCP interface, and translates state to Neo4j and NetBox. It never calls the Meraki API and never writes to Elasticsearch. This keeps rate-limit and data-collection concerns entirely in the Logstash/ES stack, so consumers of the twin can never exhaust Meraki API quotas, and the twin holds no mutable state of its own.
