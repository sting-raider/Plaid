# Replay-backed repair of boot text

```text
python scripts/native.py <local-re2-rom> --rt64 --rsp-gfx --seconds 12 --repair-loop
```

A ROM-only RE2 (USA Rev 1) build with `--repair-loop` stops at VI 215
with fault 15 at `8004d348`. On the parent commit, the second build
admits the bounded native capture as an observed alternate and stops
during solve with 126 blockers. The trap lies inside the original boot
window, which ordinary uncovered-fetch harvest already considers covered.

Pinned ares first fetch at the fault PC observes a CPU-produced span
beginning at `800138a0`. Its full 128 KiB overlap with the native fault
window matches byte for byte. The next fixed declaration starts at
`80100480` and bounds the admitted span. Compilation gets its bytes
from the same deterministic replay through the existing `ares_boot`
encoding. The policy derives the source and bounds from execution and
the current load catalog.

Mapped, counterfactual, mismatched and insufficient writes fall back to
the existing observed-image repair path. Explicit load catalogs,
explicit repair records and strict mode retain their earlier admission
policy. The executable still checks its declared text against live RAM.

The second visible RE2 build now reaches VI 309 and fault 12 at
`80135cc0`, the Status guard previously reproduced with an explicit
replay catalog.
The manifest records the replay source and witness hash with three
residual sites and `native_complete: false`. The exact reference probe
took 1.9 seconds and the cached verification phase took 0.25 seconds.
With only the experimental Status declarations supplied, a separate
visible run using automatic repair reaches the 15-second time limit at
VI 899 with 1,894 graphics tasks and fault 0. The SDK Status binding and
gameplay acceptance remain open.

The local gate passed all 82 runtime checks and seven visible 30-second
ROM controls. Each control reached VI 1798 with zero faults.
