#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/plaid-core/src/program.rs")
text = path.read_text()
needle = """        let mut fetch_totals = BTreeMap::<&str, u64>::new();
"""
guard = """        // `copy_event` names one concrete raw RomDmaObserved event. It may
        // support derived load/region/CFG facts, but one raw trace event cannot
        // simultaneously be a different primitive observation variant.
        for copy in self.loads.iter().filter_map(|l| l.copy_event.as_ref()) {
            if self
                .word_store_observations
                .iter()
                .any(|o| o.evidence.contains(copy))
                || self
                    .indirect_observations
                    .iter()
                    .any(|o| o.evidence.contains(copy))
                || self
                    .entry_verifications
                    .iter()
                    .any(|o| o.evidence.contains(copy))
            {
                return Err(
                    "load copy event reused by incompatible primitive trace observation".into(),
                );
            }
        }
        let mut fetch_totals = BTreeMap::<&str, u64>::new();
"""

if guard in text:
    print("candidate fix already applied")
elif text.count(needle) != 1:
    raise SystemExit(f"expected exactly one insertion point, found {text.count(needle)}")
else:
    path.write_text(text.replace(needle, guard, 1))
    print("applied copy-event primitive-kind exclusivity guard")
