# Primary integration: ordinary storage mutation sensing beneath RAM wrappers

Base:35ca5ee62213f994b0a78a0f02d9ffd16fd0a946. Claim:6156573169.
Harvest canonical scalar/burst, cached write/export and restore-cut contracts.
Identity-only callbacks omit successful translated and EBus writes. Add a shared
opt-in passive primitive observer, preserving existing protocols/callbacks by
default and all current closure obligations. No isolated Rust consumer is added.

Spike086 guards exact pinned little-endian Memory::Writable and routes all of its
existing scalar writes through a completed-effect callback with masked/aligned
storage address and truncated payload. Dual/unaligned/burst operations preserve
their actual component occurrences, including equal stores. Stable writable-
object identity separates foreign banks and survives explicit reallocation cuts.
Fill/load/reading serialization use conservative whole-storage cuts; saving
emits no restore. Retirement occurs before old memory is freed. No extra guest
access, translation, clock, decoder or object-layout mutation is introduced.

Actual contract:20 complete ordinary-RAM/hidden checkpoints plus GPR/PC/selected
CP0/RI state agree across unchanged baseline, disabled, enabled and repeat.
The independent25-effect census contains20 scalar effects and5 bulk/lifecycle
cuts. Ordinary/equal/base-class/EBus/nonidentity translated writes, failed
translation, out-of-range suppression, Dual/16-byte burst/unaligned components,
requestor routing, save/restore, nonempty file load, fill/retire/reallocate and
foreign-bank controls are retained. These are actual component calls; requestor
labels are not evidence of complete DMA tasks or guest instruction execution.

Reference:clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04.
Audits (UTF-8 text with normalized line endings):

- memory/lsb/writable.hpp:52565f0359450110af0836d37540a7fb8f77cb10a6e444286a5b09c14c8fd2f0.
- memory/memory.hpp:673de0205f34c3da47095bce162e5706924cb24cddaac3080a2a40e0d444b6eb.
- rdram/rdram.hpp:6a77c2fa0bbb320ff6b2855ea6379541a67096bed6b91cc6cd2697584112b1cf.

Ignored evidence:target/storage-mutation-primary, with capture/binary/build
digests in receipt.json. Canonical issue4 closeout preserves its exact source and
receipt digests externally. Reference sources/LICENSE stay in ignored generated
builds; no upstream code is copied into production or native runtime.

Final actual source:1d621cebc0cf90dbd0cf05fd43d78dd8c1c20f3b3b83bf7dedf4e92fd0acc26d.
Baseline/disabled:db26941fbb666bdd12231df89413829856a4ca9ea8350c2fdce6005cc28201c1.
Baseline build:fc4a23598896a7b1e3e36a37b7252ba94471a1d86d016d2649309a136654e1ee.
Sensor build:1b1592e934d18f3f392dd2dad1db6905549e0b1beaf97504289e585fd3a1b638.
Normalize audited source line endings for fresh Linux/Windows checkout portability.
The resulting actual generated headers remain byte EXACT (writable:
d17c68f2053515a464b10cb3ba0ea06365b084b0e94b27f8cdad608d5e142a31;
memory:b789942bc26aee6f02ee35f831e6865caf3ef422b77816e3a8a8cd7d6d6c2c82).
Retained binary/source controls therefore need no further reference rebuild.

Focused gates:four opt-in/shadow-reuse combinations, three independent audited
source drift rejections, six prior shared recipe combinations, actual generated
sensor/driver compilation and exact baseline/source census comparison, repeated
retained-source verification. Actual load coverage required a nonempty fixed-size
VFS buffer; the initial zero-capacity no-op rejected and was corrected before
final reference validation. A fixture namespace ambiguity was corrected without
changing reference semantics. No assertion or lint waiver.

Final local gate:fmt, strict locked workspace/all-target Clippy, full locked
workspace tests, python scripts/test_cli.py, git diff --check. Issue4 closeout
records final results and expected-head CAS/fetched verification. STATUS/NEXT/
DEVELOPMENT/ADR0124 describe the sensor and pending composition, progress unchanged.

Next join these effects to the original fetch/writer clock and actual producer
contexts, revoking unsupported backing ancestry while preserving separately
verified cached generations. Raw pointer/JIT/Vulkan and hidden-RAM mutation
coverage, complete lifecycle/scheduler census and whole-ROM/native closure remain
OPEN. All broad proof flags remain false. No Actions or older/full-ROM rebuild.
