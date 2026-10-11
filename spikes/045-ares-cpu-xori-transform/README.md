# Bounded interpreted XORI provenance

Reconciles `research/cpu-xori-transform-gpt56sol` through the primary strict
instruction/GPR/scalar verifier. Only an adjacent captured
`LW/LWU rt -> XORI rt,rt,imm16 -> SW rt` triple can certify this transform.
Copy mode remains separate and rejects XORI.

The seven original synthetic phases retain LW/LWU positive cases, XORI zero,
an equal-valued competing load, a wrong-source XORI with equal register bits,
an ORI clobber and a failed load. The wrong-source chain remains uncertified.
XORI zero keeps a distinct transform context even though the bits stay equal.
Four byte expressions retain the big-endian low-16-bit XOR mask.

Run from the repository root:

```sh
python spikes/045-ares-cpu-xori-transform/run.py
```

Windows delegates to WSL Ubuntu. The exact unchanged ares pin is
`9408cb43d4948fc3ea6e152a307a34348df3fe04`; generated builds and schema-0 results
remain under ignored `target/ares-cpu-xori-transform-primary`. Twenty reported
instruction checkpoints agree in original/disabled/enabled/repeated runs.
Forty instruction boundaries and thirteen scalar effects produce exactly four
transform certificates; thirteen measured forgeries and six independent
synthetic contract regressions pass. Result SHA-256:
`e73a87e0106b5bc6b9631f35795015aa6275a6d70f171a9c186d2c32a732e783`.

No general register dataflow, complete execution census, cached/translated
operation, decompression/relocation, executable consumption/lifetime, hardware
equivalence or production/native certificate is established.
