#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/plaid-core/src/merge.rs")
text = path.read_text()

replacements = [
    (
        "    let mut transfers = Vec::<(u64, RomOffset, PhysicalAddr, u32)>::new();\n",
        "    let mut transfers = Vec::<(u64, RomOffset, PhysicalAddr, u32)>::new();\n"
        "    // Successful stores are causal writers even when they leave equal bytes.\n"
        "    // Keep their trace order so a later store can revoke an older DMA origin.\n"
        "    let mut word_stores = Vec::<(u64, PhysicalAddr, EvidenceRefs)>::new();\n",
    ),
    (
        "                let physical = destination.0 & 0x1fffffff;\n"
        "                if out.regions.iter().any(|r| {\n",
        "                let physical = destination.0 & 0x1fffffff;\n"
        "                word_stores.push((event.seq, PhysicalAddr(physical), evidence.clone()));\n"
        "                if out.regions.iter().any(|r| {\n",
    ),
    (
        "                let transfer = state.1.and_then(|physical| {\n"
        "                    transfers\n"
        "                        .iter()\n"
        "                        .rev()\n"
        "                        .find(|(_, _, dest, size)| {\n"
        "                            dest.0 <= physical.0\n"
        "                                && u64::from(dest.0) + u64::from(*size)\n"
        "                                    >= u64::from(physical.0) + words.len() as u64 * 4\n"
        "                        })\n"
        "                        .map(|(seq, offset, dest, _)| {\n"
        "                            (*seq, RomOffset(offset.0 + u64::from(physical.0 - dest.0)))\n"
        "                        })\n"
        "                });\n",
        "                let (transfer, intervening_store_evidence) = if let Some(physical) = state.1 {\n"
        "                    let compiled_end = u64::from(physical.0) + words.len() as u64 * 4;\n"
        "                    if let Some((seq, offset, dest, _)) =\n"
        "                        transfers.iter().rev().find(|(_, _, dest, size)| {\n"
        "                            dest.0 <= physical.0\n"
        "                                && u64::from(dest.0) + u64::from(*size) >= compiled_end\n"
        "                        })\n"
        "                    {\n"
        "                        let store_evidence: EvidenceRefs = word_stores\n"
        "                            .iter()\n"
        "                            .filter(|(store_seq, store, _)| {\n"
        "                                *store_seq > *seq\n"
        "                                    && u64::from(store.0) < compiled_end\n"
        "                                    && u64::from(physical.0) < u64::from(store.0) + 4\n"
        "                            })\n"
        "                            .flat_map(|(_, _, refs)| refs.iter().cloned())\n"
        "                            .collect();\n"
        "                        let transfer = store_evidence.is_empty().then(|| {\n"
        "                            (\n"
        "                                *seq,\n"
        "                                RomOffset(offset.0 + u64::from(physical.0 - dest.0)),\n"
        "                            )\n"
        "                        });\n"
        "                        (transfer, store_evidence)\n"
        "                    } else {\n"
        "                        (None, EvidenceRefs::new())\n"
        "                    }\n"
        "                } else {\n"
        "                    (None, EvidenceRefs::new())\n"
        "                };\n"
        "                let source_tainted = !intervening_store_evidence.is_empty();\n",
    ),
    (
        "                } else if state.3 == 0 && matching.len() == 1 {\n",
        "                } else if !source_tainted && state.3 == 0 && matching.len() == 1 {\n",
    ),
    (
        "                    } else if matching.len() == 1 {\n",
        "                    } else if !source_tainted && matching.len() == 1 {\n",
    ),
    (
        "                let mut imported = ProgramMap::new(out.rom.clone());\n"
        "                imported.evidence = out.evidence.clone();\n"
        "                imported.regions.insert(Region {\n",
        "                let mut imported = ProgramMap::new(out.rom.clone());\n"
        "                imported.evidence = out.evidence.clone();\n"
        "                if source_tainted {\n"
        "                    imported.unresolved.insert(Unresolved {\n"
        "                        kind: \"intervening_executable_store\".into(),\n"
        "                        site: Some(base.clone()),\n"
        "                        detail: \"successful CPU store after candidate DMA overlaps compiled physical bytes; equal content cannot restore superseded copy provenance\".into(),\n"
        "                        evidence: intervening_store_evidence.clone(),\n"
        "                    });\n"
        "                }\n"
        "                imported.regions.insert(Region {\n",
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one patch anchor, found {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)

path.write_text(text)
