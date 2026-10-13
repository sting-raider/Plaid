# Cached Word producers export complete resident ancestry into executable RAM

Run `python spikes/084-cached-word-writeback-imem-consumption/run.py` or
`--verify-existing`, then `python scripts/test_rsp_definitions.py --writeback-imem
--source target/cached-word-writeback-imem-consumption-primary/source.json`.

Controlled v26/fixture27 extends the same DcacheReplay with actual decoded cached
SW and HitWritebackD. Bind full register/control/endian state, changed Word,
unchanged resident lanes and actual dirty mask. Equal stores create separate
mutation occurrences. Actual begin/complete16-byte RAM burst/end and CPU dirty
clear bind the export; nominal dirty lanes do not shrink the backing mutation.

SP LW679/read680 supplies known DMEM/DMA/RSP NOP. Cached SW685/mutation686 and
equal SW691/mutation692 replace the resident Word at e02c. CACHE697/writeback698/
actual RAM export699/end700/CPUend701 selects generation664/revision692. Outgoing
bytes0..11 retain fill663/664 parents, including unknown initial bytes and known
CPUwriter468; bytes12..15 retain mutation692 and its held source. All16 actual RAM
byte writers become699. Uncached LW705/read706 -> IMEM712/RSP714 selects export699;
cached LW719/read720 -> IMEM726/RSP728 retains mutation692 after dirty clearing.
The final words are equal, with separate consumption/writer identities.

The729-event/124-control reference capture,94 CPU steps/33 RSP words matches
baseline/disabled/enabled/repeat and full independent graphs. All27 earlier report
bytes stay exact. Missing/repeated/misbound equal stores, changed untouched lanes,
dirty-only/wrong/missing exports, false dirty-clear results and stale mutation/
fill/export/copy parents reject. Older sources are reused without reference or
full-ROM rebuilds. All completeness flags remain false; source/census/lifetime/
hardware/mapped/other-width/clean-or-miss writeback/whole-ROM/native stay OPEN.
No Actions/ROM/assets/upstream production reuse; passive callbacks only.
