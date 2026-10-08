# ares RSP IMEM provenance

Verdict: **VALIDATED for the bounded controlled identity-mapped/interpreter scope.**

On pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, a successful
`RBusDevice::SP_DMA` backing read can be joined to the completed IMEM write and a
later RSP interpreter fetch. The join must be generation-sensitive and must fail
closed when the backing read did not succeed.

Run:

```bash
python3 spikes/018-ares-rsp-imem-provenance/run.py
```

The runner builds an untouched baseline with the existing spike-003 recipe, then
a separately generated observer build. The observer samples only already-completed
operations: successful ordinary RDRAM reads, RDRAM-to-IMEM DMA writes, direct IMEM
writes, and words already fetched by the interpreter. It makes no extra guest
memory/bus accesses. The pinned ares checkout must remain clean.

The branch workflow additionally hashes every generated observer source into
`target/ares-rsp-imem-provenance-spike/traced-build/observer-build.json`; generated
outputs remain uncommitted.

## Adversarial fixture coverage

- initial 16-byte RDRAM -> IMEM load and fetch;
- byte-identical reload from a different RDRAM address into the same IMEM range;
- changed reload into the same IMEM range;
- count/skip DMA proving `0x4008` poison is skipped and `0x4010` supplies the
  second block;
- RDRAM -> DMEM transfer, which never becomes an IMEM provenance write;
- direct CPU write to IMEM, which supersedes the prior DMA lineage for its word;
- out-of-bounds SP DMA read, which writes zero to IMEM but supplies no successful
  RDRAM backing-read witness and therefore resolves as unknown.

The script requires exact repeated traced JSON and exact baseline/traced emulator
state equality before accepting any provenance result.

## Executed checkpoint

Authoritative run: GitHub Actions `37800346437`, Plaid head
`5f94f8fd4bbd18ba5876bce1ce2c559e0e97434d`, Ubuntu 24.04.5,
`g++ 13.3.0`, Python 3.12.3.

- `results.json` SHA-256:
  `78ecaa90be8bfd3c1cf317d74b95dac4e131f828082ede8b9c8ccb8a3c6abc39`
- observer manifest SHA-256:
  `416da6c0cf414bded0c69557e19703b6509d320592f50e4af893dab027f9ac54`
- workflow artifact ZIP SHA-256:
  `109536504e4bfdb52474468731c8ea8d49c9d269ed18f23c531595922b15a829`
- neutrality: `true`
- repeated trace determinism: `true`
- behavior checkpoints: `[1, 2, 1, 9, 4, 5, 7, 0]`

The decisive counterexample is a byte-identical instruction at IMEM `0x000`:
its first fetch resolves to RDRAM `0x1000`/generation 1, while the later identical
fetch resolves to RDRAM `0x2000`/generation 3. Therefore IMEM address plus content
hash is not a provenance/lifetime identity.

See `research/rsp-imem-provenance.md` for the source map, event table, exact hashes,
architectural requirements and limitations.
