# Mapped fragment partition timing (ADR-0340)

Hypothesis: parsing table evidence once per partition pass removes repeated
JSON decoding without changing the fragment boundaries. The candidate keeps
the existing declaration matches, protected extents, page cuts and slot cap.
A missing or non-object consumer is treated as unknown, so a matching table
still protects the entire load.

In three alternating pairs on the retained GoldenEye map (637 loads,
331 mapped captures), the median elapsed time fell from 5.199 s to 0.376 s.
Each run used a fresh copy of the same loads document and left it byte-identical.
The baseline was 165f52ec. This is the isolated partition pass on an already
partitioned input. An authored split with both a host function and a
cross-page table cell wrote identical JSON before and after the change.
The CLI contract also exercises a partition that writes and a matching table
whose consumer is null.
