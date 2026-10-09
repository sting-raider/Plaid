# Guest software-interrupt producer experiment

This bounded research experiment composes Plaid's already-validated maskable
interrupt root/gate result with the guest-writable portion of VR4300 CP0 Cause.
It does **not** change production Plaid or claim whole-ROM closure.

## Question

Can reachable guest software independently make the ordinary interrupt vector
reachable by writing Cause.IP0/IP1, even after all external device interrupt
producers have been excluded? Can the same write alter hardware-owned pending
bits IP2..IP7?

## Exact references

Pins are taken from `refs.lock.toml`:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`

`source_guard.py` also binds the exact source blobs containing the relevant
Cause-write semantics.

## Dynamic discriminator

`driver.cpp` boots the exact pinned unmodified ares interpreter with recompilers
disabled. At uncached KSEG1 address `0xffffffffa0000000` it installs:

```text
MTC0  $t0,$13               # actual guest write to CP0 Cause
ADDIU $s0,$zero,0x1234      # must not retire if the new pending bit is eligible
NOP
```

The harness presets only the requested starting CP0 state and `$t0` payload.
It executes one `CPU::instruction()` boundary and records the completed guest
Cause write. It can then change only the interrupt mask for clear/preserve
adversaries, and executes a second boundary. Interrupt entry is distinguished
causally from ordinary execution by PC, `$s0`, EPC, Cause.ExcCode/BD and EXL.

Cases cover:

- software IP0 and IP1 independently and together;
- both BEV vector bases;
- attempted writes to hardware IP2..IP7;
- mixed software/hardware payloads;
- software clear before later mask enable;
- same-value set and same-value clear writes;
- preservation of preexisting IP2/IP7 under hostile Cause writes;
- replacement of software IP bits while hardware IP remains pending;
- zero/disjoint masks, IE=0, EXL=1 and ERL=1.

Every dynamic case runs twice in a fresh headless system and must produce
byte-identical JSON.

## Independent adversarial model

`model.py` exhaustively checks every 8-bit initial pending state against every
16-bit Cause payload. Its only ownership rule is:

```text
new_ip = (old_ip & 0xfc) | ((cause_value >> 8) & 0x03)
```

It separately exhausts all 8-bit pending/mask combinations and IE/EXL/ERL gate
states. Same-value final states remain counted as operations rather than being
interpreted as proof that no write occurred.

## Reproduce

With the three exact references checked out beneath `.refs/`:

```bash
python3 experiments/ares-sw-interrupt-producer/source_guard.py
python3 experiments/ares-sw-interrupt-producer/model.py
python3 experiments/ares-sw-interrupt-producer/run.py
sha256sum target/ares-sw-interrupt-producer/model.json \
  target/ares-sw-interrupt-producer/results.json
```

The branch-only workflow `.github/workflows/research-sw-interrupt-producer.yml`
performs the same exact-pin build/run and uploads both JSON reports.

## Scope limits

This experiment does not prove device producer reachability, asynchronous timing
at arbitrary pipeline/delay-slot positions, physical hardware conformance of the
executed emulator, handler-byte provenance, executable lifetime, or whole-ROM
closure. It specifically tests software Cause ownership plus composition with the
previously validated architectural interrupt gate/root.
