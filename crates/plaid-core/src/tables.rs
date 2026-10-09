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
    let shift_pc = GuestAddr(pc.0.checked_sub(12)?);
    let shift = image.word(shift_pc)?;
    if load >> 26 != 35
        || field(load, 16) != field(jump, 21)
        || add >> 26 != 0
        || add & 63 != 33
        || field(add, 11) != field(load, 21)
        || shift >> 26 != 0
        || shift & 63 != 0
        || (shift >> 6) & 31 != 2
    {
        return None;
    }
    let index = field(shift, 16);
    let scale = field(shift, 11);
    if scale == 0 || index == 0 {
        return None;
    }
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
    if blocks.len() != 1 || blocks[0].start.pc.0 > shift_pc.0 {
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
        || map.entries.keys().any(|address| bypasses_guard(address))
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
    if edge.delay_slot != DelaySlot::None {
        let ds = GuestAddr(edge.site.pc.0.checked_add(4)?);
        let slot = image.word(ds)?;
        let instruction = decode(slot, ds);
        if !instruction.is_valid()
            || instruction.has_delay_slot()
            || instruction.destination_gpr() == Some(u32::from(index))
        {
            return None;
        }
        prefix.extend(slot.to_be_bytes());
    }
    let mut values = [None; 32];
    values[0] = Some(0);
    let mut current = block.start.pc;
    while current.0 < shift_pc.0 {
        let word = image.word(current)?;
        let instruction = decode(word, current);
        if !instruction.is_valid()
            || instruction.has_delay_slot()
            || instruction.is_trap()
            || instruction.destination_gpr() == Some(u32::from(index))
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

pub(crate) fn analyze(map: &ProgramMap, image: &CodeImage) -> Result<ProgramMap, String> {
    let mut out = map.clone();
    for old in &map.indirect_sites {
        let Some(mut table) = pattern(map, image, old) else {
            continue;
        };
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
        let detail = serde_json::to_string(&table).map_err(|e| e.to_string())?;
        let id = format!("table-candidates:{}", sha256(detail.as_bytes()));
        out.evidence.insert(
            id.clone(),
            Evidence {
                kind: EvidenceKind::Static,
                producer: "plaid-pointer-table-candidates/v0".into(),
                revision: "0".into(),
                detail,
            },
        );
        let refs: EvidenceRefs = [id.clone()].into();
        if let Some(words) = words {
            let mut site = old.clone();
            out.indirect_sites.remove(old);
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
            out.indirect_sites.insert(site);
            out.unresolved.insert(Unresolved { kind: "pointer_table_immutability_unproven".into(), site: Some(old.site.clone()),
                detail: "bounded snapshot candidates do not prove table contents or exhaustive runtime targets".into(), evidence: refs });
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
