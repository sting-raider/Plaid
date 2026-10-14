# Synthetic native vertical slice (milestone 1)

Hypothesis: a program the solver reports CLOSED can be lowered to C, compiled
by an ordinary host compiler and run natively with exactly the reference
interpreter's architectural results, with no guest decoder or interpreter in
the artifact (ADR-0125, ADR-0126).

`run.py` assembles seven synthetic programs (`alu`, `muldiv`, `loops`,
`memory`, `transfers`, `wide`, `calls`) at `0x80000000`, ending at the exit address
`0x80000F00`. For each it runs `plaid lower-c` (discovery, then solve under
`DeclaredStaticImagesGuardedRam`, then `crates/plaid-lower`), compiles the C
with `-Wall -Werror` against `harness.c`, runs it, and compares all GPRs, HI,
LO and the RAM window `0x1000..0x1100` with `driver.cpp` on the pinned ISC
ares interpreter (recompiler disabled). The oracle reads RAM through the D-cache
debug path, so both sides report the CPU-coherent view.

Four programs must fail closed rather than match: `self_modifying` stores
into its own code (fault 2), `cache_alias` reads through KSEG1 a line it wrote
through KSEG0 (fault 4), `bad_return` returns with a corrupted `$ra` (fault 5)
and `overflow` overflows a trapping `addi` (fault 6). On hardware the latter's result depends on write-back
D-cache state, which the coherent native memory model does not track.

```text
python spikes/096-native-slice/run.py            # reuse a built oracle
python spikes/096-native-slice/run.py --rebuild  # rebuild the ares oracle
```

Windows needs a C compiler on PATH (`gcc` or `clang`, or `CC`) and WSL Ubuntu
for the oracle build. Outputs and the receipt live under ignored
`target/native-slice/`. No ROM, firmware or upstream code is committed.

`calls` exercises recursive factorial, a non-leaf function calling a leaf
twice, a `jalr` function-pointer call and a tail call, with stack frames inside
the compared RAM window (ADR-0127). `wide` covers the 64-bit integer subset,
128-bit HI/LO results stored through `SD`, and branch-likely slots (ADR-0128).
