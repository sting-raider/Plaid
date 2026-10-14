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
