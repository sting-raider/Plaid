#!/usr/bin/env python3
"""Apply the bounded fetch-summary sequence-coverage candidate fix.

This is research scaffolding for issue #4. It refuses to patch an unexpected
program.rs blob and is idempotent after the candidate marker is present.
"""
from pathlib import Path
import subprocess

PROGRAM = Path("crates/plaid-core/src/program.rs")
EXPECTED_BLOB = "08833320888c0ccabc0d5f6b974de09000676dec"
ERROR = "fetch summaries leave unaccounted sequence position"

text = PROGRAM.read_text()
if ERROR in text:
    print("candidate already materialized")
    raise SystemExit(0)

blob = subprocess.check_output(["git", "hash-object", str(PROGRAM)], text=True).strip()
if blob != EXPECTED_BLOB:
    raise SystemExit(f"unexpected program.rs blob: {blob} != {EXPECTED_BLOB}")

old_decl = """        let mut fetch_totals = BTreeMap::<&str, u64>::new();
        let mut fetch_keys = BTreeSet::new();
        let mut fetch_endpoints = BTreeMap::new();
"""
new_decl = """        let mut fetch_totals = BTreeMap::<&str, u64>::new();
        let mut fetch_keys = BTreeSet::new();
        let mut fetch_endpoints = BTreeMap::new();
        let mut fetch_intervals = BTreeMap::<&str, Vec<(u64, u64)>>::new();
"""

old_tail = """            let total = fetch_totals.get_mut(f.capture.as_str()).unwrap();
            *total = total
                .checked_add(f.occurrences)
                .ok_or(\"fetch count overflow\")?;
        }
        for (id, total) in fetch_totals {
            if total != self.fetch_captures[id].fetch_count {
                return Err(\"fetch summaries do not account for capture count\".into());
            }
        }
"""
new_tail = """            let total = fetch_totals.get_mut(f.capture.as_str()).unwrap();
            *total = total
                .checked_add(f.occurrences)
                .ok_or(\"fetch count overflow\")?;
            fetch_intervals
                .entry(f.capture.as_str())
                .or_default()
                .push((f.first_seq, f.last_seq));
        }
        for (id, total) in fetch_totals {
            let capture_count = self.fetch_captures[id].fetch_count;
            if total != capture_count {
                return Err(\"fetch summaries do not account for capture count\".into());
            }
            let mut intervals = fetch_intervals.remove(id).unwrap_or_default();
            intervals.sort_unstable();
            let mut covered_until = 0;
            for (start, end) in intervals {
                if start > covered_until {
                    return Err(\"fetch summaries leave unaccounted sequence position\".into());
                }
                if end >= covered_until {
                    covered_until = end.checked_add(1).ok_or(\"fetch sequence overflow\")?;
                }
            }
            if covered_until != capture_count {
                return Err(\"fetch summaries leave unaccounted sequence position\".into());
            }
        }
"""

if text.count(old_decl) != 1 or text.count(old_tail) != 1:
    raise SystemExit("candidate patch context did not match exactly once")
text = text.replace(old_decl, new_decl).replace(old_tail, new_tail)
PROGRAM.write_text(text)
print("candidate materialized")
