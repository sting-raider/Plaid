# Multipart lowering memory

Retain the existing closure checks, source order and byte-weighted partition
boundaries. Write each finished function to a temporary stream and remember its
length. After successful lowering, read the stream one translation unit at a
time. The CLI removes the temporary file after both success and failure. The
single-unit and in-memory library APIs remain available.

Run `plaid lower-map` with a retained Paper Mario map (142,348 blocks), the
matching local ROM, the header entry, the mapped exit, and `--parts 57
--runtime-unit --residual-dispatch`. Compare against `470e5d33`. There are 54
files (411,940,147 bytes), and each filename and SHA-256 matches.

Two alternating runs per revision after the ROM test pool completed. Peak
working set comes from Windows `PeakWorkingSet64`, sampled every 100 ms.

| Revision | Wall time (s) | Peak working set (bytes) |
| --- | ---: | ---: |
| Parent | 14.103 | 2,007,740,416 |
| Stream | 14.416 | 1,831,878,656 |
| Parent | 13.418 | 2,055,086,080 |
| Stream | 13.978 | 1,832,038,400 |

The average peak fell by about 199 MB (9.8%) and wall time rose by 0.44 s
(3.2%). Multipart lowering needs temporary disk space for the generated
bodies. The CLI regression checks cleanup after a successful split, after a
closure refusal, and when creation of the final main unit fails.
