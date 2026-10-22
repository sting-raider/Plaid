# Mapped boot text extents

## Hypothesis and baseline

Implementation claim: contiguous CPU/PI-produced RAM authenticates bytes, not
their classification as instructions. Applying that entire extent as mapped
text can introduce false address-taken roots. The experiment keeps the replay
payload and virtual/physical mapping unchanged and varies only candidate text.
Base: `003be9a5f5dc90942ca19c22f094a73b02cef8b7`.

GoldenEye USA is a user-supplied local input; no ROM bytes are retained here.
Its entry stub at `80000450..800004b8` writes Index=1, EntryHi=70000000,
PageMask=007fe000, EntryLo0=0000001f and EntryLo1=00000001, then jumps to
70000510. Pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
(`ares/n64/cpu/tlb.cpp`, Entry::synchronize/load) interprets this as a global
4 MiB even half from physical zero and an invalid odd half. Mapping size does
not supply an executable boundary. The boot stub clears BSS from 8005d2e0.

The identity-backed initial image has ordinary CPU instructions through the
return at virtual 70020d84 and its delay slot at 70020d88; padding follows,
then a `1172` stream starts at 70020d90. The boot getter at 700004bc returns
the corresponding source address 80020d90. The existing generic `slot_text`
scan reaches its first invalid instruction at 70020da4 and selects the last
return plus delay slot as its candidate end (70020d8c). This is lexical
candidate evidence, not a proof that code can never exist after data.

Experiment receipts and generated analysis remain ignored under
`target/ge-extent/`; their numerical addresses are observations, never rules
or production constants. Reference source is read as an oracle, with no code
copied into the native artifact.

## Controlled result and actual cause

The baseline reproduces OPEN **338 ordinary / 327 residual**. Changing only
the mapped declaration's text size to 0x2098c removes six blocks but leaves
both blocker counts and every blocker class unchanged. That experiment refutes
text extent as the cause of the reported blocker explosion. It is not shipped.

The example switch at placed 80801674 is real code at virtual 70001674. Its
table is at fixed 80028400. The ROM boot image there still contains packed
bytes; those cannot describe the later initialized table. Independently
inflating the raw-DEFLATE stream after the two-byte 1172 marker yields 0x3c550
bytes, exactly the initialized-data span 80020d90..8005d2e0. This is a different
1172 container from the existing size-prefixed paired-stream catalog. No new
compression recognizer or assumed in-place decompression rule is introduced.

The pinned reset replay first reaches a requested switch at 70019520. Its
physical producer snapshot contains the initialized tables, matching the
independent inflation. For example, the seven words at 80028400 name aligned
7000167c/70001704/70001758 case blocks. Initially eight tables are known; their
case blocks expose another two. Ten replayed data slices supply 1024 bytes.
No RAM payload is supplied as an input or committed to git.

## Implementation contract

`ares_data` names the whole ROM, a first-fetch entry and an aligned physical
RAM slice at its fixed KSEG0 alias. Composition repeats the pinned reset replay,
checks the source extent and slices the authenticated output. It does not move
guest data or preload later bytes before boot. The base IPL preload is retained.
Data-only identity ranges reuse the existing text/data partition representation
with zero text; their declaration and content identity are rechecked. Even data
that looks exactly like a return instruction cannot authorize executable bytes.

Harvesting only repairs recognized tables whose earlier snapshot had invalid
pointers, and only when the replay supplies complete aligned words. This is
source recovery, not target closure. Existing table certificate rechecks,
native table checks/store protection and all other solver blockers remain.
Data-only loads have no executable entry, so their consuming native transfer
checks expected source bytes after guest initialization. Existing write
invalidation forces rechecking after subsequent stores. A byte mismatch faults
with code 8; actual register targets still pass through native dispatch checks.
Other source encodings or conflicting data witnesses refuse. Overlapping raw
declarations are split around the data while preserving every remaining ROM
offset and byte; mapped executable slot declarations remain unchanged.

Newly reached but unexecuted tables may use an already authenticated data
snapshot. Replay only requests that existing anchor, avoiding an unnecessary
100-million-instruction wait for a switch neutral input never uses. The native
table guard still checks any table certificate against actual RAM at its use.

After the two data refinements: **4706 blocks, OPEN 175 ordinary / 172 residual**.
All 106 invalid pointer-entry blockers disappear. Ordinary blockers are 85
unresolved direct targets, 78 unmapped targets, seven runtime callbacks, one
indirect target/site, two ERET obligations and one scope effect. Residual mode
removes the ERET/site obligations only; it still refuses emission. All 85 missing
direct destinations are in the 7f virtual engine range; those executable
sources and their paging/loader behavior are the next substantial frontier.
The mapped producer extent still includes writable data and needs refinement
before a native acceptance claim, independently of this blocker reduction.

## Verification receipts

Authored Rust contracts cover physical slice bounds/alignment/overflow,
preserved preload, data reads without instruction admission, wrong physical
sources and forged data-to-text metadata. The Python contract checks unique
virtual-use projection, exact raw source splitting, duplicate stability and
refusal of malformed, absent, unaligned or conflicting snapshots. Existing
native/reference table and TLB contracts remain mandatory in the full gate.
The authored replayed-data native fixture matches pinned ares CPU state and RAM
after guest initialization, refuses tampering before first use and after a
later write, and catches a mutation that removes the consuming-transfer guard.

The final normal ROM-only `native.py <rom> --rt64 --seconds 30` invocation,
without supplied loads, reproduces 175/172 and refuses before lowering or a
window. This is a verified partial analysis fix, not native GoldenEye acceptance.
No assumption is retired and no runtime decoder/JIT/interpreter is added.

Anchor-only replay takes **2.776 s instead of 29.903 s**, with identical capture
SHA-256 `0010444d72f264125c4dbba20fb9dbf495a3a3eef69ddf5e0d0332fe7066dfc6`.
Both timings come from actual uncached replay metadata, not cache-hit wall time.
The separate text-only experiment took 1.289 s identify, 1.146 s discover and
0.658/0.692 s solve; the final data-refined experiment took 1.601/1.461 s and
0.844/0.841 s. These are different coverage workloads, not a speedup claim.

Ignored receipts: baseline.log, probe.log (text-only experiment), data-probe.log
and data-probe2.log (data refinements), table-repair*.json, repaired-loads*.json,
and focused-data*.log under target/ge-extent. Final automatic pipelines are
final-ge*.log; visible 30-second BK/MM control results and elapsed times are in
control-bk.log, control-mm.log and controls.json. The full local gate records
each exact command, exit code and timing in gate.json and separate gate logs.
The complete synthetic `scripts/test_ares_boot.py` suite passes, including the
new first-use data contract and existing native/reference producer regressions.
