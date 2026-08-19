# 04 — State read mirror: uplinks, switchports, vlans, topology, clients

**What to build:** the rest of the state read mirror, bearer-protected: list/get for uplinks, switchports, vlans, topology, and clients — with network-scoped variants — all carrying `as_of`. Client responses are explicitly flagged as ephemeral (recently-seen in the ~1h30m window), and a client's device fields are presented as "the device that most recently reported it," not a definitive home.

**Blocked by:** 03 — state read mirror: networks + devices.

**Status:** done

- [x] Uplinks, switchports, vlans, and topology endpoints return trimmed state with `as_of`.
- [x] Clients can be listed (by network, switchport, ip, vlan, user/hostname) and fetched by normalized mac.
- [x] Client responses carry an explicit ephemeral/recently-seen flag.
- [x] Network-scoped variants of the endpoints work.
- [x] Every response carries `as_of`; all endpoints require bearer auth.
- [x] Each projection is tested through the REST seam with the in-memory ES fake.

## Implementation notes

- Five new entity families follow the ticket-03 pattern: `domain/{uplinks,switchports,vlans,topology,clients}.py` entities; raw doc dataclasses (`UplinkDocument`, `SwitchportDocument`, `VlanDocument`, `TopologyDocument`, `ClientDocument`) + `StateStore` protocol methods in `application/state_store.py`; projection functions in `application/state_projector.py`; queries in `adapters/elasticsearch_state_store.py`; routers in `presentation/state_router.py`.
- Index contracts (from the Logstash pipelines): `meraki-uplink-metrics` (doc id `serial-interface`, 5m), `meraki-switchport-metrics` (`serial-portId`, 60m), `meraki-vlan-metrics` (`network_id-vlan_id`, 60m), `meraki-topology-metrics` (`network_id`, 60m), `meraki-client-metrics` (`mac`, 15m). Filters map to `bool.filter` `term` clauses; `meraki_org_id` always ANDed server-side; `size` capped at 10000.
- Endpoints: `GET /uplinks?network_id&serial`, `/uplinks/{serial}/{interface}`, `GET /switchports?network_id&serial`, `/switchports/{serial}/{port_id}`, `GET /vlans?network_id`, `/vlans/{network_id}/{vlan_id}`, `GET /topology`, `/topology/{network_id}`, `GET /clients?network_id&switchport&ip&vlan&user`, `/clients/{mac}` — all bearer-protected, 401s carry `WWW-Authenticate: Bearer`.
- Network scoping is done via the `network_id` query filter (flat-surface pattern from ticket 03); uplink/vlan/switchport/topology responses carry `network_name` where the pipeline bakes it in, and switchports/clients join the network name via the network-docs map in the read core.
- Client semantics: `ephemeral` is always `true` (docs only prove a recent sighting, ~1h30m window); `serial`/`network_id` reflect the reporting device, not a definitive home.
- Topology projection converts the Meraki link-layer shape (`topology.nodes[]` with `id/name/status/productType`, `topology.links[].ends[]` with `nodeId/portId`) into structured `TopologyNode`/`TopologyLink` entities plus `node_count`/`link_count`/`offline_nodes`.
- Shared REST-seam fixtures (`bearer`, `auth_header`) moved into `tests/conftest.py`; 35 new tests across `tests/test_{uplinks,switchports,vlans,topology,clients}.py`.
- Verified: full suite green (69 unit + 5 Postgres integration), ruff clean, architecture contracts hold (domain/application free of adapters/presentation), live smoke test of all five new surfaces + 401.