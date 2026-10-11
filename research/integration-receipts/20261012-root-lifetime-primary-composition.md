# Primary composition: cached exception-root ancestry and lifetime

Base: de7ee6ad7fb7ee6bce3cca5ddc728882514dbdbf. Claim: 6112998526.
Prepared PR #25 / direct-integration/exception-root-residency-gpt56sol-20261011
at fc928de9816a70039a37f5de1f559096b500c0a1, closeout 6111020547.
Source research: exception-handler-cache-compose-gpt56sol at
a88fd5d30d6bad854ed371b21576d09e4c382278, closeout 6097352137.
Canonical root-generation and reset-cache modules remain authoritative.

Adopt the slot-replacement invariant into the existing root consumer. Preserve
its v0 restricted word policy and output shape. V1 uses completed full 32-byte
fills and a fixed identity-RDRAM/reference profile. All eight captured fill words
are checked against their own supplied backing writers; a missing writer stays
unknown. Any fill replaces the entire direct-mapped slot. The captured physical
line remains distinct from slot identity. A later same-value writer cannot repair
missing fill-time ancestry. Root selection and current backing remain separate
from resident executable-byte provenance.

Compose canonical reset-cache effects in that same observed root chronology via
one shared pinned rule: NMI preserves both domains, system reset clears cache,
full power clears both. Restore is rejected. This strengthens composition of
already integrated facts without adding another isolated consumer or granting a
solver/native waiver. The pinned profile is reference-specific, not hardware truth.

Eight focused composition tests PASS: equal-value 0x4180/0x180 slot replacement
and fresh rebind; nonconflicting fill plus index invalidation; stale-root NMI,
reset/refill and full-power missing-ancestry sequence; wrong-lane writer and
non-root-lane payload forgery; fresh equal-value full-line refill; v0/v1 format
separation; mapping/profile/lifecycle/restore adversaries; complete-source and
report tampering. Ten retained root and twelve reset tests also PASS.

Exact ares HEAD 9408cb43d4948fc3ea6e152a307a34348df3fe04 and relied-on files are
clean. Exact Git-object SHA256 values checked against the retained source receipts:
- cpu/cpu.hpp: 6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27
- cpu/cpu.cpp: 65cd30ce6e04a8799f6c50f07cc8dec13e55122bd8d5fea23e99e3e6734214f1
- cpu/exceptions.cpp: e24b2877fb5d629ca3f10f64dba9a612babb879c53ed142b42557920f216ffa7
- rdram/rdram.cpp: 5658c564640bf77f785a702378f92272771286a8ddb5079c286a6796fdeccc88
- system/system.cpp: 7bc1292bf167a45a66ce7069998fced1af332949b22aef37722e8e10c4bb7154
Paths are under ares/n64. Source shows virtual index >>5 &0x1ff, separate tag,
full eight-word fills, unconditional I-cache power, reset-preserved RDRAM, and
NMI without cache/RAM reinitialization. Retained measured stale-handler receipt
9715f83c898ae315ff2be8ed95c19dbf3019e6cd44953f6eec9fabe1d5577dd8 and canonical
root/reset integration receipts suffice; no duplicate emulator build. The new
composed test chronology is synthetic, not a claimed fresh combined emulator run.

Mandatory fmt, strict locked all-target workspace Clippy, full locked workspace
including actual outer fixed-point deletion adversary, CLI and diff checks PASS
locally. Logs: target/root-lifetime-primary (ignored). No Actions/workflows,
upstream code copying, raw research merge or progress milestone change.

PR #25 and overlapping root-residency candidates are superseded by the reconciled
canonical API; research retains source/specification value. V0 still rejects
non-root events; v1's broader primitive contract is explicit. All census/lifetime/
reachability/native flags remain false. Actual source/event capture authentication,
writer completeness/ultimate origin, delivery-to-first-fetch joins, aliases/TLB,
restored epochs, root universe and whole-ROM/native completeness stay OPEN.
