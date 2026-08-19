# 04 — State read mirror: uplinks, switchports, vlans, topology, clients

**What to build:** the rest of the state read mirror, bearer-protected: list/get for uplinks, switchports, vlans, topology, and clients — with network-scoped variants — all carrying `as_of`. Client responses are explicitly flagged as ephemeral (recently-seen in the ~1h30m window), and a client's device fields are presented as "the device that most recently reported it," not a definitive home.

**Blocked by:** 03 — state read mirror: networks + devices.

**Status:** ready-for-agent

- [ ] Uplinks, switchports, vlans, and topology endpoints return trimmed state with `as_of`.
- [ ] Clients can be listed (by network, switchport, ip, vlan, user/hostname) and fetched by normalized mac.
- [ ] Client responses carry an explicit ephemeral/recently-seen flag.
- [ ] Network-scoped variants of the endpoints work.
- [ ] Every response carries `as_of`; all endpoints require bearer auth.
- [ ] Each projection is tested through the REST seam with the in-memory ES fake.
