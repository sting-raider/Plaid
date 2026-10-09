# Actual CPU fetches from SP backing

Hypothesis: uncached CPU SP fetches can join the actual completed bank/offset/Word
read within their fetch interval, while cached SP fetches and status IO cannot.
CPU and DMA writes must retain their actual normalized storage effects, including
equal writes and the full-word SB sink, rather than inferring opcode-sized spans.

Run `python spikes/039-ares-cpu-sp-fetch/run.py`. The unchanged pinned reference
baseline and separately generated callback shadows stay under ignored `target/`.
The local recipe does not modify the shared builder or pinned checkout. Both
recompilers are disabled. Original ISC callback code consumes existing fields and
results without guest reads or clock steps. Upstream ISC/BSD licenses remain with
the separate build. No ROM/firmware asset enters Git or production runtime.

## Verdict: VALIDATED for the finite actual-reference fixture

### Evidence

The exact-pin run passes 18 CPU instruction steps and 77 ordered records.
Twelve uncached SP fetches join actual completed Word reads; a separate data
load does not become a fetch witness. DMEM/IMEM and their physical mirrors stay
distinct. Four CPU writes include equal, neighboring and changed writes plus SB
at offset +3 with its actual full-word payload. Three SP-DMA stores join existing
successful RAM receipts: one IMEM Dual and two DMEM Words.

The unchanged reference, sensor-disabled and twice-enabled runs agree on every
reported checkpoint, full GPR/HI/LO/PC/EPC/exception state, Count, freeze state
and RAM/hidden/DMEM/IMEM hashes. Enabled stdout repeats byte for byte. The expected
cached-SP freeze diagnostic is checked separately from the final JSON record.
Seven forged read/sink/order histories are rejected. Status IO emits no backing
read; the cached SP step freezes without an exception or backing-read witness.

Ignored result `target/ares-cpu-sp-fetch-spike/results.json` SHA-256:
`ff24e204cfe1e152b9d58d796a99c4505476c28ab6d882f5a042b73d5c140a49`.

### Constraints and surprises

Controlled CPU instructions and component DMA setup are not a complete boot,
hardware timing, all store/endian/TLB paths, SP producer census or lifetime proof.
An actual SP read gives backing bank/offset identity, not its ultimate ROM origin.

### Recommendation

Compose these completed results into a separate versioned boot chronology,
preserving previous raw sources and independent checkpoints. Keep ultimate byte
origins, RSP-originated DMEM writes and executable lifetimes as separate gaps.
