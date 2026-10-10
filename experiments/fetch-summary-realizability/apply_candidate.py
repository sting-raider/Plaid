#!/usr/bin/env python3
"""Apply the bounded fetch-summary realizability candidate to current main source."""

from pathlib import Path

PATH = Path("crates/plaid-core/src/program.rs")

HELPER = r'''fn fetch_summaries_realizable(fetch_count: u64, summaries: &[(u64, u64, u64)]) -> bool {
    if fetch_count == 0 {
        return summaries.is_empty();
    }

    let mut endpoints = BTreeMap::<u64, usize>::new();
    let mut interior = Vec::with_capacity(summaries.len());
    for (index, &(first, last, occurrences)) in summaries.iter().enumerate() {
        let endpoint_count = if first == last { 1 } else { 2 };
        let Some(remaining) = occurrences.checked_sub(endpoint_count) else {
            return false;
        };
        interior.push(remaining);
        for seq in [first, last] {
            if endpoints.insert(seq, index).is_some_and(|old| old != index) {
                return false;
            }
        }
    }

    // Each remaining occurrence is a unit-time job whose release is first+1
    // and deadline is last-1. Fixed endpoint positions are unavailable. For
    // interval release/deadline windows, earliest-deadline assignment is a
    // complete feasibility test. Consume whole free gaps rather than iterating
    // over every raw fetch sequence position.
    let mut active = BTreeMap::<u64, u64>::new();
    let mut previous = None;
    for (&seq, &owner) in &endpoints {
        let start = previous.map_or(0, |old: u64| old + 1);
        let Some(mut slots) = seq.checked_sub(start) else {
            return false;
        };
        while slots != 0 {
            let Some((&deadline, &demand)) = active.iter().next() else {
                return false;
            };
            if deadline < seq || demand == 0 {
                return false;
            }
            let used = slots.min(demand);
            slots -= used;
            let remaining = demand - used;
            if remaining == 0 {
                active.remove(&deadline);
            } else {
                active.insert(deadline, remaining);
            }
        }

        let (first, last, _) = summaries[owner];
        if last == seq && active.contains_key(&seq) {
            return false;
        }
        if first == seq
            && last > seq
            && interior[owner] != 0
            && active.insert(last, interior[owner]).is_some()
        {
            return false;
        }
        previous = Some(seq);
    }

    previous.is_some_and(|seq| seq.checked_add(1) == Some(fetch_count)) && active.is_empty()
}
'''


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source match, found {count}")
    return source.replace(old, new, 1)


def main() -> None:
    source = PATH.read_text()
    if "fn fetch_summaries_realizable(" in source:
        raise SystemExit("candidate helper already present")

    source = replace_once(
        source,
        "\nimpl ProgramMap {\n",
        "\n" + HELPER + "\nimpl ProgramMap {\n",
        "helper insertion",
    )
    source = replace_once(
        source,
        "        let mut fetch_endpoints = BTreeMap::new();\n",
        "        let mut fetch_endpoints = BTreeMap::new();\n"
        "        let mut fetch_constraints = BTreeMap::<&str, Vec<(u64, u64, u64)>>::new();\n",
        "constraint ledger declaration",
    )
    source = replace_once(
        source,
        "            fetch_totals.insert(id, 0);\n",
        "            fetch_totals.insert(id, 0);\n"
        "            fetch_constraints.insert(id, Vec::new());\n",
        "capture constraint initialization",
    )
    source = replace_once(
        source,
        "            *total = total\n"
        "                .checked_add(f.occurrences)\n"
        "                .ok_or(\"fetch count overflow\")?;\n",
        "            *total = total\n"
        "                .checked_add(f.occurrences)\n"
        "                .ok_or(\"fetch count overflow\")?;\n"
        "            fetch_constraints\n"
        "                .get_mut(f.capture.as_str())\n"
        "                .unwrap()\n"
        "                .push((f.first_seq, f.last_seq, f.occurrences));\n",
        "observation constraint capture",
    )
    source = replace_once(
        source,
        "        for (id, total) in fetch_totals {\n"
        "            if total != self.fetch_captures[id].fetch_count {\n"
        "                return Err(\"fetch summaries do not account for capture count\".into());\n"
        "            }\n"
        "        }\n",
        "        for (id, total) in fetch_totals {\n"
        "            let fetch_count = self.fetch_captures[id].fetch_count;\n"
        "            if total != fetch_count {\n"
        "                return Err(\"fetch summaries do not account for capture count\".into());\n"
        "            }\n"
        "            if !fetch_summaries_realizable(fetch_count, fetch_constraints.get(id).unwrap()) {\n"
        "                return Err(\"fetch summaries are not jointly realizable\".into());\n"
        "            }\n"
        "        }\n",
        "realizability validation",
    )

    PATH.write_text(source)


if __name__ == "__main__":
    main()
