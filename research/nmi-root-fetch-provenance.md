# NMI root transfer is not root-byte execution provenance

Status: **VALIDATED (bounded exact-pinned-ares composition)**

Date: 2026-10-09

Plaid canonical base inspected before claim: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Research branch: `research/nmi-root-fetch-provenance-gpt56sol`

Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`

## Question

Plaid already had two independently useful facts:

1. the exact-pinned-ares external-NMI path transfers the architectural CPU PC to
   `0xffffffffbfc00000`, records ErrorEPC, and does not clear `nmiPending`; and
2. an uncached PIF-window fetch can receive PIF-ROM byte provenance only from an
   actual PIF-ROM backing read within the same fetch context.

This experiment asks whether those facts may be composed by saying that an NMI
root transfer to `0xffffffffbfc00000` proves execution, or even byte provenance,
of the PIF instruction at that address.

They may not.

## Falsifiable hypothesis

In the pinned ares interpreter, `CPU::instruction()` checks `nmiPending` before
address translation/fetch. An asserted level calls `exception.nmi()` and returns
from the instruction function. The NMI path sets the architectural PC to
`0xffffffffbfc00000` but does not consume the pending level.

Therefore:

- after one NMI call the CPU may be at the correct root with **zero root fetches**;
- if `nmiPending` remains asserted, the next instruction call may re-enter NMI
  with **zero root fetches again**;
- if the level is explicitly cleared, a later instruction call can fetch and
  execute the root word, but its byte source must still be proved by the actual
  source path rather than root address or value equality.

A counterexample in which the persistent pending case fetches the root, or in
which an equal SI latch/foreign PIF read can acquire the root's PIF-ROM witness,
would reject this hypothesis.

## Exact-source guards

The successful exact-pin execution guarded these source files:

| pinned ares source | SHA-256 |
| --- | --- |
| `ares/n64/cpu/cpu.cpp` | `65cd30ce6e04a8799f6c50f07cc8dec13e55122bd8d5fea23e99e3e6734214f1` |
| `ares/n64/cpu/exceptions.cpp` | `e24b2877fb5d629ca3f10f64dba9a612babb879c53ed142b42557920f216ffa7` |
| `ares/n64/pif/io.cpp` | `9bc87b9353a5b9c52f1b4b609aba4858e4a257f4a82d7007aee908a7faa2b86c` |
| `ares/n64/si/io.cpp` | `6b63ba45c11d9242794aa211a8ee17ee742a4d8f348486a7a0c25382fca411ca` |

The guarded CPU source places the NMI branch before
`devirtualize<Read, Word>(ipu.pc)` and returns immediately after
`exception.nmi()`. It contains no CPU-side `scc.nmiPending = 0`. The guarded
exception path selects `0xffffffffbfc00000`.

The PIF observer is the already validated fetch-scoped backing-read mechanism:
it opens a context around the actual CPU fetch and emits a PIF witness only from
the successful ROM-read branch. SI busy-latch and PIF lockout paths do not pass
through that ROM read.

## Executable fixture

Artifacts:

- `experiments/nmi-root-fetch-provenance/driver.cpp`
- `experiments/nmi-root-fetch-provenance/run.py`
- `experiments/nmi-root-fetch-provenance/model.py`
- `experiments/nmi-root-fetch-provenance/README.md`
- branch-only `.github/workflows/research-nmi-root-fetch-provenance.yml`

The driver uses the actual pinned ares CPU instruction path with CPU/RSP
recompilers disabled. It begins from synthetic interrupted PC
`0xffffffffa0000104`, asserts `nmiPending`, and executes one real
`CPU::instruction()`. Every scenario therefore first reaches the validated NMI
root. It then either stops, leaves the level asserted for another instruction,
or clears it and executes one root instruction under a controlled source-path
adversary.

The instrumented build is generated from the existing PIF backing fixture. A
separate uninstrumented build is executed for every scenario, and complete
reported machine projections are required to agree. Every instrumented scenario
is also repeated byte-for-byte.

Successful Actions run:

- run: `37969823321`
- job: `113953292508`
- tested commit: `c03984356572e84191cb0b214f8e586b829f6a22`
- result JSON SHA-256: `3d91505e3afc53c98a6cce3eced35dd1219750c7cfacd80bec0d3b909f326f0e`
- artifact: `11635725748`
- artifact ZIP SHA-256: `27aaa75f38fc3cc482ae0f2007fdc7227d3afaf0cdaae8c276e4ca069dc705da`
- supplied NTSC PIF firmware SHA-256:
  `fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd`

The independent chronology model also passes and rejects seven forged histories.
Its deterministic report payload hash is
`2c15ad692cd6927e146c2ab306c47f7158c418d2a52b1d0356a91cd4198cb900`.

## Deterministic observations

All first NMI calls reached `0xffffffffbfc00000`, retained `nmiPending=1`, and
recorded ErrorEPC `0xffffffffa0000104`.

### 1. Root transfer without root execution

`transfer_only` stopped immediately after NMI:

- architectural PC: `0xffffffffbfc00000`;
- root fetches: 0;
- PIF backing reads: 0.

This is the minimal counterexample to `root transfer => root bytes executed`.

### 2. Persistent level repeatedly preempts fetch

`persistent_two` called `CPU::instruction()` again without clearing the level:

- architectural PC remained `0xffffffffbfc00000`;
- root fetches remained 0;
- PIF backing reads remained 0;
- the second NMI overwrote ErrorEPC with `0xffffffffbfc00000`.

Thus the pending level is not a unique completion/event token, and being parked at
the root across multiple instruction calls still proves no root instruction was
fetched.

### 3. Clearing pending permits a source-witnessed root fetch

`clear_fetch` cleared `nmiPending` after the NMI transfer. The next actual
instruction call recorded:

- virtual PC: `0xffffffffbfc00000`;
- physical address: `0x1fc00000`;
- cache policy: uncached;
- returned word: `0x3c093400`;
- one actual PIF-ROM backing read;
- witness: `pif_rom(offset=0, word=0x3c093400)`;
- architectural PC after execution: `0xffffffffbfc00004`.

This is the positive composition: root transfer and root-byte execution are
separate events, and the latter obtains provenance from the actual fetch/backing
chain.

### 4. Equal payload does not imply PIF provenance

`clear_busy_equal` deliberately placed the exact firmware word `0x3c093400` in
the SI bus latch. After the NMI level was cleared, the root instruction fetch:

- returned `0x3c093400`;
- executed and advanced PC to `0xffffffffbfc00004`;
- recorded **zero** PIF-ROM backing reads;
- carried **no** PIF-ROM witness.

Pinned SI source also force-finishes the busy state on this read, so post-read
`ioBusy` is zero. The initial CI attempt incorrectly expected the pre-read busy
flag to remain set; that harness-only assertion failed. Source inspection showed
the explicit `writeForceFinish()` side effect, the assertion was corrected, and
the unchanged semantic experiment then passed. The failed run is retained as a
harness diagnostic rather than evidence against the hypothesis.

This case is stronger than a value-collision warning: the CPU genuinely executes
a root-address word whose value exactly equals the firmware word while its actual
source is the SI latch, not PIF ROM.

### 5. Lockout can execute a non-ROM root value

`clear_lockout` cleared NMI pending but enabled PIF ROM lockout. The root fetch:

- occurred at the same virtual/physical root;
- returned zero;
- recorded zero PIF-ROM backing reads;
- carried no PIF-ROM witness;
- advanced the PC after executing that returned word.

Therefore root-address identity alone does not even prove which source branch
provided the executed root word.

### 6. A foreign real PIF read cannot be recycled

`foreign_read_then_persistent` performed a real PIF ROM read before NMI, then
left the NMI level asserted:

- PIF backing reads: 1;
- unattributed backing reads: 1;
- root fetches: 0.

The real, equal-source read does not become provenance for the later architectural
root merely because the CPU reaches the same firmware root address.

`foreign_read_then_clear_fetch` then provides the positive control:

- total PIF backing reads: 2;
- one remains unattributed/foreign;
- the later root fetch gets its own in-context PIF witness.

## Adversarial model

`model.py` accepts only a chronology containing all of:

1. NMI architectural transfer to the root;
2. explicit pending/deassertion state permitting fetch;
3. root fetch-begin context;
4. same-context PIF ROM read at offset zero;
5. matching root fetch completion sourced from that PIF ROM read.

It rejects seven alternatives:

- root transfer only;
- repeated persistent-NMI re-entry;
- earlier equal-valued foreign PIF read;
- forged fetch while pending remains asserted;
- equal SI-latch payload;
- PIF read from a different context;
- PIF read from the wrong firmware offset.

## What prior work this composes or challenges

This composes:

- `research/nmi-root-contract.md` on `research/nmi-root-gpt56sol`, which proves
  the bounded architectural NMI root but explicitly leaves event/latch lifecycle
  unresolved;
- `research/bounded-boot-pif-history.md`, which proves actual fetch-scoped PIF-ROM
  backing witnesses in a finite boot prefix;
- reset/cache lifetime research, which keeps reset/NMI/cache/backing lifetimes
  distinct;
- exception-root-generation research, which independently shows that architectural
  exception-vector identity must be separated from executable-generation identity.

It challenges a tempting composition shortcut that would promote a known root PC
plus known firmware contents into an executed executable image without observing
or otherwise proving the intervening fetch/source lifecycle.

## Closed-world impact

A whole-ROM root certificate needs at least three distinct facts for reset/NMI:

1. **architectural root-transfer identity**: the transition selected
   `0xffffffffbfc00000`;
2. **root fetch/execution occurrence**: control actually progressed beyond the
   transfer rather than being repeatedly preempted by a persistent event level;
3. **executed-byte source/generation identity**: the root fetch was supplied by a
   particular backing/source path, such as the actual PIF-ROM read, not an equal
   SI latch, lockout value, stale foreign read or value match.

Proving (1) must not silently discharge (2) or (3). If event-latch lifecycle is
not modeled strongly enough to prove progress to a root fetch, or if the root
fetch lacks source evidence, the corresponding executable-root obligation stays
OPEN/UNKNOWN.

This matters even though the N64 normally boots from PIF ROM: the certificate is
supposed to justify the executable universe from evidence, not from a familiar
address and a reassuringly identical 32-bit value.

## Limitations

- This is bounded exact-pinned-ares interpreter evidence, not physical N64 timing
  or electrical reset-button proof.
- The harness directly clears `nmiPending` for the positive post-transfer cases.
  It therefore proves the fetch/provenance distinction, not the real hardware or
  full emulator producer/deassertion mechanism that should clear/consume NMI.
- Existing reference disagreement over reset/NMI Status.SR remains untouched.
- It does not prove reset-button HW2 timing, simultaneous interrupt+NMI ordering,
  complete PIF/HLE producer lifecycle, save-state behavior across NMI, or every
  possible root source/device state.
- It establishes one required certificate composition rule. It is not a complete
  whole-ROM root verifier or executable-lifetime proof.

## Reproduction

With `.refs/ares` checked out exactly at
`9408cb43d4948fc3ea6e152a307a34348df3fe04`:

```sh
python3 -m py_compile experiments/nmi-root-fetch-provenance/{model.py,run.py}
python3 experiments/nmi-root-fetch-provenance/model.py
python3 experiments/nmi-root-fetch-provenance/run.py
```

## Integration recommendation

**ADOPT the invariant, not the research branch wholesale.**

Represent root transfer, root fetch/execution, and root executable-byte
provenance as separate evidence obligations. For reset/NMI, do not create a PIF
root image/generation merely because PC became `0xffffffffbfc00000` or because a
word equals supplied firmware. Require an actual source-bound fetch or an
equivalent independently recheckable causal witness. Persistent/ambiguous NMI
lifecycle must keep fetch occurrence OPEN rather than fabricating progress.
