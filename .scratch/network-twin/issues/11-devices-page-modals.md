# 11 — Devices page + uplinks/clients modals

**What to build:** the Devices page of the dashboard: a list of devices (merged status) from the shared core, with a per-device "show uplinks" button (gated on `appliance` product type) and a "show clients" button, each opening a modal rendering plain tables from the shared core.

**Blocked by:** 09 — dashboard shell + auth, 03 — state read mirror: networks + devices, 04 — state read mirror: uplinks, switchports, vlans, topology, clients.

**Status:** ready-for-agent

- [ ] The Devices page lists devices with merged status and `as_of`.
- [ ] "Show uplinks" opens a modal with that device's uplink table; the button only appears for appliance devices.
- [ ] "Show clients" opens a modal with the device's recently-seen clients, flagged ephemeral.
- [ ] The page renders from the shared core; no data logic lives in the view.
- [ ] The page is only reachable when authenticated.
- [ ] Views are tested thin through TestClient (gating + render, not logic).
