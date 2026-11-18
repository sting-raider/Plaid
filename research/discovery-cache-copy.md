# Discovery cache file copies

Benchmark the work after a synthetic producer has written a retained Paper
Mario map of 213,897,415 bytes. Alternate the parent and candidate
`memo_plaid` against fresh output and cache directories five times. The
outputs match by SHA-256. The median cache publication falls from 1.263 s to
1.008 s with concurrent validation activity. The samples vary with disk
load. The structural saving is one full map read and write per miss, and a
file-sized Python buffer is no longer required on either path.

The memoization contract checks one copy from the producing path during
publication and one copy to it on restoration. Binary, input, and oracle
source changes still invalidate the cache. Failures still rerun.
