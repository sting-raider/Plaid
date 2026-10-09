# ares translated-RDRAM fetch join

Bounded research spike for Plaid at pinned ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Hypothesis: an uncached CPU fetch boundary can causally bracket one completed
non-identity RDRAM scalar read, preserving both the raw mapped backing word and
the post-CCI delivered instruction. The join must use ordered context plus the
post-endian bus request, not value equality or request-address backing bytes.

The fixture covers:

- reliable request `0x000000 -> mapped 0x200000` with an equal-valued decoy at
  request-address backing;
- an equal-valued translated data read immediately outside the fetch interval;
- CCI degradation where raw `ORI` becomes delivered zero/NOP;
- missing translated chip mapping;
- MI EBUS HiddenRAM fetch, which is not ordinary backing provenance;
- reverse-endian Word fetch where translated paddr `0` becomes bus request `4`
  and maps to backing `0x200004`;
- deliberate ambiguous/wrong-request/raw-vs-delivered/missing-read history
  forgeries.

Run:

```bash
python3 spikes/043-ares-translated-fetch-join/run.py
```

The runner requires `.refs/ares` at the exact pin. It builds an unmodified-state
baseline plus generated research-only shadows, executes disabled/enabled/repeated
variants, and writes ignored results under `target/ares-translated-fetch-join-spike/`.

This is an observed-source primitive, not executable lifetime, reachability,
mutation-completeness, hardware-accurate CCI, or N64-wide proof.
