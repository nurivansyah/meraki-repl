# 08 — ES→NetBox sync

**What to build:** the middleware that keeps NetBox current with discovered state: a one-way translation, keyed by serial, that additively creates/updates NetBox devices (name, type matched from model, serial, status from availability `online/offline` → `active/offline`) and uplink interfaces + IP records. NetBox is a sync target now, not a source of truth — no feedback flow.

**Blocked by:** 04 — state read mirror: uplinks, switchports, vlans, topology, clients.

**Status:** ready-for-agent

- [ ] The sync creates/updates NetBox devices and uplink interfaces/IPs keyed by serial.
- [ ] Status mapping is `online/offline` → `active/offline`; device type is derived from model.
- [ ] The sync is additive (create/update, no deletion of unknown records in v1).
- [ ] The transform logic is tested as a pure function with a fake NetBox client at the boundary.
- [ ] NetBox URL and token come from the environment.
