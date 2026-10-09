#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/plaid-core/src/merge.rs")
source = path.read_text()
old = '''    // Multiple byte extents or direct destinations for an identical identity
    // remain visible. Different generations/images are intentionally distinct.
    for a in &out.blocks {
        for b in &out.blocks {
            if a.start == b.start && (a.size != b.size || a.delay_slot_entry != b.delay_slot_entry)
            {
                let evidence = a.evidence.union(&b.evidence).cloned().collect();
                out.unresolved.insert(Unresolved {
                    kind: "conflicting_block".into(),
                    site: Some(a.start.clone()),
                    detail: "same execution identity has different block extent or entry semantics"
                        .into(),
                    evidence,
                });
            }
        }
    }
    for a in &out.direct_edges {
        for b in &out.direct_edges {
            if a.site == b.site
                && a.kind == b.kind
                && (a.target != b.target || a.delay_slot != b.delay_slot)
            {
                out.unresolved.insert(Unresolved {
                    kind: "conflicting_direct_edge".into(),
                    site: Some(a.site.clone()),
                    detail: "same direct site/kind has contradictory target or slot semantics"
                        .into(),
                    evidence: a.evidence.union(&b.evidence).cloned().collect(),
                });
            }
        }
    }
'''
new = '''    // Multiple byte extents or direct destinations for an identical identity
    // remain visible. Different generations/images are intentionally distinct.
    // Index only the exact identity keys used by the quadratic conflict scan.
    // Every participating evidence reference is retained if a key has >1
    // semantic variant; no byte/value equality is consulted.
    let mut block_groups =
        BTreeMap::<CodeAddress, ((u32, bool), bool, EvidenceRefs)>::new();
    for block in &out.blocks {
        let signature = (block.size, block.delay_slot_entry);
        let slot = block_groups
            .entry(block.start.clone())
            .or_insert_with(|| (signature, false, EvidenceRefs::new()));
        if slot.0 != signature {
            slot.1 = true;
        }
        slot.2.extend(block.evidence.clone());
    }
    for (start, (_, conflicting, evidence)) in block_groups {
        if conflicting {
            out.unresolved.insert(Unresolved {
                kind: "conflicting_block".into(),
                site: Some(start),
                detail: "same execution identity has different block extent or entry semantics"
                    .into(),
                evidence,
            });
        }
    }
    let mut edge_groups = BTreeMap::<
        (CodeAddress, EdgeKind),
        ((CodeAddress, DelaySlot), bool, EvidenceRefs),
    >::new();
    for edge in &out.direct_edges {
        let signature = (edge.target.clone(), edge.delay_slot);
        let slot = edge_groups
            .entry((edge.site.clone(), edge.kind))
            .or_insert_with(|| (signature.clone(), false, EvidenceRefs::new()));
        if slot.0 != signature {
            slot.1 = true;
        }
        slot.2.extend(edge.evidence.clone());
    }
    for ((site, _), (_, conflicting, evidence)) in edge_groups {
        if conflicting {
            out.unresolved.insert(Unresolved {
                kind: "conflicting_direct_edge".into(),
                site: Some(site),
                detail: "same direct site/kind has contradictory target or slot semantics".into(),
                evidence,
            });
        }
    }
'''
if source.count(old) != 1:
    raise SystemExit("refusing to patch: expected quadratic conflict block is not unique/exact")
path.write_text(source.replace(old, new))
