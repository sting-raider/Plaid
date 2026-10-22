# Rogue Squadron table/code overlap investigation

## Finding

The repeated bogus pointer candidates at indirect site `0x8006c694` came from
interpreting executable words as a pointer table. The inferred table begins at
`0x80034158`, within the loaded image beginning at `0x8003407c` (ROM offset
`0x2f20`). The image-relative source offset is `0x2f20 + (0x80034158 -
0x8003407c) = 0x2ffc`. Those 15 words are:

```text
10e00015 24020001 94e30000 30620001 10400008
30620004 5440000f 24020001 8ce20004 8ca30004
24420010 00431021 ace20004 08000915 24020001
```

They decode as instruction words (notably `0x00431021` is `addu`). CFG
branches enter the same bytes from `0x80034134`, `0x8003413c`, and
`0x80034154`. This is evidence of code/data overlap, not a safe bounded table.
Other candidate evidence around `0x80073aec` also overlaps decoded blocks.

## Change and contract

`plaid-core::tables` rejects table snapshots whose byte interval overlaps a
decoded block in that image generation. If code is decoded after table evidence
was first recorded, the next analysis pass removes its table-derived candidate
edges and table-specific unresolved records, retaining the evidence for audit.
It does not close the indirect site: the site remains unresolved/residual until
independent proof exists. Synthetic contracts cover initial rejection and
withdrawal after later code discovery.

## Results

On Star Wars - Rogue Squadron (USA) (Rev 1), the user-observed residual solve
count was 184; after the change it was 151 across 17 residual sites. Ordinary
harvested blockers ended at 168, compared with the previously observed 201.
The report still contains 69 unresolved indirect targets, 50 invalid pointer
table entries, 14 unsupported scope effects, 6 immutability and 6 target
identity proof failures, 3 unsupported instructions/exceptions, one unmapped
target, one unresolved direct target, and one unsupported delay slot. The map
is still OPEN; the native pipeline correctly refused to emit an artifact.

The remaining direct edge includes `0x80091a48 -> 0x8334b334`; the float
constant at `0x80831148` (`0x3f99999a`) and related constant words are reached
only through static image-root provenance in the final map, without an
independent control-flow edge. These need separate root/extent provenance
analysis. Unsupported scope effects include `0x8000041c`. No ROM bytes are
stored here.

Focused verification: `cargo test --locked --release -p plaid-core --test
core tables:: -- --nocapture` passed 13 tests. Exact-tree full gate recorded on `07157a5a`: `cargo fmt --all -- --check`,
`cargo clippy --locked --workspace --all-targets -- -D warnings`,
`cargo test --locked --workspace` (537 passed, 1 ignored),
`python scripts/test_cli.py`, and `python runtime/test_runtime.py` all passed.
Cross-game native runs used `SDL_AUDIODRIVER=dummy`: Banjo-Kazooie (VI 1798,
618 graphics / 894 audio tasks), Paper Mario (VI 1798, 1786 graphics / 1796
audio tasks), and Majora's Mask (VI 1798, 657 graphics / 1775 audio tasks),
each stopped at its 30-second limit with fault 0. An optional Banjo `--rt64`
link attempt was unavailable because the worktree lacked `plaid_rt64.dll`; the
standard headless native invocation passed.
