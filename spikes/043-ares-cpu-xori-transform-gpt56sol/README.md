# Exact ares CPU XORI transformed-copy provenance

This branch-only spike extends the previously validated adjacent uncached `LW/LWU -> SW` evidence shape by exactly one interpreted ALU def-use step:

`LW/LWU rt,[src] -> XORI rt,rt,imm16 -> SW rt,[dst]`

It does not claim arbitrary register dataflow or decompression closure.

## Reproduce

Checkout exact ares revision `9408cb43d4948fc3ea6e152a307a34348df3fe04` at `.refs/ares`, then run:

```sh
python3 spikes/043-ares-cpu-xori-transform-gpt56sol/run.py
```

The branch workflow `research-cpu-xori-transform.yml` performs the exact checkout automatically.

## Cases

1. `LW` + nonzero XORI + SW.
2. `LWU` + nonzero XORI + SW.
3. `LW` + zero-immediate XORI + SW. Bits do not change, but the XORI remains a distinct causal generation.
4. Equal-valued decoy source load in another register before the real three-instruction chain.
5. Wrong-source XORI: the real load writes `t0`, but XORI reads equal-valued `t1`; an expression/value matcher can falsely attribute the later store to the load.
6. Equal-bit ORI clobber instead of XORI.
7. Misaligned failed load with no completed backing read.

The replay verifier requires exact instruction words, instruction begin/end GPR snapshots, completed uncached identity-RDRAM transactions and three-instruction adjacency. For accepted chains it emits a word transform plus four byte expressions. The N64 big-endian word maps XORI's immediate bytes to destination offsets 2 and 3; a zero immediate still emits a new transform context.

## Adversarial history checks

The runner rejects a forged source backing address, forged XORI source register, forged SW source register and a fabricated successful read inside the failed-load instruction.

## Neutrality

The runner compares an observer-free baseline, generated observer build with callbacks disabled, enabled capture, and a repeated enabled capture. Reported fixture facts and final state must match across baseline/disabled/enabled; enabled output must repeat byte-for-byte.
