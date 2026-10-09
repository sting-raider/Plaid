# RSP DMEM -> CPU SP refetch composition

Bounded question: can actual RSP DMEM store contexts be carried into a later CPU instruction fetch from the SP DMEM aperture without matching by value or RSP PC?

The exact pinned ares fixture composes the already validated SP word callback shadow (`spikes/039`) with the scoped RSP instruction/DMEM sink shadow (`spikes/042`) under one event ordinal. It executes:

1. CPU fetch of an explicit initial DMEM word.
2. RSP `SW` to the fetched word and CPU refetch.
3. A same-value RSP `SW` and CPU refetch.
4. A same-value CPU `SW` overwrite and CPU refetch.
5. An equal-valued RSP `SW` to the neighboring word and CPU refetch of the original word.

`run.py` replays concrete bytes and assigns per-byte writer generations only at completed sinks. It also mutates histories to ensure the generation verifier rejects deleted same-value generations, wrong-address decoys, lost RSP context, forged CPU writer identity, forged read values and duplicate ordinals. The deliberately weaker value-only check is expected to accept the deleted same-value generation counterexample.

Reproduce from the repository root with exact ares pin `9408cb43d4948fc3ea6e152a307a34348df3fe04` checked out at `.refs/ares`:

```sh
python3 spikes/043-ares-rsp-dmem-cpu-refetch/run.py
```

This is controlled reference evidence. It is not a complete writer census, producer-dataflow proof, executable lifetime certificate, RSP hardware atomicity claim, or whole-ROM closure proof.
