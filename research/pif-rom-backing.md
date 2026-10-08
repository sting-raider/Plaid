# PIF ROM backing provenance

Date: 2026-10-08  
Plaid base: `3cf45dc323cbcd9e6463ccc781d3de093a433097`  
Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`  
Verdict: **PARTIAL**

## Question

Can the CPU's natural PIF boot fetches be assigned exact supplied-firmware byte
origins without mistaking SI/PIF side effects or aliases for backing reads?

## Result

Yes for a narrowly defined **successful backing-read witness**, but not from the
existing fetch record alone.

Pinned ares has four independent facts that make address/value inference unsafe:

1. the N64 bus routes the full physical `0x1fc00000..0x1fcfffff` interval to SI;
2. PIF masks delegated addresses with `& 0x7ff`, creating many physical mirrors;
3. SI may return `io.busLatch` before PIF is touched;
4. PIF may return lockout zero or PIF RAM without reading firmware.

A successful firmware witness therefore has to be generated at the actual
unlocked `PIF::readInt -> rom.read<Word>` branch and joined to the **same CPU fetch
context**. The existing debugger fetch observation is too late to originate that
context: `CPU::instruction()` calls `fetch(access)` before `instructionPrologue`.

The independent deterministic harness in
`experiments/pif-rom-backing/witness_model.py` constructs equal-value and alias
counterexamples, then fuzzes the exact source-selection predicate. At 1,000,000
iterations it observed 92,583 positive ROM reads, 907,417 negatives and 92,426
positive mirrored-address reads with no assertion failure. Value-only and naive
physical-delta source inference are both explicitly falsified.

## Required evidence contract

A future reference sensor should carry a temporary fetch ID from immediately before
`CPU::fetch(access)` through bus/SI/PIF delegation. Only a successful PIF ROM
backing read may attach:

- fetch ID;
- guest PC / fetch access;
- actual post-endian physical address;
- masked PIF ROM offset;
- returned word;
- PIF-ROM source kind.

No source witness is emitted for SI `ioBusy`, ROM lockout, PIF RAM, cached
non-RDRAM rejection, or unrelated PIF DMA/HLE reads. Production import must also
recheck the word against the explicitly supplied 1,984-byte firmware input and
its declared SHA-256.

This event proves one fetch's byte origin. It does **not** prove firmware
authenticity, boot equivalence, immutable lifetime, complete boot coverage,
exception/TLB closure, or native completeness.

## Evidence and reproduction

Run:

```sh
python3 experiments/pif-rom-backing/witness_model.py --fuzz 1000000 > /tmp/pif.json
python3 -m py_compile experiments/pif-rom-backing/witness_model.py
```

Expected deterministic counts: `92583` positive, `907417` negative, `92426`
mirrored positive. Expected harness SHA-256:
`4b35066e8bfc6e2bfc9064bba38e2ecb6ec4a199ca6bf112f6fc63677eaab036`.
Expected JSON SHA-256:
`0fc0d77daa8b3c745eba67d40954a7ec7a7b253370527c55f98abf1270f09476`.

A local real firmware can be supplied with `--firmware`; the harness requires the
same size/hash already recorded by Plaid's boot-input research and does not emit
its bytes.

## Remaining gap

This worker could inspect the exact pinned upstream source but could not obtain a
full upstream checkout/build in the execution environment. The new hook therefore
has **not** passed instrumented-vs-uninstrumented ares neutrality or a real boot
capture. That is the next bounded experiment before any ProgramMap/trace schema
promotion.

Recommendation: **PRIMARY-INTEGRATOR-REVIEW**, then a small follow-up actual-ares
instrumentation run if this evidence contract is accepted.
