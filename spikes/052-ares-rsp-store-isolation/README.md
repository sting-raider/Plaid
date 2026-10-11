# Finite decoded RSP store isolation

Run `python spikes/052-ares-rsp-store-isolation/test_verify.py` for synthetic
report contracts, or `python spikes/052-ares-rsp-store-isolation/run.py` for
unmodified exact pinned ares interpreter execution (g++/Ubuntu WSL on Windows).

The unchanged project-owned ISC driver from
`research/rsp-self-store-imem-gpt56sol` head
`761d1b53625bb78c6e0b0fa7fc93d076f4532516` executes 29 decoded probes: four
scalar bit-12/wrap cases, all twelve vector-store families at 0x1000/0x0fff,
and nonzero SRV at 0x100f. It compares all 4096 IMEM bytes before/after every
probe and aborts on any change. Aligned SRV is deliberately a zero-byte case;
the additional nonaligned SRV exercises its actual store path.

Ten exact source objects and three clean reference pins are checked. Source
audits cover every ares scalar/vector store handler and 4-KiB DMEM masking;
Gopher64 and n64-systemtest supply independent source expectations only. Their
behavior and physical hardware are not executed here. Both recompilers are
disabled, so the result is confined to this interpreter contract.

`expected.json` freezes synthetic probe metadata and storage hashes from the
successful historical runs. It contains no ROM/firmware/game bytes. The strict
verifier checks all 29 typed instruction/base/count/digest records in order and
final storage digests; 122 mutations reject in the measured report. Repeated
unmodified runs must agree byte-for-byte. This is store-domain behavior, not a
general producer, task activation, lifetime or native certificate.

Keep CPU/SP-window writes, SP DMA, reset/restore/debugger and other out-of-band
IMEM paths as independent mutation obligations. No new source interpreter,
reference code, branch workflow or observer instrumentation enters production.
Generated reference code/notices and raw results remain ignored.
