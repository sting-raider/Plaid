# Residual local traps

Integration claim: locally identified unsupported operations can be made
buildable by replacing their containing blocks with fail-closed native traps;
identity, provenance, overlay, and other nonlocal obligations still refuse.
Base: 62db2797aeb8e3eb3f398350c78f70684c58475e.

RE2 (USA Rev 1), `native.py --rt64 --seconds 30`: residual solve OPEN with
19 blockers, then native stop VI 17, fault 15, PC 8004d348, target 00000000.
Native validation reports failure for that expected guest fault.

On the same ROM inputs, before/after initial `discover --address-taken --fr0`
map SHA-256: F-Zero X 66e33c1d9b470fc197cb2a10d2d56603ffa24925eb602f95d16e7289ca7ac9cd;
Ocarina of Time 8f00136a91b9e3afa15dae800bea2dfed45c5d3dc3d96c57ceeb2e6939e2842c.
These are initial discovery maps, not full game executions or generated C.
