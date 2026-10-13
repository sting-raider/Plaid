# Reset producer candidate: source binding required before composition

Reviewed against canonical main35f529b9f9d51f08a8a8a3fb31527f9e4aa5178d,
2026-10-13. Prepared PR39 branch
`direct-integration/reset-producer-identity-gpt56sol-b9`,
head3112e7585303af9dd81ae95997714ee0d9124f55.
Candidate module blob:efcef8a5c2ec6b026766d72767239caa9df1c2e9;
canonical module bytes SHA256:
5138cca8857ecd5bebdcb923110a7379e3738a0ebe3ed7ebc0cfba4673171276.

Read the candidate receipt and referenced reset/HW2/NMI research. Its portable
occurrence invariants are useful: fresh request/event IDs, one-shot delivery,
explicit supersession, imported ancestry unknown, and no universal accumulating
or coalescing policy. The pinned Mupen/Gopher policy disagreement remains open.
These facts do not supply authentication of the producing capture or a join to
the actual ares NMI transfer/first-fetch clock.

Local exact-module reproduction compiled the prepared Rust module unchanged in
an ignored standalone Cargo project. Supply the well-formed all-zero 64-character
`capture_sha256` and three invented records:

```json
[
  {"kind":"request","ordinal":1,"request_generation":99},
  {"kind":"produce","ordinal":2,"event_generation":7,"request_generation":99,"delivery_kind":"nmi","schedule_value":123},
  {"kind":"deliver","ordinal":3,"event_generation":7,"delivery_kind":"nmi"}
]
```

`verify_reset_producer_history` accepts them and returns
`producer_identity_certified:true` for delivery7/request99. No raw capture bytes
or independently expected digest are arguments; the hash is checked only for
syntax. Thus this is verification of caller-declared occurrence algebra, not a
source-authenticated producer receipt. The reproduction ran twice with identical
output SHA256:
06730f23a3cb328e24ddd64e41685ac91f381dc9aadbd50f4c945d38914bab60.
Local source, command project and report: `target/reset-producer-primary-review`.
This is a candidate boundary probe, not an emulator or hardware observation.

Decision: retain PR39 as preparation needing reconciliation; do not import its
source-certification flag or create another disconnected producer consumer.
Canonical `root_provenance` already authenticates actual supplied source and
firmware bytes against separately expected digests, reconstructs transfer/
pending/fetch/read relationships, and keeps producer lifecycle false. The
canonical cache/root consumers likewise cannot borrow request labels from this
other clock. Later composition needs an authenticated complete producer capture
with actual creation/consumption identity and an explicit same-source join to
transfer, deassertion, first fetch and executable generation. Imported/restored
events remain unknown without an independent epoch contract.

No production code or proof flags changed. No duplicate reference rebuild,
Actions, copyrighted assets, raw research branch merge or hardware-policy vote.
The candidate branch and research evidence remain available.
