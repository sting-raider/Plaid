//! Bounded pointer-table candidates from a guarded scalar dispatch pattern.
//! Snapshot reads are hypotheses: data immutability is not established here.
use crate::{
    EvidenceKind, GuestAddr,
    discovery::{CodeImage, decode},
    indirect::{signed_word, transfer},
    program::*,
    rom::sha256,
};
use serde::Serialize;

const MAX_ENTRIES: u32 = 256;

#[derive(Serialize)]
struct TableEvidence {
    site: CodeAddress,
    load_pc: GuestAddr,
    guard_pc: GuestAddr,
    index_register: u8,
    table_start: GuestAddr,
    count: u32,
    prefix_sha256: String,
    snapshot_sha256: Option<String>,
    assumptions: [&'static str; 2],
}

fn field(word: u32, shift: u32) -> u8 {
    ((word >> shift) & 31) as u8
}

fn pattern(map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> Option<TableEvidence> {
    if site.site.image != image.base.image || site.site.generation != image.base.generation {
        return None;
    }
    let pc = site.site.pc;
    let jump = image.word(pc)?;
    if jump >> 26 != 0 || !matches!(jump & 63, 8 | 9) {
        return None;
    }
    let load_pc = GuestAddr(pc.0.checked_sub(4)?);
    let load = image.word(load_pc)?;
    let add_pc = GuestAddr(pc.0.checked_sub(8)?);
    let add = image.word(add_pc)?;
    if load >> 26 != 35
        || field(load, 16) != field(jump, 21)
        || add >> 26 != 0
        || add & 63 != 33
        || field(add, 11) != field(load, 21)
    {
        return None;
    }
    let is_shift = |w: u32| {
        w >> 26 == 0 && w & 63 == 0 && (w >> 6) & 31 == 2 && field(w, 11) != 0 && field(w, 16) != 0
    };
    let blocks: Vec<_> = map
        .blocks
        .iter()
        .filter(|b| {
            b.start.image == site.site.image
                && b.start.generation == site.site.generation
                && !b.delay_slot_entry
                && GuestRange {
                    start: b.start.pc,
                    size: b.size,
                }
                .contains(pc)
        })
        .collect();
    if blocks.len() != 1 || blocks[0].start.pc.0 > add_pc.0 {
        return None;
    }
    let block = blocks[0];
    let bypasses_guard = |address: &CodeAddress| {
        address.image == site.site.image
            && address.generation == site.site.generation
            && address.pc.0 > block.start.pc.0
            && address.pc.0 <= pc.0
    };
    if map.entries.contains_key(&block.start)
        || map.entries.keys().any(&bypasses_guard)
        || map
            .direct_edges
            .iter()
            .any(|edge| bypasses_guard(&edge.target))
        || map.indirect_sites.iter().any(|s| {
            s.candidates
                .keys()
                .chain(s.observed.keys())
                .any(|address| address == &block.start || bypasses_guard(address))
        })
    {
        return None;
    }
    let incoming: Vec<_> = map
        .direct_edges
        .iter()
        .filter(|e| e.target == block.start)
        .collect();
    if incoming.len() != 1 {
        return None;
    }
    let edge = incoming[0];
    if edge.site.image != image.base.image || edge.site.generation != image.base.generation {
        return None;
    }
    let branch = image.word(edge.site.pc)?;
    let compare_pc = GuestAddr(edge.site.pc.0.checked_sub(4)?);
    // The index scale is the SLL just before the add or, as GCC schedules it,
    // the delay slot of a non-likely guard branch, which runs on both paths.
    let adjacent = GuestAddr(add_pc.0.checked_sub(4)?);
    let (shift_pc, in_slot) =
        if adjacent.0 >= block.start.pc.0 && image.word(adjacent).is_some_and(is_shift) {
            (adjacent, false)
        } else if matches!(branch >> 26, 4 | 5)
            && image
                .word(GuestAddr(edge.site.pc.0.checked_add(4)?))
                .is_some_and(is_shift)
        {
            (GuestAddr(edge.site.pc.0 + 4), true)
        } else {
            return None;
        };
    let shift = image.word(shift_pc)?;
    let index = field(shift, 16);
    let scale = field(shift, 11);
    let base = if field(add, 21) == scale {
        field(add, 16)
    } else if field(add, 16) == scale {
        field(add, 21)
    } else {
        return None;
    };
    if base == scale {
        return None;
    }

    // The table bound is established by the SLTIU immediately before this
    // branch. Alternate execution that enters the branch can reuse an
    // unconstrained/stale flag and still select the dispatch edge. When the
    // selected dispatch is the sequential branch fallthrough, entering the
    // physical delay-slot word also skips both compare and branch and then
    // falls directly into the dispatch block. Keep image/generation identity
    // explicit; equal guest PCs in another executable generation are unrelated.
    let bypasses_compare = |address: &CodeAddress| {
        if address.image != site.site.image || address.generation != site.site.generation {
            return false;
        }
        if address.pc == edge.site.pc {
            return true;
        }
        edge.site.pc.0.checked_add(8) == Some(block.start.pc.0)
            && edge.site.pc.0.checked_add(4) == Some(address.pc.0)
    };
    if map.entries.keys().any(&bypasses_compare)
        || map
            .direct_edges
            .iter()
            .any(|candidate| bypasses_compare(&candidate.target))
        || map.indirect_sites.iter().any(|candidate| {
            candidate
                .candidates
                .keys()
                .chain(candidate.observed.keys())
                .any(&bypasses_compare)
        })
    {
        return None;
    }

    let compare = image.word(compare_pc)?;
    if compare >> 26 != 11 || field(compare, 21) != index {
        return None;
    } // SLTIU
    let count = u32::from(compare as u16);
    let flag = field(compare, 16);
    if count == 0 || count > MAX_ENTRIES || flag == 0 {
        return None;
    }
    if !((field(branch, 21) == flag && field(branch, 16) == 0)
        || (field(branch, 16) == flag && field(branch, 21) == 0))
    {
        return None;
    }
    let guarded = matches!(branch >> 26, 4 | 20) && edge.kind == EdgeKind::Fallthrough
        || matches!(branch >> 26, 5 | 21) && edge.kind == EdgeKind::Branch;
    if !guarded {
        return None;
    }
    let mut prefix = Vec::new();
    prefix.extend(compare.to_be_bytes());
    prefix.extend(branch.to_be_bytes());
    if edge.delay_slot != DelaySlot::None && !in_slot {
        let ds = GuestAddr(edge.site.pc.0.checked_add(4)?);
        let slot = image.word(ds)?;
        let instruction = decode(slot, ds);
        if !instruction.is_valid()
            || instruction.has_delay_slot()
            || instruction.is_trap()
            || matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
            || instruction.destination_gpr() == Some(u32::from(index))
        {
            return None;
        }
        prefix.extend(slot.to_be_bytes());
    }
    let mut values = [None; 32];
    values[0] = Some(0);
    // Before the scale, the index must survive; after it, the scaled index.
    let (end, kept) = if in_slot {
        (add_pc, scale)
    } else {
        (shift_pc, index)
    };
    let mut current = block.start.pc;
    while current.0 < end.0 {
        let word = image.word(current)?;
        let instruction = decode(word, current);
        if !instruction.is_valid()
            || instruction.has_delay_slot()
            || instruction.is_trap()
            || instruction.destination_gpr() == Some(u32::from(kept))
        {
            return None;
        }
        transfer(word, current, &mut values);
        prefix.extend(word.to_be_bytes());
        current = GuestAddr(current.0.checked_add(4)?);
    }
    let value = values[base as usize]?;
    let low = value as u32;
    if value != u64::from(low) && value != signed_word(low) {
        return None;
    }
    let table_start = GuestAddr(low.wrapping_add_signed(i32::from(load as i16)));
    if !table_start.0.is_multiple_of(4)
        || u64::from(table_start.0) + u64::from(count) * 4 > 1u64 << 32
    {
        return None;
    }
    for word in [shift, add, load, jump] {
        prefix.extend(word.to_be_bytes());
    }
    Some(TableEvidence {
        site: site.site.clone(),
        load_pc,
        guard_pc: edge.site.pc,
        index_register: index,
        table_start,
        count,
        prefix_sha256: sha256(&prefix),
        snapshot_sha256: None,
        assumptions: [
            "recognized scalar guard pattern suggests this dispatch index bound",
            "table snapshot is not proven immutable during execution",
        ],
    })
}

pub const PRODUCER: &str = "plaid-pointer-table-candidates/v0";

/// The recognized table, its snapshot words and the evidence detail.
fn evidence(
    map: &ProgramMap,
    image: &CodeImage,
    site: &IndirectSite,
) -> Option<(TableEvidence, Option<Vec<u32>>, String)> {
    let mut table = pattern(map, image, site)?;
    let words: Option<Vec<_>> = (0..table.count)
        .map(|n| image.word(GuestAddr(table.table_start.0 + n * 4)))
        .collect();
    if let Some(words) = &words {
        table.snapshot_sha256 = Some(sha256(
            &words
                .iter()
                .flat_map(|word| word.to_be_bytes())
                .collect::<Vec<_>>(),
        ));
    }
    let detail = serde_json::to_string(&table).ok()?;
    Some((table, words, detail))
}

/// A table proof closes a site only when it is recomputed from the current CFG
/// and bytes, its snapshot is complete and aligned, and the candidates are
/// exactly the snapshot targets. Whether the table may be treated as
/// immutable is a scope decision (ADR-0132), not part of this check.
pub fn verify(map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> bool {
    let Some(e) = site
        .closed_proof
        .as_ref()
        .and_then(|id| map.evidence.get(id))
    else {
        return false;
    };
    if e.kind != EvidenceKind::Static
        || e.producer != PRODUCER
        || site.link_register.is_some()
        || site.delay_slot != DelaySlot::Always
    {
        return false;
    }
    let Some((_, Some(words), detail)) = evidence(map, image, site) else {
        return false;
    };
    let targets: std::collections::BTreeSet<_> =
        words.iter().map(|w| image.address(GuestAddr(*w))).collect();
    detail == e.detail
        && words.iter().all(|w| w.is_multiple_of(4))
        && site
            .candidates
            .keys()
            .cloned()
            .collect::<std::collections::BTreeSet<_>>()
            == targets
        && site.observed.keys().all(|a| targets.contains(a))
}

/// Guest bytes of a verified table, as (start, entry count).
pub fn table_range(
    map: &ProgramMap,
    image: &CodeImage,
    site: &IndirectSite,
) -> Option<(GuestAddr, u32)> {
    if !verify(map, image, site) {
        return None;
    }
    let (table, _, _) = evidence(map, image, site)?;
    Some((table.table_start, table.count))
}

pub(crate) fn analyze(map: &ProgramMap, image: &CodeImage) -> Result<ProgramMap, String> {
    let mut out = map.clone();
    for old in &map.indirect_sites {
        let Some((table, words, detail)) = evidence(map, image, old) else {
            continue;
        };
        let id = format!("table-candidates:{}", sha256(detail.as_bytes()));
        out.evidence.insert(
            id.clone(),
            Evidence {
                kind: EvidenceKind::Static,
                producer: PRODUCER.into(),
                revision: "0".into(),
                detail,
            },
        );
        let refs: EvidenceRefs = [id.clone()].into();
        if let Some(words) = words {
            let mut site = old.clone();
            out.indirect_sites.remove(old);
            let fresh = site.candidates.is_empty() && site.closed_proof.is_none();
            let aligned = words.iter().all(|w| w.is_multiple_of(4));
            for (n, target) in words.into_iter().enumerate() {
                if target.is_multiple_of(4) {
                    site.candidates
                        .entry(image.address(GuestAddr(target)))
                        .or_default()
                        .insert(id.clone());
                } else {
                    out.unresolved.insert(Unresolved {
                        kind: "invalid_pointer_table_entry".into(),
                        site: Some(old.site.clone()),
                        detail: format!(
                            "unaligned snapshot pointer {target:08x} at table index {n}"
                        ),
                        evidence: refs.clone(),
                    });
                }
            }
            // Closing is only a claim; `verify` rechecks it and only the
            // guarded scope accepts it.
            if (fresh || site.closed_proof.as_deref() == Some(id.as_str()))
                && aligned
                && site.link_register.is_none()
                && site
                    .observed
                    .keys()
                    .all(|a| site.candidates.contains_key(a))
            {
                site.closed_proof = Some(id.clone());
            }
            out.indirect_sites.insert(site);
            out.unresolved.insert(Unresolved {
                kind: "pointer_table_immutability_unproven".into(),
                site: Some(old.site.clone()),
                detail: "bounded snapshot candidates do not prove table contents or exhaustive runtime targets".into(),
                evidence: refs.clone(),
            });
            out.unresolved.insert(Unresolved {
                kind: "pointer_table_target_identity_unproven".into(),
                site: Some(old.site.clone()),
                detail: "numeric table targets do not prove target image/generation, mapping context, cache-resident generation or executable lifetime".into(),
                evidence: refs,
            });
        } else {
            out.unresolved.insert(Unresolved {
                kind: "pointer_table_source_missing".into(),
                site: Some(old.site.clone()),
                detail: format!(
                    "{} entries at {:?} lack a complete supplied memory snapshot",
                    table.count, table.table_start
                ),
                evidence: refs,
            });
        }
    }
    out.validate()?;
    Ok(out)
}
