# Subword whole-Word effects compose with transformed executable ancestry

Run `python spikes/081-subword-transform-imem-consumption/run.py` or `--verify-existing`,
then `python scripts/test_rsp_definitions.py --subword-imem --source
target/subword-transform-imem-consumption-primary/source.json`.

Controlled v23/fixture24 binds actual raw device addresses separately from aligned
SP Word sink addresses. Full decoded GPR/control/link/endian before/completed
snapshots and direct-KSEG1 mapping bind the existing `cpu_sp_subword` normalizer.
Nominal SB/SH width is not mutation width. Successful completed Word sinks create
four-byte writer generations, even when payloads repeat.

Actual LW547/read548 loads known DMEM/DMA/RSP NOP; XORI553 derives ADDU21. SB558/
write559 at device04001003 installs aligned Word04001000, consumed at RSP561.
SH566/write567 at device04001002 installs the equal full Word again, consumed at
RSP569. Both copy receipts retain the same load/read/actual XORI expression and
their distinct sink identities. Latest final IMEM writer is567. The new optional
IMEM-copy transform reuses `CpuXorTransform`; older report shapes remain exact.

Only actual shift-zero lanes supply identity-word copy ancestry (SB lane3,
SH lane2). Other lanes retain normalized mutation witnesses without borrowing
that copy relation. A synthetic lane0 variant produces21000000, keeps its Word
effect and omits the identity-copy receipt; that unsupported RSP word is not
executed in the variant, and all completeness flags remain false. This reducer
check is separate from the actual reference capture.

Complete570 events/94 full existing machine/cache/CP0/pipeline/TLB controls,
71 CPU steps and26 RSP words agree baseline/disabled/enabled/repeat. Independent
source/report graphs agree. Earlier sources/reports are reused, with no old
reference/full-ROM rebuild. Missing/repeated/misbound or nominal-width sinks,
wrong device/aligned address/endian/source/state/transform and stale equal writer
parents reject.

Scope is normalized direct-SP kernel32/IE0/big-endian successful SB/SH. Preserve
the retained ares/Gopher/systemtest vs Mupen masked-source disagreement; no new
hardware consensus. Other lanes' ancestry, fault/alias/endian/global source/census/
root/lifetime/whole-ROM/native remain OPEN, all flags false; static ERET unsupported.
Reference objects/notices/controls stay ignored; no upstream production reuse.
