# Reuse a CFG index during tail-cell verification (ADR-0342)

Tail-cell analysis adds candidate destinations before checking whether every
prefix and target still agrees with its evidence. For a map with one indirect
record per address, subsequent updates only change proof labels. The existing
index remains valid for those checks, including revocation of older proofs.
Maps with multiple records at an address still rebuild the index and recheck
after the updates.

Three paired Paper Mario discovery runs used the same retained load and
runtime declarations. The median combined tail-cell phase went from 0.499 s
to 0.337 s against the ADR-0341 release binary. All six serialized maps matched
byte for byte, including candidate edges and stale proof handling. Reusing
the certificate alone measured 0.479 s to 0.474 s, too small to establish a
useful gain by itself. These numbers are for the phase, not a cold build.
An authored test revokes an existing proof when a new entry bypasses the
load, with one record and with two records at the same address.

This is reuse inside one analysis pass. General per-round table proof reuse
still needs a read set that accounts for failed queries and changed roots.
