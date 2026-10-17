# ADR-0192 paired executable slot integration

Prepared against canonical `6d846dfb45235d978988ff84ddb90767ccabc53d`.
Recovered candidate: `bk-closure-3` at `f27d513`.

The compiler derives paired-stream executable files from ROM-owned literal
source catalogs and unique matching segment metadata. It retains stream
end/size checks, format-owned text/data bounds, native content identity and
active-frame pins. This is a declared conditional executable universe.
Whole-loader lifetime, every future executable source and whole-ROM
completeness remain unproved. No assumption is retired.

The takeover gate on the recovered tree passed (729 Rust tests, one ignored),
including raw/paired native slot switching and pinned-ares state, PC, fault
and retained RAM comparisons. Its normal BK pipeline regenerated 33,796
blocks and refused the single unsupported Status read at `80259d30`.
Native BK gameplay/audio validation remains unreached.

Review nevertheless stopped the landing. Retained synthetic cases exposed:

- a source catalog prefix matching only part of a longer segment table;
- conflicting literal initializers silently choosing the last table;
- eager unsigned subtraction while scanning malformed metadata.

The first three regressions failed on the recovered tree. The fix validates
segment ordering before arithmetic, rejects matching prefixes/suffixes with
adjacent segment records, and checks every catalog cell against all literal
writes, including partial/malformed conflicting initializers. Conflicting
writes within a single block are retained for that check. Identical duplicate
initializers remain acceptable. Six Rust regressions cover these cases in
debug and release; five independent Python parser contracts cover boundaries,
metadata and initializers. Removing conflict refusal makes its regression
fail, and the source is restored byte-for-byte afterward.

The initial review also inverted the instruction/data filter; its existing
regression failed and the isolated source was restored. The user subsequently
requested no subagents. Both active tasks were stopped and their useful
tests/evidence were preserved; the primary session owns these fixes and final
validation directly.

The first takeover runner incorrectly exported GCC as CC across Rust/MSVC
compilation. Rabbitizer's C objects then failed MSVC linking. The corrected
runner leaves CC unset and places GCC on PATH for Python/native tests; no
production workaround was introduced. Accepted pre-fix timings were fmt
1.075 s, Clippy 7.250 s, workspace 94.622 s, CLI 11.995 s, runtime 177.417 s
and research parser 0.216 s. These measurements describe the recovered tree,
not the final gate after review fixes.

Final acceptance commands are the complete local fmt/strict Clippy/workspace/
CLI/runtime gate, release catalog regressions, exact pinned-ares slot
contracts, a fresh normal BK pipeline, and regeneration of the nine existing
control maps/IDs plus configured SM64. Ignored logs, timings and comparisons
live under `target/continuation-0192/`. The issue #4 closeout records final
results and the exact validated canonical commit. No Actions, runtime guest
decoder, ROM/assets, captures or generated game code enter git.

The hardened candidate gate passed: fmt 0.776 s, strict Clippy 0.334 s,
workspace tests 87.016 s (735 passed, one ignored), CLI 8.134 s, runtime
151.351 s and Python parser 0.363 s. Release catalog regressions also passed.
The normal BK pipeline repeated OPEN/1 in 73.224 s; it built no game.

Three-sample median infer-loads timings before -> after review hardening were
BK 0.04998 -> 0.04910 s, Paper Mario 1.61744 -> 1.62684 s, and MM
0.22905 -> 0.22143 s. Complete declaration files were byte-identical. These
small/noisy differences establish no broad speedup or regression. Controls
use the retained comparison protocol with independent ROM jobs batched three
at a time; outputs, rather than elapsed time, are their acceptance gate.

`research/status-interrupt-model.md` preserves the next bounded experiment.
It admits no Status boundary and does not replace the remaining differential
or native-game validation.
