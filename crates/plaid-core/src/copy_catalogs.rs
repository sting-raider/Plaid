//! Guarded candidates for indexed ROM-to-RAM descriptor tables.
//!
//! These rows are byte-source candidates only. They do not prove a reachable
//! index bound, execution, runtime binding, or control-flow closure.
use crate::{
    GuestAddr,
    copy_calls::{self, CopyCall},
    discovery::{CodeImage, decode},
    indirect::{MapIndex, prefix_state_in, transfer},
    program::{ProgramMap, RomOffset},
};
use std::collections::{BTreeMap, BTreeSet};

const MAX_IMAGE: u32 = 8 * 1024 * 1024;
const MAX_ROWS: u32 = 256;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Value {
    Unknown,
    Dynamic,
    Scaled(u32),
    Row {
        base: u32,
        stride: u32,
        reg: u8,
    },
    Field {
        base: u32,
        stride: u32,
        row: u8,
        offset: u8,
    },
}

fn reg(word: u32, shift: u32) -> usize {
    ((word >> shift) & 31) as usize
}

fn constant32(value: u64) -> Option<u32> {
    let low = value as u32;
    (value == u64::from(low) || value == i64::from(low as i32) as u64).then_some(low)
}

fn jal_target(word: u32, pc: GuestAddr) -> GuestAddr {
    GuestAddr(((pc.0.wrapping_add(4)) & 0xf000_0000) | ((word & 0x03ff_ffff) << 2))
}

fn valid_plain(word: u32, pc: GuestAddr) -> bool {
    let instruction = decode(word, pc);
    instruction.is_valid()
        && !instruction.has_delay_slot()
        && !instruction.is_trap()
        && !matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
}

fn delay_word(image: &CodeImage, pc: GuestAddr) -> Option<u32> {
    let slot = GuestAddr(pc.0.checked_add(4)?);
    let word = image.instruction_word(slot)?;
    valid_plain(word, slot).then_some(word)
}

fn field_value(value: Value, offset: u8) -> Option<(u32, u32, u8)> {
    match value {
        Value::Field {
            base,
            stride,
            row,
            offset: actual,
        } if actual == offset => Some((base, stride, row)),
        _ => None,
    }
}

fn table_run(
    rom: &[u8],
    image: &CodeImage,
    site: GuestAddr,
    base: u32,
    stride: u32,
    helper: GuestAddr,
) -> Vec<CopyCall> {
    let table = image.slot_view(site, base);
    let word = |record: u32, field: u32| {
        let offset = record.checked_mul(stride)?.checked_add(field)?;
        image.word(GuestAddr(table.checked_add(offset)?))
    };
    let mut rows = Vec::new();
    let mut saw_valid = false;
    let mut leading_null = false;
    for record in 0..MAX_ROWS {
        let Some((source, end, destination)) = word(record, 0)
            .zip(word(record, 4))
            .zip(word(record, 8))
            .map(|((a, b), c)| (a, b, c))
        else {
            break;
        };
        if source == 0 && end == 0 && destination == 0 {
            let all_zero = (0..stride)
                .step_by(4)
                .all(|field| word(record, field) == Some(0));
            if all_zero && !saw_valid && !leading_null {
                leading_null = true;
                continue;
            }
            break;
        }
        let Some(length) = end.checked_sub(source) else {
            if saw_valid {
                break;
            }
            return Vec::new();
        };
        let valid = length > 0
            && length <= MAX_IMAGE
            && source.is_multiple_of(16)
            && end.is_multiple_of(16)
            && u64::from(end) <= rom.len() as u64
            && (0x8000_0000..0x8080_0000).contains(&destination)
            && destination.is_multiple_of(4)
            && u64::from(destination) + u64::from(length) <= 0x8080_0000;
        if !valid {
            if saw_valid {
                break;
            }
            return Vec::new();
        }
        saw_valid = true;
        rows.push((source, end, GuestAddr(destination)));
    }

    let mut by_slot = BTreeMap::<GuestAddr, Vec<(u32, u32)>>::new();
    for (source, end, destination) in rows {
        by_slot.entry(destination).or_default().push((source, end));
    }
    let mut result = Vec::new();
    for (destination, ranges) in by_slot {
        if ranges.len() < 2 {
            continue;
        }
        let nonoverlap = ranges.iter().enumerate().all(|(i, &(start, end))| {
            ranges
                .iter()
                .skip(i + 1)
                .all(|&(other_start, other_end)| end <= other_start || other_end <= start)
        });
        let adjacent = ranges.iter().any(|&(start, end)| {
            ranges
                .iter()
                .any(|&(other_start, other_end)| start == other_end || end == other_start)
        });
        if !nonoverlap || !adjacent {
            continue;
        }
        for &(source, end) in &ranges {
            result.push(CopyCall {
                source: RomOffset(u64::from(source)),
                end: RomOffset(u64::from(end)),
                destination,
                helper,
                callers: BTreeSet::from([site]),
            });
        }
    }
    result
}

fn scan_block(
    rom: &[u8],
    map_index: &MapIndex<'_>,
    image: &CodeImage,
    start: GuestAddr,
    size: u32,
) -> Vec<CopyCall> {
    let Some(end) = start.0.checked_add(size) else {
        return Vec::new();
    };
    let Some((_, mut constants, _)) = prefix_state_in(map_index, image, &image.address(start))
    else {
        return Vec::new();
    };
    let mut values = [Value::Unknown; 32];
    values[0] = Value::Dynamic;
    let mut lui_bases = [false; 32];
    constants[0] = Some(0);
    let mut output = Vec::new();
    let mut pc = start.0;
    while pc < end {
        let site = GuestAddr(pc);
        let Some(word) = image.instruction_word(site) else {
            break;
        };
        let instruction = decode(word, site);
        if !instruction.is_valid()
            || instruction.is_trap()
            || matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
        {
            break;
        }
        if instruction.opcode_name() == "jal" {
            let Some(delay) = delay_word(image, site) else {
                break;
            };
            let helper = jal_target(word, site);
            let args = [
                field_value(values[4], 0),
                field_value(values[5], 4),
                field_value(values[6], 8),
            ];
            let delay_dest = decode(delay, GuestAddr(pc + 4))
                .destination_gpr()
                .unwrap_or(0) as u8;
            if args.iter().all(Option::is_some)
                && args[0]
                    .zip(args[1])
                    .zip(args[2])
                    .is_some_and(|((a, b), c)| {
                        a.0 == b.0
                            && a.0 == c.0
                            && a.1 == b.1
                            && a.1 == c.1
                            && a.2 == b.2
                            && a.2 == c.2
                    })
                && ![4, 5, 6].contains(&delay_dest)
            {
                let (table_base, stride, row) = args[0].unwrap();
                let row_live = matches!(values[row as usize], Value::Row { base, stride: actual, reg } if base == table_base && actual == stride && reg == row);
                if row_live && delay_dest != row && copy_calls::helper_shape(image, helper) {
                    // `prefix_state_in` and `transfer` preserve static constants;
                    // the row expression separately carries the dynamic index.
                    output.extend(table_run(rom, image, site, table_base, stride, helper));
                }
            }
            transfer(delay, GuestAddr(pc + 4), &mut constants);
            if let Some(dest) = decode(delay, GuestAddr(pc + 4)).destination_gpr()
                && dest != 0
            {
                values[dest as usize] = Value::Unknown;
                lui_bases[dest as usize] = false;
            }
            for register in 1..32 {
                if !(16..=23).contains(&register) {
                    constants[register] = None;
                    values[register] = Value::Unknown;
                    lui_bases[register] = false;
                }
            }
            pc = pc.checked_add(8).unwrap_or(end);
            continue;
        }
        if instruction.has_delay_slot() {
            break;
        }

        let op = word >> 26;
        let rs = reg(word, 21);
        let rt = reg(word, 16);
        let imm = word as u16;
        let dest = instruction
            .destination_gpr()
            .map(|register| register as usize);
        let next = match op {
            0 if word & 63 == 0 && values[rt] == Value::Dynamic => {
                let shift = (word >> 6) & 31;
                (4..=8)
                    .contains(&shift)
                    .then_some(Value::Scaled(1 << shift))
            }
            0 if word & 63 == 33 => {
                let row_from = |scaled_reg: usize, base_reg: usize| match (
                    values[scaled_reg],
                    constants[base_reg].and_then(constant32),
                ) {
                    (Value::Scaled(stride), Some(base)) if lui_bases[base_reg] => {
                        Some(Value::Row {
                            base,
                            stride,
                            reg: dest.unwrap_or(0) as u8,
                        })
                    }
                    _ => None,
                };
                row_from(rs, rt).or_else(|| row_from(rt, rs))
            }
            35 => match values[rs] {
                Value::Row {
                    base,
                    stride,
                    reg: row,
                } if [0u16, 4, 8].contains(&imm) => Some(Value::Field {
                    base,
                    stride,
                    row,
                    offset: imm as u8,
                }),
                _ => Some(Value::Dynamic),
            },
            _ => None,
        };
        let base_provenance = match op {
            15 => true,
            9 => lui_bases[rs],
            _ => false,
        };
        transfer(word, site, &mut constants);
        if let Some(dest) = dest
            && dest != 0
        {
            values[dest] = next.unwrap_or(Value::Unknown);
            lui_bases[dest] = base_provenance;
        }
        pc = match pc.checked_add(4) {
            Some(next) => next,
            None => break,
        };
    }
    output
}

/// Infer bounded byte-backed files named by a table consumed by an indexed
/// raw-copy call. This is a candidate catalog, never a bound or closure proof.
pub fn infer(rom: &[u8], map: &ProgramMap, image: &CodeImage) -> Vec<CopyCall> {
    let map_index = MapIndex::new(map);
    let mut catalog =
        BTreeMap::<(RomOffset, RomOffset, GuestAddr, GuestAddr), BTreeSet<GuestAddr>>::new();
    for block in &map.blocks {
        if block.start.image != image.base.image || block.start.generation != image.base.generation
        {
            continue;
        }
        for call in scan_block(rom, &map_index, image, block.start.pc, block.size) {
            catalog
                .entry((call.source, call.end, call.destination, call.helper))
                .or_default()
                .extend(call.callers);
        }
    }
    catalog
        .into_iter()
        .map(|((source, end, destination, helper), callers)| CopyCall {
            source,
            end,
            destination,
            helper,
            callers,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::program::{BasicBlock, CodeAddress, RomIdentity};

    const BASE: u32 = 0x8000_0000;
    const HELPER: u32 = BASE + 0x100;
    const TABLE: u32 = BASE + 0x300;
    const DEST: u32 = 0x8000_4000;
    const CALL_PC: u32 = BASE + 32;

    fn i(op: u32, rs: u32, rt: u32, imm: i16) -> u32 {
        op << 26 | rs << 21 | rt << 16 | imm as u16 as u32
    }
    fn r(rs: u32, rt: u32, rd: u32, sa: u32, funct: u32) -> u32 {
        rs << 21 | rt << 16 | rd << 11 | sa << 6 | funct
    }
    fn lui(rt: u32, value: u16) -> u32 {
        i(15, 0, rt, value as i16)
    }
    fn jal(target: u32) -> u32 {
        3 << 26 | ((target >> 2) & 0x03ff_ffff)
    }

    struct Fixture {
        rom: Vec<u8>,
        map: ProgramMap,
        image: CodeImage,
    }

    fn fixture() -> Fixture {
        let mut words = vec![0; 256];
        // Indexed consumer: a table base, dynamic index scaled by 64, then
        // the three copy arguments. The leading null row is the only sentinel.
        words[0] = lui(8, 0x8000);
        words[1] = i(9, 8, 8, 0x300);
        words[2] = i(35, 16, 9, 0x20); // dynamic index
        words[3] = r(0, 9, 9, 6, 0); // sll t1, t1, 6
        words[4] = r(8, 9, 10, 0, 33); // addu t2, t0, t1
        words[5] = i(35, 10, 4, 0); // lw a0, 0(t2)
        words[6] = i(35, 10, 5, 4); // lw a1, 4(t2)
        words[7] = i(35, 10, 6, 8); // lw a2, 8(t2)
        words[8] = jal(HELPER);
        words[9] = 0;
        words[10] = r(31, 0, 0, 0, 8); // jr ra
        words[11] = 0;

        // The recognized helper's internal copy shape is shared with the
        // simpler copy-call inference.
        let h = (HELPER - BASE) as usize / 4;
        words[h] = r(4, 0, 16, 0, 33);
        words[h + 1] = r(6, 0, 17, 0, 33);
        words[h + 2] = r(5, 4, 18, 0, 35);
        words[h + 3] = r(16, 0, 4, 0, 33);
        words[h + 4] = r(17, 0, 5, 0, 33);
        words[h + 5] = i(9, 0, 6, 32);
        words[h + 6] = jal(BASE + 0x500);
        words[h + 7] = 0;
        words[h + 8] = i(9, 16, 4, 32);
        words[h + 9] = i(9, 17, 5, 32);
        words[h + 10] = i(9, 18, 6, -32);
        words[h + 11] = jal(BASE + 0x500);
        words[h + 12] = 0;
        words[h + 13] = r(31, 0, 0, 0, 8);
        words[h + 14] = 0;

        let table = ((TABLE - BASE) / 4) as usize;
        // Complete all-zero leading record, then deliberately unsorted but
        // nonoverlapping adjacent source ranges. Trailing words are opaque.
        for (row, (source, end)) in [(0, 0), (0x180, 0x1c0), (0x100, 0x140), (0x140, 0x180)]
            .into_iter()
            .enumerate()
        {
            let at = table + row * 16;
            words[at] = source;
            words[at + 1] = end;
            words[at + 2] = if row == 0 { 0 } else { DEST };
            words[at + 3] = (row & 1) as u32;
            if row != 0 {
                words[at + 4] = 0xdead_beef;
            }
        }

        let id = "synthetic-indexed-copy-image".to_owned();
        let image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(BASE),
                image: id.clone(),
                generation: 1,
            },
            words,
            rom_offset: Some(RomOffset(0)),
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        };
        let rom = vec![0; 0x400];
        let mut map = ProgramMap::new(RomIdentity {
            sha256: "0".repeat(64),
            size: rom.len() as u64,
        });
        map.blocks.insert(BasicBlock {
            start: CodeAddress {
                pc: GuestAddr(BASE),
                image: id,
                generation: 1,
            },
            size: 40,
            delay_slot_entry: false,
            evidence: BTreeSet::new(),
        });
        Fixture { rom, map, image }
    }

    fn write_row(image: &mut CodeImage, row: usize, source: u32, end: u32, dest: u32) {
        let index = ((TABLE - BASE) / 4) as usize + row * 16;
        image.words[index] = source;
        image.words[index + 1] = end;
        image.words[index + 2] = dest;
    }

    fn rebase(mut f: Fixture, base: u32) -> Fixture {
        let new_table = base + 0x300;
        let high = new_table.wrapping_add(0x8000) >> 16;
        let low = new_table as u16 as i16;
        f.image.base.pc = GuestAddr(base);
        f.image.words[0] = lui(8, high as u16);
        f.image.words[1] = i(9, 8, 8, low);
        f.image.words[8] = jal(base + 0x100);
        let helper = 0x100usize / 4;
        f.image.words[helper + 6] = jal(base + 0x500);
        f.image.words[helper + 11] = jal(base + 0x500);
        let old = f.map.blocks.first().expect("loader block").clone();
        f.map.blocks.clear();
        f.map.blocks.insert(BasicBlock {
            start: CodeAddress {
                pc: GuestAddr(base),
                image: old.start.image,
                generation: old.start.generation,
            },
            size: old.size,
            delay_slot_entry: old.delay_slot_entry,
            evidence: old.evidence,
        });
        f
    }

    #[test]
    fn collects_adjacent_slot_files_from_a_dynamic_64_byte_table() {
        let f = fixture();
        let calls = infer(&f.rom, &f.map, &f.image);
        assert_eq!(calls.len(), 3);
        assert_eq!(
            calls.iter().map(|c| c.source.0).collect::<Vec<_>>(),
            [0x100, 0x140, 0x180]
        );
        assert!(calls.iter().all(|c| c.destination == GuestAddr(DEST)));
        assert!(
            calls
                .iter()
                .all(|c| c.callers == BTreeSet::from([GuestAddr(CALL_PC)]))
        );
    }

    #[test]
    fn supports_other_power_of_two_strides_and_shifted_images() {
        let mut f = fixture();
        f.image.words[3] = r(0, 9, 9, 5, 0); // stride 32
        let table = ((TABLE - BASE) / 4) as usize;
        f.image.words[table..].fill(0);
        for (row, (source, end)) in [(0, 0), (0x180, 0x1c0), (0x100, 0x140), (0x140, 0x180)]
            .into_iter()
            .enumerate()
        {
            let at = table + row * 8;
            f.image.words[at] = source;
            f.image.words[at + 1] = end;
            f.image.words[at + 2] = if row == 0 { 0 } else { DEST };
            if row != 0 {
                f.image.words[at + 4] = 0xdead_beef;
            }
        }
        assert_eq!(infer(&f.rom, &f.map, &f.image).len(), 3);

        let f = rebase(fixture(), 0x8010_0000);
        let calls = infer(&f.rom, &f.map, &f.image);
        assert_eq!(calls.len(), 3);
        assert!(
            calls
                .iter()
                .all(|call| call.helper == GuestAddr(0x8010_0100))
        );
        assert!(
            calls
                .iter()
                .all(|call| call.callers == BTreeSet::from([GuestAddr(0x8010_0020)]))
        );
    }

    #[test]
    fn rejects_pre_call_argument_and_row_pointer_clobbers() {
        for clobbered_register in [4, 10] {
            let mut f = fixture();
            f.image.words[8] = i(9, 0, clobbered_register, 1);
            f.image.words[9] = jal(HELPER);
            f.image.words[10] = 0;
            let old = f.map.blocks.first().expect("loader block").clone();
            f.map.blocks.clear();
            f.map.blocks.insert(BasicBlock { size: 44, ..old });
            assert!(infer(&f.rom, &f.map, &f.image).is_empty());
        }
    }

    #[test]
    fn rejects_clobbers_wrong_stride_wrong_field_order_and_unknown_helper() {
        let mut f = fixture();
        f.image.words[9] = i(9, 0, 4, 1); // delay slot clobbers a0
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        f = fixture();
        f.image.words[3] = r(0, 9, 9, 5, 0); // stride 32, not 64
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        f = fixture();
        f.image.words[6] = i(35, 10, 5, 8);
        f.image.words[7] = i(35, 10, 6, 4);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        f = fixture();
        f.image.words[8] = jal(BASE + 0x500);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
    }

    #[test]
    fn rejects_nonadjacent_overlapping_out_of_bounds_and_broken_runs() {
        let mut f = fixture();
        write_row(&mut f.image, 3, 0x200, 0x240, DEST); // nonadjacent
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        f = fixture();
        write_row(&mut f.image, 3, 0x120, 0x160, DEST); // overlaps row 2
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        f = fixture();
        write_row(&mut f.image, 2, 0x3f0, 0x430, DEST); // past ROM
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        f = fixture();
        write_row(&mut f.image, 1, 0x180, 0x1c0, 0x807f_ffd0); // RAM end overflow
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        f = fixture();
        write_row(&mut f.image, 2, 0, 0, 0); // run stops before later adjacent rows
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
    }

    #[test]
    fn literal_table_without_indexed_loader_use_is_not_cataloged() {
        let mut f = fixture();
        f.image.words[3] = 0;
        f.image.words[4] = 0;
        f.image.words[5] = lui(4, 0);
        f.image.words[6] = i(9, 4, 4, 0x100);
        f.image.words[7] = lui(5, 0);
        f.image.words[8] = i(9, 5, 5, 0x140);
        f.image.words[9] = lui(6, 0x8000);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
    }
}
