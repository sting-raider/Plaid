//! ROM-backed candidates for structurally observed TLB executable copies.
//!
//! These records identify bounded byte sources and virtual addresses. They do
//! not prove that a loader ran, that its index is bounded, or that a mapping or
//! executable lifetime remains valid.
use crate::{
    GuestAddr, copy_calls,
    discovery::{CodeImage, decode},
    program::{BasicBlock, ProgramMap, RomOffset},
};
use std::collections::BTreeSet;

const MAX_IMAGE: u32 = 8 * 1024 * 1024;
const MAX_ROWS: u32 = 256;
const ROW_STRIDE: u32 = 6 * 4;
const MAX_CALL_GAP: u32 = 32;
const MAX_WINDOW_WORDS: u32 = 256;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct TableWitness {
    pub base: GuestAddr,
    pub stride: u32,
}

/// A byte-bounded ROM file proposed as TLB-backed executable content.
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Candidate {
    pub source: RomOffset,
    pub end: RomOffset,
    pub virtual_base: GuestAddr,
    pub entry: GuestAddr,
    pub text_size: u32,
    /// The loader's copy-helper call site, when observed structurally.
    pub caller: Option<GuestAddr>,
    pub helper: Option<GuestAddr>,
    pub table: Option<TableWitness>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Value {
    Unknown,
    Constant(u32),
    Index {
        origin: u8,
        scale: u32,
    },
    Row {
        base: u32,
        origin: u8,
        stride: u32,
    },
    Field {
        base: u32,
        origin: u8,
        stride: u32,
        offset: u8,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Row {
    base: u32,
    origin: u8,
    stride: u32,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mapping {
    Indexed(Row),
    Fixed(u32),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct MapCall {
    mapping: Mapping,
    gap: u32,
}

fn reg(word: u32, shift: u32) -> usize {
    ((word >> shift) & 31) as usize
}

fn valid_plain(word: u32, pc: GuestAddr) -> bool {
    let instruction = decode(word, pc);
    instruction.is_valid()
        && !instruction.has_delay_slot()
        && !instruction.is_trap()
        && !matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
}

fn jal_target(word: u32, pc: GuestAddr) -> GuestAddr {
    GuestAddr(((pc.0.wrapping_add(4)) & 0xf000_0000) | ((word & 0x03ff_ffff) << 2))
}

fn delay(image: &CodeImage, pc: GuestAddr) -> Option<u32> {
    let slot = GuestAddr(pc.0.checked_add(4)?);
    let word = image.instruction_word(slot)?;
    valid_plain(word, slot).then_some(word)
}

fn add_index(left: Value, right: Value) -> Option<Value> {
    match (left, right) {
        (Value::Constant(0), value) | (value, Value::Constant(0)) => Some(value),
        (Value::Constant(base), Value::Index { origin, scale })
        | (Value::Index { origin, scale }, Value::Constant(base)) => Some(Value::Row {
            base,
            origin,
            stride: scale,
        }),
        (
            Value::Constant(base),
            Value::Row {
                base: row_base,
                origin,
                stride,
            },
        )
        | (
            Value::Row {
                base: row_base,
                origin,
                stride,
            },
            Value::Constant(base),
        ) if base == 0 => Some(Value::Row {
            base: row_base,
            origin,
            stride,
        }),
        (
            Value::Row {
                base,
                origin: left_origin,
                stride: left_stride,
            },
            Value::Index {
                origin: right_origin,
                scale: right_scale,
            },
        )
        | (
            Value::Index {
                origin: right_origin,
                scale: right_scale,
            },
            Value::Row {
                base,
                origin: left_origin,
                stride: left_stride,
            },
        ) if left_origin == right_origin && left_stride == right_scale => Some(Value::Row {
            base,
            origin: left_origin,
            stride: left_stride,
        }),
        (
            Value::Index {
                origin: a,
                scale: x,
            },
            Value::Index {
                origin: b,
                scale: y,
            },
        ) if a == b => Some(Value::Index {
            origin: a,
            scale: x.checked_add(y)?,
        }),
        (Value::Constant(a), Value::Constant(b)) => Some(Value::Constant(a.wrapping_add(b))),
        _ => None,
    }
}

/// Apply the small address/index fragment needed by the recognizer. Unknown
/// writes erase symbolic facts; calls are handled separately below.
fn step(word: u32, pc: GuestAddr, image: &CodeImage, values: &mut [Value; 32]) {
    let instruction = decode(word, pc);
    let Some(dest) = instruction
        .destination_gpr()
        .map(|register| register as usize)
    else {
        return;
    };
    if dest == 0 {
        return;
    }
    let rs = reg(word, 21);
    let rt = reg(word, 16);
    let immediate = word as u16;
    let signed_immediate = i32::from(word as i16) as u32;
    let next = match word >> 26 {
        15 => Some(Value::Constant(u32::from(immediate) << 16)),
        9 | 25 => match values[rs] {
            Value::Constant(value) => Some(Value::Constant(value.wrapping_add(signed_immediate))),
            value if immediate == 0 => Some(value),
            _ => None,
        },
        13 => match values[rs] {
            Value::Constant(value) => Some(Value::Constant(value | u32::from(immediate))),
            value if immediate == 0 => Some(value),
            _ => None,
        },
        35 => match values[rs] {
            Value::Row {
                base,
                origin,
                stride,
            } => {
                let offset = immediate as u8;
                (u16::from(offset) == immediate
                    && immediate.is_multiple_of(4)
                    && u32::from(offset) < stride)
                    .then_some(Value::Field {
                        base,
                        origin,
                        stride,
                        offset,
                    })
            }
            Value::Constant(base) => {
                let address = base.wrapping_add(signed_immediate);
                image.word(GuestAddr(address)).map(Value::Constant)
            }
            _ => None,
        },
        0 => match word & 63 {
            0 => match values[rt] {
                Value::Index { origin, scale } => scale
                    .checked_shl((word >> 6) & 31)
                    .map(|scale| Value::Index { origin, scale }),
                Value::Constant(value) => {
                    Some(Value::Constant(value.wrapping_shl((word >> 6) & 31)))
                }
                _ => None,
            },
            33 | 45 => add_index(values[rs], values[rt]),
            37 if rs == 0 => Some(values[rt]),
            37 if rt == 0 => Some(values[rs]),
            _ => None,
        },
        _ => None,
    };
    values[dest] = next.unwrap_or(Value::Unknown);
    values[0] = Value::Constant(0);
}

fn after_call(delay_word: u32, pc: GuestAddr, image: &CodeImage, values: &mut [Value; 32]) {
    step(delay_word, pc, image, values);
    // MIPS o32 caller-saved GPRs, including all four argument registers.
    for register in [
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 24, 25, 31,
    ] {
        values[register] = Value::Unknown;
    }
    values[0] = Value::Constant(0);
}

fn mapped_virtual(address: u32) -> bool {
    // KSEG0/KSEG1 are direct-mapped and do not need the TLB catalog.
    !(0x8000_0000..0xc000_0000).contains(&address) && address.is_multiple_of(0x1000)
}

fn map_call(arg2: Value) -> Option<Mapping> {
    match arg2 {
        Value::Field {
            base,
            origin,
            stride,
            offset: 12,
        } => Some(Mapping::Indexed(Row {
            base,
            origin,
            stride,
        })),
        Value::Constant(address) if mapped_virtual(address) => Some(Mapping::Fixed(address)),
        _ => None,
    }
}

fn field(value: Value, offset: u8) -> Option<(u32, u8, u32)> {
    match value {
        Value::Field {
            base,
            origin,
            stride,
            offset: actual,
        } if actual == offset => Some((base, origin, stride)),
        _ => None,
    }
}

fn rom_file(rom: &[u8], source: u32, end: u32) -> Option<(&[u8], u32)> {
    let size = end.checked_sub(source)?;
    if size == 0
        || size > MAX_IMAGE
        || !source.is_multiple_of(16)
        || !end.is_multiple_of(16)
        || u64::from(end) > rom.len() as u64
    {
        return None;
    }
    let bytes = rom.get(source as usize..end as usize)?;
    Some((bytes, size))
}

fn descriptor(
    rom: &[u8],
    source: u32,
    end: u32,
    virtual_base: u32,
    entry: u32,
) -> Option<(Candidate, u32)> {
    if !mapped_virtual(virtual_base) || !entry.is_multiple_of(4) {
        return None;
    }
    let (bytes, size) = rom_file(rom, source, end)?;
    let virtual_end = u64::from(virtual_base).checked_add(u64::from(size))?;
    if virtual_end > 1u64 << 32 {
        return None;
    }
    // Mapped bridge files can end in register tail thunks rather than JR $ra.
    // This is a bounded layout proposal; CFG discovery and byte binding remain
    // required before any of these bytes can execute natively.
    let mut terminal = None;
    for (n, chunk) in bytes.as_chunks::<4>().0.iter().enumerate() {
        let word = u32::from_be_bytes(*chunk);
        if matches!(word >> 26, 18 | 19 | 50 | 54 | 58 | 62)
            || !decode(word, GuestAddr(virtual_base.wrapping_add(n as u32 * 4))).is_valid()
        {
            break;
        }
        if word >> 26 == 0 && word & 63 == 8 && (n + 2) * 4 <= bytes.len() {
            terminal = Some((n as u32 + 2) * 4);
        }
    }
    let text_size = terminal.unwrap_or(size);
    if text_size == 0
        || text_size > size
        || !text_size.is_multiple_of(4)
        || (virtual_base < 0x8000_0000 && virtual_end > 0x8000_0000)
        || u64::from(entry) < u64::from(virtual_base)
        || u64::from(entry) >= u64::from(virtual_base) + u64::from(text_size)
    {
        return None;
    }
    Some((
        Candidate {
            source: RomOffset(u64::from(source)),
            end: RomOffset(u64::from(end)),
            virtual_base: GuestAddr(virtual_base),
            entry: GuestAddr(entry),
            text_size,
            caller: None,
            helper: None,
            table: None,
        },
        size,
    ))
}

fn indexed_candidates(
    rom: &[u8],
    image: &CodeImage,
    table_site: GuestAddr,
    row: Row,
    caller: GuestAddr,
    helper: GuestAddr,
) -> Vec<Candidate> {
    if row.stride != ROW_STRIDE || !row.base.is_multiple_of(4) {
        return Vec::new();
    }
    let table = image.slot_view(table_site, row.base);
    let read = |index: u32, field: u32| {
        let at = index.checked_mul(row.stride)?.checked_add(field)?;
        image.word(GuestAddr(table.checked_add(at)?))
    };
    let mut run = Vec::<(u32, Candidate)>::new();
    let mut output = Vec::new();
    let flush = |run: &mut Vec<(u32, Candidate)>, output: &mut Vec<Candidate>| {
        if run.len() >= 2 {
            output.extend(run.drain(..).map(|(_, candidate)| candidate));
        } else {
            run.clear();
        }
    };
    for index in 0..MAX_ROWS {
        let Some(words) = (0..6)
            .map(|field| read(index, field * 4))
            .collect::<Option<Vec<_>>>()
        else {
            break;
        };
        if words.iter().all(|word| *word == 0) {
            // Empty records are sparse IDs, not a proved catalog terminator.
            continue;
        }
        // Only the entry, source range and mapped virtual page define executable
        // bytes. The two trailing fields remain opaque allocation metadata.
        if let Some((mut candidate, _)) = descriptor(rom, words[1], words[2], words[3], words[0]) {
            candidate.caller = Some(caller);
            candidate.helper = Some(helper);
            candidate.table = Some(TableWitness {
                base: GuestAddr(row.base),
                stride: row.stride,
            });
            run.push((index, candidate));
        } else {
            flush(&mut run, &mut output);
        }
    }
    flush(&mut run, &mut output);
    output
}

fn helper_matches(values: &[Value; 32], mapping: Mapping) -> bool {
    match mapping {
        Mapping::Indexed(row) => {
            let args = [
                field(values[4], 4),
                field(values[5], 8),
                field(values[6], 12),
            ];
            args.iter()
                .all(|value| *value == Some((row.base, row.origin, row.stride)))
        }
        Mapping::Fixed(destination) => matches!(
            (values[4], values[5], values[6]),
            (Value::Constant(_), Value::Constant(_), Value::Constant(copy_dest))
                if copy_dest == destination
        ),
    }
}

fn fixed_copy_range(values: &[Value; 32]) -> Option<(u32, u32)> {
    match (values[4], values[5]) {
        (Value::Constant(source), Value::Constant(end)) => Some((source, end)),
        _ => None,
    }
}

fn os_map_targets(map: &ProgramMap) -> BTreeSet<GuestAddr> {
    map.runtime_functions
        .iter()
        .filter(|(_, function)| function.name == "osMapTLB")
        .map(|(address, _)| address.pc)
        .collect()
}

struct ScanIndex<'a> {
    cfg: crate::indirect::MapIndex<'a>,
    blocks: std::collections::BTreeMap<u32, &'a BasicBlock>,
    outgoing: std::collections::BTreeMap<u32, Vec<&'a crate::program::DirectEdge>>,
    helpers: BTreeSet<u32>,
}

fn has_call_edge(map: &ScanIndex, image: &CodeImage, site: GuestAddr, target: GuestAddr) -> bool {
    map.cfg
        .edges_to(&image.address(target))
        .iter()
        .any(|edge| edge.site == image.address(site) && edge.kind == crate::program::EdgeKind::Call)
}

fn scan_window(
    rom: &[u8],
    map: &ScanIndex,
    image: &CodeImage,
    block: &BasicBlock,
    seed_arguments: bool,
    os_map: &BTreeSet<GuestAddr>,
) -> Vec<Candidate> {
    if block.start.image != image.base.image
        || block.start.generation != image.base.generation
        || block.delay_slot_entry
    {
        return Vec::new();
    }
    let mut values = [Value::Unknown; 32];
    values[0] = Value::Constant(0);
    if seed_arguments {
        for (index, value) in values.iter_mut().enumerate().take(8).skip(4) {
            *value = Value::Index {
                origin: index as u8,
                scale: 1,
            };
        }
    }
    let mut output = Vec::new();
    let mut pending = vec![(block.start.pc.0, values, None, BTreeSet::new())];
    let mut steps = 0;
    while let Some((mut pc, mut values, mut mapping, mut path)) = pending.pop() {
        for _ in 0..MAX_WINDOW_WORDS {
            steps += 1;
            if steps > 4096 || !path.insert(pc) {
                break;
            }
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
                let Some(delay_word) = delay(image, site) else {
                    break;
                };
                let target = jal_target(word, site);
                let mut at_call = values;
                step(delay_word, GuestAddr(pc + 4), image, &mut at_call);
                let Some(continuation) = pc.checked_add(8).map(GuestAddr) else {
                    break;
                };
                let continuation_ok = map.outgoing.get(&pc).is_some_and(|edges| {
                    edges.iter().any(|edge| {
                        edge.target == image.address(continuation)
                            && edge.kind == crate::program::EdgeKind::ReturnContinuation
                    })
                });
                if os_map.contains(&target) && has_call_edge(map, image, site, target) {
                    mapping = if continuation_ok {
                        map_call(at_call[6]).map(|mapping| MapCall { mapping, gap: 0 })
                    } else {
                        None
                    };
                } else if map.helpers.contains(&target.0) && has_call_edge(map, image, site, target)
                {
                    let current = mapping.filter(|call| call.gap <= MAX_CALL_GAP);
                    if let Some(call) = current
                        && helper_matches(&at_call, call.mapping)
                    {
                        let mut candidates = match call.mapping {
                            Mapping::Indexed(row) => {
                                indexed_candidates(rom, image, site, row, site, target)
                            }
                            Mapping::Fixed(virtual_base) => fixed_copy_range(&at_call)
                                .and_then(|(source, end)| {
                                    descriptor(rom, source, end, virtual_base, virtual_base)
                                })
                                .map(|(mut candidate, _)| {
                                    candidate.caller = Some(site);
                                    candidate.helper = Some(target);
                                    vec![candidate]
                                })
                                .unwrap_or_default(),
                        };
                        output.append(&mut candidates);
                    }
                    mapping = None;
                } else {
                    mapping = None;
                }
                if !continuation_ok {
                    break;
                }
                after_call(delay_word, GuestAddr(pc + 4), image, &mut values);
                pc = continuation.0;
                if let Some(call) = &mut mapping {
                    call.gap = 0;
                }
                continue;
            }
            if instruction.has_delay_slot() {
                if let Some(edges) = map.outgoing.get(&pc) {
                    for edge in edges.iter().filter(|edge| {
                        matches!(
                            edge.kind,
                            crate::program::EdgeKind::Branch
                                | crate::program::EdgeKind::Jump
                                | crate::program::EdgeKind::Fallthrough
                        )
                    }) {
                        let mut next_values = values;
                        if edge.delay_slot != crate::program::DelaySlot::None {
                            let Some(slot) = delay(image, site) else {
                                continue;
                            };
                            step(slot, GuestAddr(pc + 4), image, &mut next_values);
                        }
                        if edge.target.image == image.base.image
                            && edge.target.generation == image.base.generation
                        {
                            pending.push((edge.target.pc.0, next_values, mapping, path.clone()));
                        }
                    }
                }
                break;
            }
            step(word, site, image, &mut values);
            let next = match pc.checked_add(4) {
                Some(next) => GuestAddr(next),
                None => break,
            };
            pc = next.0;
            if let Some(call) = &mut mapping {
                call.gap = call.gap.saturating_add(1);
            }
        }
        if steps > 4096 {
            break;
        }
    }
    output
}

/// Infer bounded source files named by indexed TLB/copy consumers or by a
/// fixed TLB/copy pair on a bounded CFG path. Each branch preserves its own
/// symbolic state and only executes its selected delay slot. Cycles stop that
/// path; no candidate claims that every execution takes the witnessed path.
/// The row, path and instruction limits are resource budgets only.
pub fn infer(rom: &[u8], map: &ProgramMap, image: &CodeImage) -> Vec<Candidate> {
    let os_map = os_map_targets(map);
    if os_map.is_empty() {
        return Vec::new();
    }
    let mut starts = map
        .blocks
        .iter()
        .filter(|block| {
            block.start.image == image.base.image && block.start.generation == image.base.generation
        })
        .map(|block| (block.start.pc.0, false))
        .collect::<std::collections::BTreeMap<_, _>>();
    for address in map
        .entries
        .keys()
        .chain(
            map.direct_edges
                .iter()
                .filter(|edge| edge.kind == crate::program::EdgeKind::Call)
                .map(|edge| &edge.target),
        )
        .chain(map.address_taken.keys())
    {
        if address.image == image.base.image
            && address.generation == image.base.generation
            && starts.contains_key(&address.pc.0)
        {
            starts.insert(address.pc.0, true);
        }
    }
    let index = ScanIndex {
        cfg: crate::indirect::MapIndex::new(map),
        blocks: map
            .blocks
            .iter()
            .filter(|b| {
                b.start.image == image.base.image && b.start.generation == image.base.generation
            })
            .map(|b| (b.start.pc.0, b))
            .collect(),
        outgoing: {
            let mut edges = std::collections::BTreeMap::<u32, Vec<_>>::new();
            for edge in &map.direct_edges {
                if edge.site.image == image.base.image
                    && edge.site.generation == image.base.generation
                {
                    edges.entry(edge.site.pc.0).or_default().push(edge);
                }
            }
            edges
        },
        helpers: map
            .direct_edges
            .iter()
            .filter(|edge| edge.kind == crate::program::EdgeKind::Call)
            .map(|edge| edge.target.pc)
            .collect::<BTreeSet<_>>()
            .into_iter()
            .filter(|target| copy_calls::helper_shape(image, *target))
            .map(|target| target.0)
            .collect(),
    };
    // A source witness must reach a mapping call in this native function.
    // Index predecessors once rather than rescan unrelated blocks/windows.
    let mut useful = BTreeSet::new();
    let mut pending: Vec<_> = map
        .direct_edges
        .iter()
        .filter(|edge| {
            edge.kind == crate::program::EdgeKind::Call && os_map.contains(&edge.target.pc)
        })
        .flat_map(|edge| index.cfg.containing(&edge.site))
        .map(|block| block.start.clone())
        .collect();
    while let Some(start) = pending.pop() {
        if !useful.insert(start.pc.0) {
            continue;
        }
        for edge in index
            .cfg
            .edges_to(&start)
            .into_iter()
            .filter(|edge| edge.kind != crate::program::EdgeKind::Call)
        {
            pending.extend(
                index
                    .cfg
                    .containing(&edge.site)
                    .into_iter()
                    .map(|block| block.start.clone()),
            );
        }
    }
    starts.retain(|start, _| useful.contains(start));
    starts
        .iter()
        .filter_map(|(start, seed)| index.blocks.get(start).map(|block| (*block, *seed)))
        .flat_map(|(block, seed)| scan_window(rom, &index, image, block, seed, &os_map))
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::discovery::direct_cfg_bounded;
    use crate::program::{CodeAddress, RomIdentity, RuntimeFunction};

    const BASE: u32 = 0x8000_0000;
    const HELPER: u32 = BASE + 0x100;
    const TABLE_DELTA: u32 = 0x300;
    const MAP: u32 = BASE + 0x700;
    const ROM: usize = 0x1000;

    fn i(op: u32, rs: u32, rt: u32, imm: i16) -> u32 {
        op << 26 | rs << 21 | rt << 16 | imm as u16 as u32
    }

    fn r(rs: u32, rt: u32, rd: u32, sa: u32, funct: u32) -> u32 {
        rs << 21 | rt << 16 | rd << 11 | sa << 6 | funct
    }

    fn lui(rt: u32, value: u16) -> u32 {
        i(15, 0, rt, value as i16)
    }

    fn jal(target: u32, _pc: u32) -> u32 {
        3 << 26 | ((target >> 2) & 0x03ff_ffff)
    }

    fn helper(words: &mut [u32], base: u32) {
        let h = ((base + 0x100 - base) / 4) as usize;
        words[h] = r(4, 0, 16, 0, 33);
        words[h + 1] = r(6, 0, 17, 0, 33);
        words[h + 2] = r(5, 4, 18, 0, 35);
        words[h + 3] = r(16, 0, 4, 0, 33);
        words[h + 4] = r(17, 0, 5, 0, 33);
        words[h + 5] = i(9, 0, 6, 32);
        words[h + 6] = jal(base + 0x500, base + 0x100 + 24);
        words[h + 7] = 0;
        words[h + 8] = i(9, 16, 4, 32);
        words[h + 9] = i(9, 17, 5, 32);
        words[h + 10] = i(9, 18, 6, -32);
        words[h + 11] = jal(base + 0x500, base + 0x100 + 44);
        words[h + 12] = 0;
        words[h + 13] = r(31, 0, 0, 0, 8);
        words[h + 14] = 0;
    }

    struct Fixture {
        rom: Vec<u8>,
        map: ProgramMap,
        image: CodeImage,
        helper_site: u32,
        table: u32,
    }

    fn fixture(base: u32, alternate_scale: bool) -> Fixture {
        let table = base + TABLE_DELTA;
        let map_target = base + 0x600;
        let map_continuation = base + if alternate_scale { 44 } else { 40 };
        let mut words = vec![0; 256];
        if alternate_scale {
            // (index * 4 + index * 2) * 4 = index * 24.
            words[0] = lui(9, ((table.wrapping_add(0x8000)) >> 16) as u16);
            words[1] = i(9, 9, 9, table as u16 as i16);
            words[2] = r(4, 0, 18, 0, 33); // preserve input index
            words[3] = r(0, 18, 8, 2, 0); // index * 4
            words[4] = r(0, 18, 10, 1, 0); // index * 2
            words[5] = r(8, 10, 8, 0, 33); // index * 6
            words[6] = r(0, 8, 8, 2, 0); // index * 24
            words[7] = r(9, 8, 17, 0, 33); // table row
            words[8] = i(35, 17, 6, 12);
            words[9] = jal(map_target, base + 36);
            words[10] = 0;
            words[11] = i(35, 17, 4, 4);
            words[12] = i(35, 17, 5, 8);
            words[13] = i(35, 17, 6, 12);
            words[14] = jal(HELPER + (base - BASE), base + 56);
            words[15] = 0;
            words[16] = r(31, 0, 0, 0, 8);
            words[17] = 0;
        } else {
            words[0] = lui(9, ((table.wrapping_add(0x8000)) >> 16) as u16);
            words[1] = i(9, 9, 9, table as u16 as i16);
            words[2] = r(4, 0, 18, 0, 33); // save dynamic index
            words[3] = r(0, 18, 8, 1, 0); // index * 2
            words[4] = r(8, 18, 8, 0, 33); // index * 3
            words[5] = r(0, 8, 8, 3, 0); // index * 24
            words[6] = r(9, 8, 17, 0, 33); // table row
            words[7] = i(35, 17, 6, 12);
            words[8] = jal(map_target, base + 32);
            words[9] = 0;
            words[10] = i(35, 17, 4, 4);
            words[11] = i(35, 17, 5, 8);
            words[12] = i(35, 17, 6, 12);
            words[13] = jal(HELPER + (base - BASE), base + 52);
            words[14] = 0;
            words[15] = r(31, 0, 0, 0, 8);
            words[16] = 0;
        }
        helper(&mut words, base);

        let virtuals = [0xe000_1000, 0xe000_2000, 0xe000_3000];
        let ranges = [(0x100, 0x140), (0x140, 0x180), (0x180, 0x1c0)];
        let table_word = ((table - base) / 4) as usize;
        for (index, (&virtual_base, &(source, end))) in virtuals.iter().zip(&ranges).enumerate() {
            let at = table_word + (index + 1) * 6;
            words[at] = virtual_base + 0x20;
            words[at + 1] = source;
            words[at + 2] = end;
            words[at + 3] = virtual_base;
            words[at + 4] = u32::MAX; // opaque second-range metadata
            words[at + 5] = 0xdead_beef;
        }

        let id = format!("synthetic-tlb-image-{base:08x}");
        let image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(base),
                image: id.clone(),
                generation: 1,
            },
            words,
            rom_offset: Some(RomOffset(0)),
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        };
        let identity = RomIdentity {
            sha256: "0".repeat(64),
            size: ROM as u64,
        };
        let mut map = direct_cfg_bounded(
            identity,
            &image,
            &[GuestAddr(base)],
            256,
            &BTreeSet::from([GuestAddr(map_target), GuestAddr(base + 0x500)]),
        )
        .expect("direct CFG with resolved runtime calls")
        .map;
        assert!(map.blocks.iter().any(|block| {
            block.start.pc == GuestAddr(base) && block.size == map_continuation - base
        }));
        assert!(
            map.blocks
                .iter()
                .any(|block| { block.start.pc == GuestAddr(map_continuation) })
        );
        map.runtime_functions.insert(
            CodeAddress {
                pc: GuestAddr(map_target),
                image: "runtime".into(),
                generation: 1,
            },
            RuntimeFunction {
                name: "osMapTLB".into(),
                evidence: BTreeSet::new(),
                callbacks: Vec::new(),
                source_size: None,
                status_global: None,
                eeprom_timer: None,
            },
        );
        Fixture {
            rom: vec![0; ROM],
            map,
            image,
            helper_site: base + if alternate_scale { 56 } else { 52 },
            table,
        }
    }

    fn write_row(f: &mut Fixture, row: usize, fields: [u32; 6]) {
        let base = ((f.table - f.image.base.pc.0) / 4) as usize + row * 6;
        f.image.words[base..base + 6].copy_from_slice(&fields);
    }

    #[test]
    fn indexed_six_word_rows_require_mapping_copy_and_adjacent_code_files() {
        for (base, alternate_scale) in [(BASE, false), (0x8010_0000, true)] {
            let f = fixture(base, alternate_scale);
            let candidates = infer(&f.rom, &f.map, &f.image);
            assert_eq!(candidates.len(), 3);
            assert_eq!(candidates[0].source, RomOffset(0x100));
            assert_eq!(candidates[0].end, RomOffset(0x140));
            assert_eq!(candidates[0].virtual_base, GuestAddr(0xe000_1000));
            assert_eq!(candidates[0].entry, GuestAddr(0xe000_1020));
            assert_eq!(candidates[0].text_size, 0x40);
            assert_eq!(candidates[0].caller, Some(GuestAddr(f.helper_site)));
            assert_eq!(
                candidates[0].helper,
                Some(GuestAddr(HELPER + (base - BASE)))
            );
            assert_eq!(
                candidates[0].table,
                Some(TableWitness {
                    base: GuestAddr(f.table),
                    stride: 24,
                })
            );
        }
    }

    fn fixed_fixture() -> (Vec<u8>, ProgramMap, CodeImage, u32) {
        let mut words = vec![0; 256];
        let destination = 0xe020_0000;
        words[0] = lui(6, (destination >> 16) as u16);
        words[1] = i(13, 6, 6, destination as u16 as i16);
        words[2] = jal(MAP, BASE + 8);
        words[3] = 0;
        words[4] = lui(4, 0);
        words[5] = i(13, 4, 4, 0x100);
        words[6] = lui(5, 0);
        words[7] = i(13, 5, 5, 0x140);
        words[8] = lui(6, (destination >> 16) as u16);
        words[9] = i(13, 6, 6, destination as u16 as i16);
        words[10] = jal(HELPER, BASE + 40);
        words[11] = 0;
        helper(&mut words, BASE);
        let image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(BASE),
                image: "fixed-tlb-image".into(),
                generation: 1,
            },
            words,
            rom_offset: Some(RomOffset(0)),
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        };
        let identity = RomIdentity {
            sha256: "0".repeat(64),
            size: ROM as u64,
        };
        let mut map = direct_cfg_bounded(
            identity,
            &image,
            &[GuestAddr(BASE)],
            256,
            &BTreeSet::from([GuestAddr(MAP), GuestAddr(BASE + 0x500)]),
        )
        .expect("direct CFG with resolved runtime calls")
        .map;
        map.runtime_functions.insert(
            CodeAddress {
                pc: GuestAddr(MAP),
                image: "runtime".into(),
                generation: 1,
            },
            RuntimeFunction {
                name: "osMapTLB".into(),
                evidence: BTreeSet::new(),
                callbacks: Vec::new(),
                source_size: None,
                status_global: None,
                eeprom_timer: None,
            },
        );
        (vec![0; ROM], map, image, destination)
    }

    #[test]
    fn fixed_tlb_mapping_requires_a_bounded_same_caller_raw_copy_pair() {
        let (rom, map, image, destination) = fixed_fixture();
        let candidates = infer(&rom, &map, &image);
        assert_eq!(candidates.len(), 1);
        assert_eq!(candidates[0].source, RomOffset(0x100));
        assert_eq!(candidates[0].end, RomOffset(0x140));
        assert_eq!(candidates[0].virtual_base, GuestAddr(destination));
        assert_eq!(candidates[0].entry, GuestAddr(destination));
        assert_eq!(candidates[0].table, None);

        let mut map = map;
        map.runtime_functions.clear();
        assert!(infer(&rom, &map, &image).is_empty());
    }

    #[test]
    fn rejects_clobbered_or_mismatched_mapping_copy_arguments() {
        let mut f = fixture(BASE, false);
        f.image.words[7] = i(35, 17, 6, 8); // map gets ROM end, not virtual page
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        let mut f = fixture(BASE, false);
        f.image.words[10] = i(35, 17, 4, 8); // helper source field mismatch
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        let mut f = fixture(BASE, false);
        f.image.words[7] = i(9, 0, 6, 0x1000); // clobber a2 before osMapTLB
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
    }

    #[test]
    fn rejects_index_expressions_that_do_not_select_six_word_rows() {
        let mut f = fixture(BASE, false);
        f.image.words[5] = r(0, 8, 8, 2, 0); // 12-byte rows, not the fixed 24-byte schema
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
    }

    #[test]
    fn rejects_literal_only_calls_wrong_runtime_name_and_unrelated_callers() {
        let mut f = fixture(BASE, false);
        f.map.runtime_functions.clear();
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        let mut f = fixture(BASE, false);
        let runtime = f.map.runtime_functions.values_mut().next().unwrap();
        runtime.name = "someOtherFunction".into();
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        let mut f = fixture(BASE, false);
        f.map
            .entries
            .insert(f.image.address(GuestAddr(BASE + 40)), BTreeSet::new());
        // Another entry does not erase the witnessed path from the original
        // caller. Candidates do not claim all executions follow that path.
        assert_eq!(infer(&f.rom, &f.map, &f.image).len(), 3);
        f.map.direct_edges.retain(|edge| {
            !(edge.site.pc == GuestAddr(BASE + 32)
                && edge.kind == crate::program::EdgeKind::ReturnContinuation)
        });
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());

        let (rom, mut map, mut image, _) = fixed_fixture();
        image.words[2] = jal(BASE + 0x710, BASE + 8); // not the named osMapTLB
        assert!(infer(&rom, &map, &image).is_empty());
        // The fixed triple without its TLB call has no loader relationship.
        map.runtime_functions.clear();
        assert!(infer(&rom, &map, &image).is_empty());
    }

    #[test]
    fn cfg_paths_preserve_row_provenance_and_execute_their_delay_slots() {
        let mut f = fixture(BASE, false);
        f.image.words[7..24].copy_from_slice(&[
            i(4, 3, 0, 4),
            0,
            0,
            2 << 26 | ((BASE + 56) >> 2 & 0x03ff_ffff),
            0,
            0,
            0,
            i(35, 17, 6, 12),
            jal(BASE + 0x600, BASE + 60),
            0,
            i(35, 17, 4, 4),
            i(35, 17, 5, 8),
            i(35, 17, 6, 12),
            jal(HELPER, BASE + 80),
            0,
            r(31, 0, 0, 0, 8),
            0,
        ]);
        let runtime = f.map.runtime_functions.clone();
        let rebuild = |image: &CodeImage| {
            let mut map = direct_cfg_bounded(
                f.map.rom.clone(),
                image,
                &[GuestAddr(BASE)],
                256,
                &BTreeSet::from([GuestAddr(BASE + 0x600), GuestAddr(BASE + 0x500)]),
            )
            .unwrap()
            .map;
            map.runtime_functions = runtime.clone();
            map
        };
        let map = rebuild(&f.image);
        assert_eq!(infer(&f.rom, &map, &f.image).len(), 3);
        // Both paths execute this non-likely slot, erasing their row base.
        f.image.words[8] = i(9, 0, 17, 0);
        let map = rebuild(&f.image);
        assert!(infer(&f.rom, &map, &f.image).is_empty());
    }

    #[test]
    fn o32_pointer_moves_also_use_daddu() {
        let mut f = fixture(BASE, false);
        f.image.words[2] = r(4, 0, 18, 0, 45);
        assert_eq!(infer(&f.rom, &f.map, &f.image).len(), 3);
        let (rom, map, mut image, _) = fixed_fixture();
        for word in &mut image.words {
            if *word >> 26 == 0 && *word & 63 == 33 {
                *word = (*word & !63) | 45;
            }
        }
        assert_eq!(infer(&rom, &map, &image).len(), 1);
    }

    #[test]
    fn empty_ids_between_valid_records_are_not_a_catalog_terminator() {
        let mut f = fixture(BASE, false);
        write_row(&mut f, 2, [0; 6]);
        let candidates = infer(&f.rom, &f.map, &f.image);
        assert_eq!(candidates.len(), 2);
        assert_eq!(
            candidates.iter().map(|c| c.source.0).collect::<Vec<_>>(),
            [0x100, 0x180]
        );
    }

    #[test]
    fn trailing_register_tail_thunks_are_executable_before_pointer_data() {
        let mut rom = vec![0; 0x140];
        let words = [
            0x03e0_0008u32,
            0,
            0x3c01_c040,
            0x8c21_0020,
            0x0020_0008,
            0,
            0xffff_ffff,
            0,
        ];
        for (n, word) in words.into_iter().enumerate() {
            rom[0x100 + n * 4..0x104 + n * 4].copy_from_slice(&word.to_be_bytes());
        }
        let candidate = descriptor(&rom, 0x100, 0x140, 0xc040_0000, 0xc040_0008)
            .unwrap()
            .0;
        assert_eq!(candidate.text_size, 24);
        assert!(descriptor(&rom, 0x100, 0x140, 0xc040_0000, 0xc040_0018).is_none());
    }

    #[test]
    fn rejects_invalid_ranges_empty_rows_and_entries_outside_text() {
        let mut f = fixture(BASE, false);
        write_row(&mut f, 2, [0xe000_1020, 0x100, 0x100, 0xe000_1000, 0, 0]);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty()); // empty code range

        let mut f = fixture(BASE, false);
        write_row(&mut f, 2, [0xe000_2000, 0x100, 0x140, 0xe000_1000, 0, 0]);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty()); // entry at text end

        let mut f = fixture(BASE, false);
        write_row(&mut f, 2, [0xe000_1020, 0xff0, 0x1030, 0xe000_1000, 0, 0]);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty()); // ROM overrun

        let mut f = fixture(BASE, false);
        write_row(&mut f, 2, [0xe000_1020, 0x100, 0x140, 0x8000_1000, 0, 0]);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty()); // direct-mapped page

        let mut f = fixture(BASE, false);
        write_row(&mut f, 1, [0, 0, 0, 0, 0, 0]);
        let candidates = infer(&f.rom, &f.map, &f.image);
        assert_eq!(candidates.len(), 2);
        assert!(candidates.iter().all(|candidate| candidate.source.0 != 0));
    }
}
