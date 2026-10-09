#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/plaid-core/src/solver.rs")
text = path.read_text()
marker = '"ambiguous_physical_executable_identity"'
if marker in text:
    print("candidate fix already present")
    raise SystemExit(0)

anchor = "    let starts: BTreeSet<_> = map\n"
assert anchor in text, "solver insertion anchor changed"
patch = '''    if scope == Scope::DeclaredStaticImages {
        let regions: Vec<_> = map.regions.iter().collect();
        for (index, a) in regions.iter().enumerate() {
            let Some(a_physical) = a.physical_start else {
                continue;
            };
            for b in &regions[index + 1..] {
                let Some(b_physical) = b.physical_start else {
                    continue;
                };
                if a.image == b.image && a.generation == b.generation {
                    continue;
                }
                let a_start = u64::from(a_physical.0);
                let a_end = a_start + u64::from(a.range.size);
                let b_start = u64::from(b_physical.0);
                let b_end = b_start + u64::from(b.range.size);
                if a_start < b_end && b_start < a_end {
                    let evidence: EvidenceRefs =
                        a.evidence.union(&b.evidence).cloned().collect();
                    add(
                        "ambiguous_physical_executable_identity",
                        None,
                        "distinct executable image/generation identities overlap explicit physical backing; alias/lifetime equivalence is unproven",
                        evidence,
                    );
                }
            }
        }
    }
'''
path.write_text(text.replace(anchor, patch + anchor, 1))
print("applied candidate physical-alias closure gate")
