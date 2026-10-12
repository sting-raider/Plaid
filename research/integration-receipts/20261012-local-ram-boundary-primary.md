# Retained local RAM boundary and bounded capture hashing

Base: ced57162bfef4b5ef60754e5f83ad519f8e006bb. Claim: 6118492063.

Reuse the existing exact compatible CIC6105 observer build for a million calls.
No reference rebuild. Disabled/repeated complete existing checkpoints and
messages agree; complete repeated source bytes are identical. Of 1,000,000
fetches, 2,055 are PIF, 841,500 SP and 156,445 RAM. First RAM fetch is seq843555,
PC ffffffff80000004, physical4, cached=true, sourceunknown. There are 41 unique
RAM PCs and zero observed word substitutions at those PCs. ROM entry 80000400
is not observed. These values are finite observations, not writer/lifetime proof.

Trace: aa6ee65d48121740f2d9d6b14cc739dfcf78318fa21b3b18382ec55c2676b157.
Checkpoint: 6b3e04574c520d8e86ee34374ac1ab7a09478498724f1d01eda80f30bd2beac7.
Complete canonical boot-fetch import retains 989 summaries, independently
rechecks source/firmware, and stays WholeRom OPEN. Actual raw words/maps and
boundary records remain ignored in target/local-boot-primary/oot-1m/.

The existing shared driver's maximum is ten million calls. Align the generic
recipe's budget ceiling with that bound and retain rejection beyond it before
output/build/capture. Stream SHA256 in bounded chunks instead of allocating an
entire trace. Replaying the retained million-call source preserves the exact
digest and all controls. On the same 168,765,554-byte actual input, tracemalloc
measures 168,775,267 peak Python bytes before and 2,106,214 after; measured wall
time 0.606/0.524 seconds is diagnostic only, not an emulator performance claim.
No sensor, guest semantics, proof flag or solver change.

Local full fmt, strict locked workspace/all-target Clippy, locked workspace,
canonical CLI and diff gate pass. Actual source replay and excessive-budget
rejection pass. Ten-million-call extension is an ongoing ignored local experiment;
its outcome is not asserted by this receipt. No Actions execution, reference
rebuild, ROM/firmware bytes in git, or milestone promotion.

Continue through the actual RAM/game-entry boundary, then join existing PI/SP
producer and cache lifetime sensors on an authenticated source clock. Do not
convert unknown RAM fetches or equal words into ancestry/immutability certificates.
