# Synthetic full-core PI session

2026-10-08. Reference pin `ba95bab92a76744753bfe61470823a4937850ab0`.

Hypothesis: the trace/import boundary can preserve source-correlated executed
code after a guest-initiated PI transfer through the full reference device layer.

`scripts/build_mupen_core.py` exports the pin with Git (preserving LF scripts),
applies the GPL research patch in a temporary repository, and builds the x64 core
with OSD/netplay/Vulkan disabled. The helper must request the `all` target:
default `make` prints help successfully. Extracted SDL2 headers need the multiarch
include parent for `SDL2/_real_SDL_config.h`. These were build setup issues.

`scripts/test_mupen_session.py` authors an 8192-byte ROM containing only project
test code. Its bootstrap at A4000040 programs PI to copy ROM 1000..1100 to RAM
400..500, polls busy, and jumps into the payload. JALR/JR exercise both source
events. A store/load checks RAM value 12 before the IS64 marker requests stop.
Each mode uses a separate process and configuration directory. PI/SI randomized
interrupt timing is disabled. The pinned startup connects CORE instead of RSP;
the frontend explicitly attaches/starts every bundled dummy plugin via the API,
otherwise teardown calls an uninitialized RSP callback after the marker.

Results: pure interpreter, untraced dynarec, traced dynarec and traced rerun have
identical 32 GPRs, HI/LO and PC (80000448). Registers s0/s1/s2 are 5/12/9 and the
RAM load yields 12. Traced reruns contain identical 42 events, one actual PI DMA
of 256 bytes, and the expected call/return observations. Import produces seven
blocks, preserves all three raw indirect events and identifies ROM-backed units
at 80000400 and 800004c0. Solver output remains OPEN/native_complete=false.
The original boot snapshot lacks a sensed PIF-HLE copy source. Ordinary cache
invalidation is not proof of a write; unknown-write diagnostics remain conservative.

The session also exposed a diagnostic error: empty/incomplete indirect candidate
sets were treated as exhaustive when comparing observations. The solver now
reports disagreement only against a claimed closed set. New tests preserve OPEN
status for incomplete hypotheses and still reject conflicting certificates.

Reproduce: `python scripts/test_mupen_session.py`. Python 3.12+, Linux x64
GCC/make/NASM, SDL2/zlib/libpng headers and libraries are required. Windows uses
WSL Ubuntu. This run extracted apt NASM 3.01 and SDL2 2.32.10/zlib 1.3.1/libpng
1.6.57 development packages under `target/reference-tools/`, without installing
system packages. Set PLAID_NASM or PLAID_REF_DEPS for alternate local prefixes.

This tests integration, not an independent hardware oracle: PIF HLE and synthetic
unknown-CIC fallback are reference choices. Graphics/audio/RSP plugins are dummy,
and no broader timing, exceptions, controller or commercial compatibility claim
follows. No native lowering or runtime emulation dependency is added to Plaid.
