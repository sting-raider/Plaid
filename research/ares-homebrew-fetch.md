# Broader raw executable observations

2026-10-08. ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`; test source
`196f5421173220eb2f63a7a99c64795dc0ea0698`; original ROM hash
`629f908c200bbf21013dcd1d331d4ddedd08a6c9d7ae1f528421564238056e8a`.

Hypothesis and reproducible commands are in `spikes/004-ares-fetch/README.md`.
The headless interpreter starts at a declared synthetic SP IPL3 entry with guest
ROM bytes copied into SP, r22=0x3f and reference power state. It uses no PIF firmware,
ELF metadata or game-specific symbol inputs. The debugger sees the exact fetched
word before execution; a generated const accessor exposes it without altering
instruction code. Its observer reads no guest memory and performs no translation.

At five million instruction calls the observer records 4,999,998 fetched words,
52,424 distinct RAM, 548 SP and 65 cartridge addresses. Every direct cartridge
word matches its canonical ROM offset. Repeated 465,553,451-byte streams have
SHA-256 `2657fb26ab09059050e6d2a23e6c7e984f3ece26544db994c7fcf3a9a5abb78c`.
Plain/traced/repeat state agrees in GPR/HI/LO/PC/Count, exception/EPC, RAM/SP
hashes, RDRAM/PIF configuration and guest message bytes. Verification streams
records rather than constructing a five-million-record list.

The smaller 100,000-call trial remains in SP RAM initialization; one million
calls reach RAM. At five million, the guest has reached exception tests and
cartridge/DMA tests. StartupTest reports one initial Config mismatch (reference
power value 7006e460 vs expected 7006e463); PIF remains WaitLockout because IPL2
execution is absent. Retain these limitations rather than patching guest state
to satisfy one test. Neither an authentic boot nor suite completion is claimed.

The VALIDATED result establishes broader finite capture and observer neutrality,
not executable closure or universal accuracy. The separate research stream
retains full 64-bit PCs and delay context; a fetch may still trap before retirement.
No compilation, DMA, relocation, overlay generation or RAM immutability is invented.
A production adapter must preserve raw provenance and changing words at the same
PC, keep RAM source/lifetime unknown, and verify cartridge backing explicitly.
Its artifact cost needs measurement before scalability claims. The existing
whole-ROM ProgramMap/solver remains OPEN with native lowering deferred.
