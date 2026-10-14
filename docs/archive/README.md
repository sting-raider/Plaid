# Archived swarm branches

`swarm-branches-20261015.tsv` lists every non-`main` branch that existed on
GitHub on 2026-10-15 (mostly the Oct 8-11 research swarm), with its exact
commit SHA, last commit date, commits not on `main`, and whether an open PR
uses it. Branches with open PRs are kept; the rest are candidates for deletion
from GitHub to declutter. Any branch can be recreated from its SHA while the
commit is still reachable, and from the owner's local bundle
`target/swarm-branches-20261015.bundle` (ignored; keep a copy outside the repo):

```bash
git fetch target/swarm-branches-20261015.bundle refs/remotes/origin/<branch>:refs/heads/<branch>
```

Done on 2026-10-15 at the owner's request: the 287 swarm branches with no open
PR were deleted from GitHub, each push checked against the SHA recorded here.
Kept: `main`, the 67 `codex/*` primary-integrator branches (all merged into
`main`), and the 7 branches behind open draft PRs #8, #10, #19, #28, #31, #39
and #50.
