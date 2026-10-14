# Primary integration: physical PI storage writers feed executable consumption

Base:85fbcdf1e67d703991efe7950b1821179593ade5. Claim:6158183575.
Reuse the existing PI buffer/attempt/return state and v5 storage clock, rather
than a separate provenance policy. Current main reproduced the conservative gap:
four completed translated primitives without identity wrappers remained unknown.

An immediate, unique completed Byte primitive now supplies the actual physical
sink and original writer occurrence within an authenticated PI attempt. The
returned buffer lane still needs its separately observed canonical ROM parent.
Defer selection until the synchronous attempt returns; no fetch may intervene.
Normal successful wrapper writes retain their distinct writer ordinal. A physical
sink disagreement, duplicate/interposed primitive, wrong PC/payload/width or bulk
cut inside a byte attempt rejects. Missing/before-attempt effects and unobserved
ROM origins stay unknown; matching values alone never restore ancestry.

Exact pinned ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04 executes three actual
PI I/O requests: identity, translated and failed translation. Identity emits eight
storage primitives plus eight wrappers. Translation emits eight physical
primitives and no identity wrappers. Failure emits neither. Returned ROM halves
and immediate attempt/effect/return order are checked. The two successful copies
feed actual decoded CPU execution at separate physical destinations after an
explicit host mapping control. Eight full ordinary/hidden RAM hashes plus selected
GPR/PC/CP0/PI checkpoints agree across baseline, disabled, enabled and repeated
controls; the110-event source repeats exactly. No guest-MMIO, guest-mapping,
queue-completion, hardware-timing or whole-machine coverage claim follows.

Focused27 PI-history Rust tests and two complete physical-writer CLI/independent
model graphs pass, retaining ten malformed-attempt and six missing-origin
controls. The earlier six storage/cache graphs also pass. Initial synthetic
address adapters were corrected to include virtual, translated and bus addresses;
an ineffective zero-byte adversary now flips the actual byte. The reference
fixture's duplicate-main include was corrected before successful controls.
No assertion, lint or proof obligation was waived.

Actual source SHA-256:
25538212ce99dc8afb0e58c57392657cb267a6083bf3581d3a537b3139de24c7.
Baseline/disabled SHA-256:
06a9e993b796d87985410603b06937f4a11af448b55001a4d1e9efd92403ed5f.
Reference receipt SHA-256:
4b680fb4cf784698b54a476e34d9c7c584bf1c3a72a7c9cf8786072cc8978156.
Both executable and build-manifest digests are pinned in that receipt. Rechecking
the retained controls after strengthening source-half assertions requires no rebuild.

The complete authenticated69,513,732-record source from the preceding integration
is reused. A full streaming delta check pins its original SHA-256 and canonical
report SHA-256, checks all1,048,576 PI attempts and proves each still selects its
same wrapper writer. Its1,978,805 other storage effects retain the original cut
semantics. The new physical-parent branch is never selected on that source, so
the earlier complete canonical/independent result remains applicable; it is not
claimed newly re-emitted. The two-checker regression rejects changed physical
parents, malformed intervals and source edits. Actual evidence and final digests
are retained under target/pi-storage-executable-primary and the issue4 closeout.
Delta receipt SHA-256:
18525f270b5e517a7de2163afa9ce307c56d3e7e8c1a2f5185e8ff26a48edff0.

Final canonical gate, expected-head CAS and fetched verification belong in the
closeout. STATUS/NEXT/DEVELOPMENT/ADR0124 change only for the adopted composition;
progress stays unchanged. Reference code/notices and synthetic/native artifacts
stay ignored. No Actions or ROM/assets enter Git. General mutation/mapping/cache/
root/epoch coverage, whole-ROM closure and native execution remain OPEN, all broad
flags false.
