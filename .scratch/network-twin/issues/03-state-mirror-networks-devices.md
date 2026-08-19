# 03 — State read mirror: networks + devices

**What to build:** the first slice of the REST read mirror, bearer-protected: list and get-by-id endpoints for networks, and list (with filters) and get-by-serial endpoints for devices, where a device response merges inventory, availability, and network name into one payload. Every state response carries an `as_of` freshness timestamp. Responses are flat arrays with trimmed fields and a fixed org — no pagination envelope.

**Blocked by:** 02 — auth realm: API tokens.

**Status:** ready-for-agent

- [ ] `GET` networks returns the network list with trimmed fields and `as_of`.
- [ ] `GET` devices returns devices; filters (network, product type, status) work.
- [ ] A device response merges inventory + availability + network name into one object.
- [ ] `GET` a single network and single device by id/serial work.
- [ ] Every response carries `as_of`; responses are flat arrays without Meraki's pagination envelope.
- [ ] Unauthenticated requests are rejected; bearer auth works on every endpoint.
- [ ] Projection logic is tested through the REST seam with the in-memory ES fake.
