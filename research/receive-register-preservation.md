# Saved register effects of message receive

A native message receive can block and return through a scheduling handoff.
The runtime saves the thread's register state, restores it before resuming the
host continuation, and writes the receive result to the ordinary result
register. A call effect now retains only the eight saved registers ($s0–$s7)
for this runtime declaration. The effect still requires a fixed source
binding and includes the declaration in the regenerated witness.

The unit contract checks the precise register set, budget and slot guards.
The native scheduler fixture records all eight registers after a blocking
receive while another thread holds different values. The fixture checks
single-unit and multipart lowering, queue handoffs and stale-source refusal.

Use the local replay-authenticated RE2 load catalog described in
large-rsp-registry.md. With this effect in analysis the map adds the
eight candidate entries for the indexed jump at `80088194`. The residual
site list still contains that address, and the build stays
`native_complete: false`. The visible run advances from VI 254 to VI 309,
with 43 PI transfers, and stops at fault 12 during CACHE at `80135cc0`.
It still produces zero graphics tasks. The next fault requires diagnosis
of the modeled CP0 state at that operation.
