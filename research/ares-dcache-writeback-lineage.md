# ares D-cache store-to-writeback lineage

2026-10-09. Status: **VALIDATED for the bounded controlled scope below**.

## Bounded question

At exact pinned ares revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`, can one cached VR4300 word-store mutation be carried through a specific resident D-cache line/lane identity to the exact later successful identity-RDRAM burst write, without inferring provenance from physical address or payload equality?

The tested scope is interpreter execution with both recompilers disabled, cacheable direct KSEG0 data addresses, identity-mapped RDRAM, one aligned `SW`, and either explicit D-cache hit writeback or dirty same-index replacement. Clean replacement and dirty hit-invalidate are adversarial negatives.

## Result

**Yes, but only with resident cache lineage plus the actual backing transaction.** A cached store is neither an immediate nor an inevitable RDRAM mutation.

The exact-pin executable fixture established four cases:

1. `SW` to cached A followed by `CACHE 0x19` hit writeback: A's RDRAM backing remained old after `SW`; the later full-line writeback exported the mutated first word. The observed D-cache `writeback_begin` strictly preceded the successful `VR4300_DCACHE` RDRAM burst write, which strictly preceded `writeback_end`.
2. `SW` to cached A followed by a load from same-selected-line B (`A + 0x2000`, different physical tag): the dirty miss wrote A back before the backing read/fill of B. This closes the dirty-eviction hole left by the earlier CPU-copy study for this controlled scope.
3. Clean A -> B same-index replacement, with A and B deliberately initialized to equal line payloads: there was no D-cache RDRAM write. Equal addressable payloads do not imply a mutation relationship.
4. `SW` to cached A followed by `CACHE 0x11` hit invalidate and then B replacement: the line became invalid while its dirty mask still contained the stored word, but A backing stayed old both before and after replacement. No D-cache RDRAM write occurred. A real resident mutation can therefore die without ever becoming backing provenance.

The measured trace verifier certifies backing bytes only when all of these are joined in one shared chronology: a completed successful backing fill, a concrete resident line generation, the resident store/lane mutation, `writeback_begin` for that same line state, an exact nested successful RDRAM burst write with matching address/payload, and `writeback_end`. Fill/replacement or invalidation retires the resident generation.

The independent model additionally versions every resident mutation. A same-value store after a pending writeback snapshot invalidates that snapshot even though generation, physical address and payload bytes still match. This is the counterexample that rules out `(tag,address,value)` as sufficient provenance identity.

## Exact source behavior used

Pinned `ares/n64/cpu/dcache.cpp` selects `lines[vaddr >> 4 & 0x1ff]`. A miss writes back only a valid dirty resident line before filling the replacement. `Line::fill` clears dirty state and performs `busReadBurst<DCache>`. `Line::write<Size>` mutates resident bytes and dirty-mask lanes. `Line::writeBack` sends the complete resident 16-byte line through `busWriteBurst<DCache>` and does not itself clear dirty state.

Pinned `ares/n64/cpu/interpreter-ipu.cpp` `CACHE 0x19` invokes `line.writeBack()` for a matching dirty line and clears dirty afterward. `CACHE 0x11` instead clears validity on a hit without first writing dirty data.

Pinned `ares/n64/rdram/rdram.hpp` identity burst reads provide the backing payload used by a fill, while completed burst writes update the backing words and hidden RAM. The experiment's RDRAM callback is placed after those controlled successful effects.

Pinned source SHA-256 values from the exact CI checkout:

- `ares/n64/cpu/dcache.cpp`: `a1e2dd9c619cae7dbba4162eab8ab09a239f818019b50a88e49b09501488650b`
- `ares/n64/cpu/cpu.hpp`: `6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27`
- `ares/n64/rdram/rdram.hpp`: `6a77c2fa0bbb320ff6b2855ea6379541a67096bed6b91cc6cd2697584112b1cf`

## Executable experiment and neutrality

Durable fixture: `spikes/034-ares-dcache-writeback-lineage/`.

The instrumented build uses generated copies of pinned `cpu.hpp`, `dcache.cpp`, and `rdram.hpp`; it does not add fields to ares CPU/cache objects. One observer records fill/store/writeback/invalidate lifecycle events and another records completed RDRAM bursts. Both feed one monotonic capture ordinal.

The runner compares:

- an unmodified pinned-ares baseline build;
- the generated instrumented build with callbacks disabled;
- the same generated build with callbacks enabled;
- a repeated callback-enabled run.

Guest/emulator facts and hashed state are equal across baseline/plain/traced runs, and the two traced JSON outputs are byte-identical.

Exact-pin successful GitHub Actions run: `37851339805`.

- trace SHA-256: `e0cf9f8332b72377c20f665d89f640b80406ea358de7ecbf68de4b6936329192`
- result JSON SHA-256: `6d42e2edcd1db308e219c971fbadb2c1b69cb15de343b49e317c7bdbb057a747`

The strengthened standalone verifier model (`model.py`) executes 3,000 deterministic histories x 120 actions. Final model result: 1,179 legitimate certificates and 50,206 forged/unjoined writes rejected, plus fixed negative cases for clean replacement, dirty invalidate/drop, same-payload wrong generation, and same-payload wrong resident revision. Canonical report SHA-256: `02bbfbfd58817fcdd10d21523018be2b69dba1cf8b2e2b9c9c6afcc4dd98a9eb`.

## Architecture consequence for Plaid

Adopt a two-level mutation model for cacheable CPU stores:

1. a successful cached store creates/updates **resident D-cache byte origins** on a concrete line identity/generation/revision and dirty lanes;
2. those origins become **backing-memory origins** only at an actually observed/proved successful backing write for the same writeback snapshot.

For a full-line writeback, modified lanes inherit their most recent resident store/copy origin; untouched lanes retain the origin of the fill that populated the same still-resident generation. Invalidation/drop retires all unexported resident mutation origins. A clean replacement exports nothing. Address/tag/value equality must never resurrect retired cache lineage.

This rule composes with CPU-copy provenance: a cached destination store may carry the source byte origin into D-cache residency, but it is not an RDRAM copy witness until this later writeback join succeeds.

## Limitations / still open

This is not a universal VR4300 cache proof. General Plaid closure still needs the same lineage discipline across all relevant store families and byte lanes, TLB/cacheability transitions and aliases, reverse-endian modes, non-identity/degraded RDRAM mapping, reset/save-state/restore epochs, other CACHE operations, exceptional/failing backing routes, DMA/device interactions, RSP execution, and production ProgramMap integration/scalability. This fixture also does not prove hardware behavior independently of pinned ares; it validates the causal witness construction against the declared reference implementation in a controlled scope.

## Recommendation

**ADOPT** the versioned resident-line/lane -> exact successful backing-write witness rule. Do not treat cached store observation, dirty state, current RAM contents, cache tag, or matching payload as backing provenance by themselves. The branch is a research artifact; production implementation should be transplanted deliberately rather than merged wholesale.
