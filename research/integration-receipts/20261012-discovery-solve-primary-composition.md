# Primary composition: discovery sources at closure admission

Base: 474c9244869f11b5b2d346282ab8aeb0c76c0d24. Claim: 6112923011.
Source: research/evidence-manifest-composition-gpt56sol at
31ca1f778f3b0ac2161a676eb2944437fbc74757; canonical ADR-0113 and closeout
6112621231. This composes already integrated APIs, not another isolated consumer.

Hypothesis: external source-set expectations, complete primitive replay and the
stronger ROM-aware installed-entry projection must all succeed before closure
admission. The original trace-import known images can differ from solver image
witnesses, so keep their contexts separate. The emitted report preserves source
expectations and the canonical validated-map SHA256; it never recreates trusted
expectations from the submitted artifacts.

Five focused tests pass: legitimate declared-static CLOSED/whole-ROM OPEN,
deleted raw negative facts plus diagnostics, installed-entry deletion that passes
primitive-only authentication, merged two-session negative evidence with whole-
session deletion and order-independent output, and wrong ROM/unexpected sessions.
The deleted-store regression demonstrates ordinary finite-static solving becomes
CLOSED after raw facts/diagnostics are removed; the source-bound API rejects.

CLI integration passes source/report workflow, create-once expectations, input
protection, edited/extra/missing source rejection, raw primitive deletion and
installed-entry deletion. All previous CLI byte-order/map/identity cases pass.
Mandatory fmt check, strict locked workspace/all-target Clippy, full locked
workspace including the actual outer fixed-point adversary, CLI and diff checks
PASS locally on the exact base. Logs: target/discovery-solve-primary (ignored).
No Actions, workflow scaffolding or redundant reference builds. No hardware
semantics changed, so retained canonical source contracts are sufficient.

No helper flags waive proof obligations. This authenticates modeled raw discovery
primitives and installed entries, not every compiled/derived projection or other
source domains. Complete mutation/root/executable-lifetime census and whole-ROM/
native readiness remain OPEN; progress milestones unchanged. ADR-0114.

User ROM baseline: external local file, 33554432 bytes, big-endian, header country
E/version 2. Canonical SHA256
49acd3885f13b0730119b78fb970911cc8aba614fe383368015c21565983368d.
The explicit conditional ROM window 0x1000..0x101000 at guest 0x80000400 found
293 blocks, 45 indirect sites and 11 importer unresolved items. Whole-ROM solve
is OPEN with 62 blockers, including 44 unresolved indirect sites. This is a
conditional static baseline, not actual boot/mapping or whole-game coverage.
Bytes, maps and reports remain outside git / in ignored artifacts. No game code
or copyrighted trace contents are included in this receipt.
