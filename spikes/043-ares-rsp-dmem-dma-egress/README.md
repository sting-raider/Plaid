# Spike 043: RSP DMEM writer lineage through SP write-DMA

Status: **VALIDATED** in the bounded exact-pin fixture. See
`research/rsp-dmem-dma-egress.md` for the full evidence and limitations.

This experiment validates one producer-export edge:

`ordered DMEM writer generations -> actual SP write-DMA -> completed RDRAM effects`

without selecting provenance from matching payload values.

## Core causal join

At pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, each DMEM
write-DMA fragment reads two DMEM Words, performs two
`RBusDevice::SP_DMA` RDRAM Word writes, and only then advances current PBUS/DRAM
addresses. The successful RDRAM callback can therefore derive its source DMEM
Word offset from the still-current DMA descriptor. Payload equality is checked
only afterward for trace integrity.

Pinned N64 ares uses its `lsb` memory wrapper, where guest Byte addresses map to
host backing through `address ^ 3`. The fixture therefore initializes and hashes
**logical guest bytes** through memory accessors rather than pretending raw byte
indices are guest addresses. This guard was added after preliminary runs exposed
that exact mistake.

## Adversarial fixture

The fixture contains:

- a decoded same-value RSP `SB`;
- a decoded scalar `SW`;
- a decoded vector `SDV`;
- a later fixture-known CPU-origin SP-memory Word overwrite;
- a two-row SP write-DMA with DRAM skip;
- an unaligned decoded RSP `SW` crossing `0xfff -> 0x000`;
- a 16-byte write-DMA beginning at DMEM `0xff8`, wrapping its source to `0x000`;
- monitoring for competing completed writes in the declared RDRAM windows;
- nine forged histories that must fail closed.

## Successful receipt

Plaid research commit:
`2a395485b3828badb8e2f68178f626008da9fa61`

GitHub Actions run: `37917030869`

Observed:

- 42 ordered events;
- 17 completed RSP DMEM primitive sink effects;
- 1 fixture-known CPU DMEM overwrite;
- 8 completed SP-DMA RDRAM Word effects;
- 0 competing non-SP-DMA writes in the declared destination windows;
- same-value RSP writer retained at event sequence 2;
- exported byte origins: 13 RSP, 4 CPU overwrite, 15 initial;
- 9/9 forged histories rejected;
- baseline / callback-disabled / enabled / repeat state neutrality passed;
- repeated enabled trace was deterministic.

Hashes:

- events: `060e97a1fa347dc1b2a928852491da320040a0dcaee6bf24dd8460de2c285060`;
- scoped logical RDRAM destinations: `4702a25853c06b1b082985076830a2e325ebc50965a68c63ce918a5065b0ac14`;
- trace: `25248a01ac69ebb9c7f5697a0fb010f632c7a852b5310475d9a7472f9b0dd927`;
- `results.json`: `03d5138badc899d3b19fe24401199a672db6ce2eb2e1e00957e882bff6e54274`.

## Reproduce

Fetch the exact ares pin into `.refs/ares`, then:

```bash
python3 spikes/043-ares-rsp-dmem-dma-egress/source_guard.py
python3 spikes/043-ares-rsp-dmem-dma-egress/run.py
```

The result is reference evidence for one causal provenance edge, not hardware
proof, exhaustive mutation coverage, executable reachability, or whole-ROM
closure. SP -> RDRAM still needs a separately proven downstream executable
consumer before it contributes to executable-byte provenance.
