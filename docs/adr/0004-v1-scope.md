# v1 scope: read mirror and impact analysis only

v1 ships the REST read mirror, MCP interface, graph projection with deterministic impact analysis, NetBox sync, and auth realm — but explicitly excludes what-if capacity simulation (the fleet maxes out at two uplinks, and no capacity/utilization data is polled) and drift/intent reconciliation against NetBox-as-source-of-truth (intended state does not exist yet). Excluding these is a deliberate scope decision so the twin's v1 contract stays truthful about what it can and cannot answer.
