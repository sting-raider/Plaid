# Finite guest EntryHi/cache reactivation

Run `python spikes/053-ares-asid-cache-lifetime/test_verify.py` for synthetic
report contracts, or `python spikes/053-ares-asid-cache-lifetime/run.py` for
unmodified exact pinned ares interpreter execution (g++/Ubuntu WSL on Windows).

The original ISC driver from `research/asid-icache-lifetime-gpt56sol` head
`a23c432ebc11ad2efdda8a33db7b5af6b9401896` is retained with its shared include
path adapted. Actual guest MTC0 EntryHi changes the active ASID without changing
installed entries. A resident line survives a switch away, a same-value context
write, changed backing, unrelated global execution and an unmatched-ASID fault.
Switching back executes stale 0x1111 with no miss; equal payload at another PA
then replaces the line, and the next return refills fresh 0x4444.

Four exact ares source objects and the independent Gopher64 cache object are
checked at clean pins. The EntryHi source guard isolates the setter rather than
the similarly named getter case. Gopher's physical cache index disagrees with
ares's virtual index; this finite ares behavior is not a hardware index rule.

The verifier checks all 32 typed report leaves, valid tags, exact miss counts
and the final I-cache tag/index/word digest. Repeated runs must agree. All 36
measured report mutations reject, including offset miss counts, invalid tags,
boolean indices and invented generation fields. The abstract 50k-history model
is reviewed separately and is not imported as a measured certificate.

TLBWI setup, debugger backing writes and exception resets are staged component
operations. Installed-entry snapshots are compared internally, but the report
contains equality flags rather than a complete writer history. Neither the final
cache digest nor the selected fetch facts establish complete machine state,
mapping generations, backing ancestry, mutation census or executable lifetime.
Those obligations and native closure remain OPEN. Generated reference code,
notices and raw results stay ignored; no reference implementation or branch CI
workflow enters production/native mode.
