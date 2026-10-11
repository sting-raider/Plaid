# Finite guest TLBR/cache reactivation

Run `python spikes/054-ares-tlbr-cache-lifetime/test_verify.py` for synthetic
report contracts, or `python spikes/054-ares-tlbr-cache-lifetime/run.py` for
unmodified exact pinned ares interpreter execution (g++/Ubuntu WSL on Windows).

The original ISC driver from `research/tlbr-icache-lifetime-gpt56sol` head
`a625e4ac88482b6947c018dabf464073e58187bc` is retained with its shared include
path adapted. Real decoded TLBR changes active EntryHi context without replacing
installed entries or cache contents. Switching back reactivates stale 0x1111;
equal payload at another PA replaces the line, and a later return refills 0x4444.
TLBP, same-value TLBR, out-of-range TLBR, global code and ASID fault controls
remain. Internal context-step checks compare installed entries, serialized cache
tag/index/words and selected miss counts. This is not full machine state.

The strict verifier checks all 34 typed report leaves, exact tags/counters/cache
digest and schema. Repeated actual output must agree; all 38 measured mutations
reject. Four synthetic tests also preserve missing-field and type adversaries.
The original model is replayed separately, not imported as a generation proof.

Eight exact source objects are checked. ares, Gopher and n64-systemtest require
clean pins. The existing instrumented Mupen checkout is left intact; its pinned
HEAD and selected TLB source must be unchanged, including the index. Gopher's
physical cache index and Mupen's inspected LUT translation without active-ASID
matching remain source disagreements. Those references and systemtest are not
executed; hardware policy is not inferred from the ares result.

Index staging, TLBWI setup, exception resets and debugger backing mutation are
direct component operations. Successful TLBR loading, instruction occurrence,
mapping storage, backing and resident identity require separate histories.
Snapshot equality does not authenticate those histories. General writer census,
ancestry, lifetime and native closure remain OPEN. Generated reference code,
notices and raw captures remain ignored, and no reference implementation or
research-only workflow enters production/native mode.
