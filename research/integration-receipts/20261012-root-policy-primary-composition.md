# Primary composition: explicit target hardware policy and numeric root selection

Base: 96337129f2bb6826ade7099fbe0292a6e43baa56. Claim: 6116115342.
PR #16 @ c6544c25f76297e5bc2ee293424920ecc0017bec; source research
cache-error-root-sol @ c52bf1845d89629116ce36fc0023260fe0c7635a.

Reconcile the target-scoped exclusion and connect it to canonical general/TLB
vector selection through classify_execution_root. Numeric candidates and
hardware-excluded classes remain distinct, fully rechecked results. Only the
explicit Nintendo64Vr4300 target receives the reviewed vector/exclusion rules;
generic MIPS III stays unresolved. Existing root APIs and gates are unchanged.
No handler-byte/reachability/census/lifetime/native certification is inferred.

Primary basis: NEC U10504EJ7V0UM00 / cover U10504EJ7V0UMJ1, seventh edition.
Appendix B.1.7/Table B-1, printed p632, and chapter 6.3.11/p178 were checked in
the original manual PDF. [Manual mirror](https://hack64.net/docs/VR43XX.pdf#page=632).
The source note's chapter-4 register reference is corrected here to chapter 6.
No emulator observation or missing callback substitutes for this hardware fact.

Retained actual two-BEV result SHA256:
87556a786d87fb5f812d267452fc0436b26a0e8b5bf04b0efe33aeae846afb3b.
Both leave CacheErr/readback zero, EXL/ERL clear and Cause/EPC/ErrorEPC sentinel
state unchanged, ending after the ordinary guest sequence. Four source Git
objects match the recorded hashes and are clean at exact ares/systemtest/Gopher
pins. The original model replays with SHA256:
aa7acaef54e2cb9965aff90aee1bedef8d25e5890e31a8be831ee0500f3124e3.
Its single-class closed flag is not imported as whole-ROM/root-universe closure.
No emulator rebuild or Actions execution was needed.

LOCAL PASS six focused policy/class/authority/unknown-field/target/lifetime
regressions, including all 24 canonical numeric vector combinations; retained
actual/model/source checks; fmt, strict locked workspace/all-target Clippy,
full locked workspace including actual outer fixed-point deletion adversary,
canonical CLI and diff. Ignored logs/evidence under target/root-policy-primary.
ADR-0122, STATUS/NEXT updated; no milestone change.

Superseded: PR #16 prepared standalone exclusion surface and duplicate production
recommendation, now composed with existing root selection. No branch workflow,
manual text or upstream implementation imported. Numeric vectors still require
independent classification/BEV/EXL/mode histories and handler source/lifetime.
Watch's CACHE-access exclusion is a separate obligation, not a cache-error fact.
Reset/NMI/interrupt/watch/full roots and whole-ROM/native closure remain OPEN.
