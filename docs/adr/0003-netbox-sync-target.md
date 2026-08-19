# NetBox is a sync target now, a source of truth later

The twin translates discovered state one-way from Elasticsearch into NetBox (devices and uplink interfaces/IPs, keyed by serial, additive create/update), keeping NetBox current while the operational model is still discovery-based rather than intent-based. NetBox is explicitly not a source of truth yet; if and when the ecosystem matures, this flow may invert. Recording this posture prevents a future reader from assuming NetBox feedback flows back into the twin.
