//! Bounded compiler-time replay of captured RSP scalar DMEM load/store lineage.
//! Local generations do not certify complete reads/writers, ultimate ancestry,
//! executable lifetime, or hardware-wide behavior.
use crate::rom::sha256;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub const FORMAT: &str = "plaid-rsp-scalar-history-v0";

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    phases: Vec<Phase>,
    events: Vec<Event>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Phase {
    phase: u32,
    initial_dmem: Vec<u8>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "event", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    Instruction {
        begin: bool,
        ordinal: u64,
        context: u64,
        phase: u32,
        pc: u32,
        word: u32,
        rs: u8,
        rt: u8,
        rd: u8,
        rs_value: u32,
        rt_value: u32,
        rd_value: u32,
        halted: bool,
    },
    DmemWrite {
        ordinal: u64,
        context: u64,
        phase: u32,
        pc: u32,
        offset: u32,
        bytes: u32,
        value: u32,
    },
}

impl Event {
    fn ordinal(&self) -> u64 {
        match self {
            Self::Instruction { ordinal, .. } | Self::DmemWrite { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RspStoreKind {
    Sb,
    Sh,
    Sw,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmemByteSource {
    pub phase: u32,
    pub offset: u16,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspScalarStoreByte {
    pub sink_ordinal: u64,
    pub destination_offset: u16,
    pub value: u8,
    pub source: Option<DmemByteSource>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspScalarStoreWitness {
    pub phase: u32,
    pub context: u64,
    pub instruction_ordinal: u64,
    pub pc: u32,
    pub kind: RspStoreKind,
    pub source_register: u8,
    pub value: u32,
    pub producer_load_context: Option<u64>,
    pub producer_load_generation: Option<u64>,
    pub bytes: Vec<RspScalarStoreByte>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspScalarLineageReport {
    pub format: String,
    pub source_sha256: String,
    pub phases: usize,
    pub instruction_contexts: usize,
    pub dmem_write_effects: usize,
    pub load_generations: u64,
    pub stores: Vec<RspScalarStoreWitness>,
    pub primitive_read_coverage_certified: bool,
    pub gpr_writer_coverage_certified: bool,
    pub source_storage_ancestry_certified: bool,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Clone, Copy)]
struct Instruction {
    ordinal: u64,
    context: u64,
    phase: u32,
    pc: u32,
    word: u32,
    rs: u8,
    rt: u8,
    rd: u8,
    rs_value: u32,
    rt_value: u32,
    rd_value: u32,
    halted: bool,
}

#[derive(Debug, Clone, Copy)]
struct Sink {
    ordinal: u64,
    offset: u32,
    bytes: u32,
    value: u32,
}

struct Active {
    begin: Instruction,
    sinks: Vec<Sink>,
}

#[derive(Clone)]
struct Lineage {
    generation: u64,
    load_context: u64,
    width: usize,
    sources: Vec<Option<DmemByteSource>>,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn decode(word: u32) -> (u32, u8, u8, u8, i16, u32) {
    (
        word >> 26,
        ((word >> 21) & 31) as u8,
        ((word >> 16) & 31) as u8,
        ((word >> 11) & 31) as u8,
        word as i16,
        word & 63,
    )
}

fn instruction(event: &Event) -> Option<Instruction> {
    match event {
        Event::Instruction {
            ordinal,
            context,
            phase,
            pc,
            word,
            rs,
            rt,
            rd,
            rs_value,
            rt_value,
            rd_value,
            halted,
            ..
        } => Some(Instruction {
            ordinal: *ordinal,
            context: *context,
            phase: *phase,
            pc: *pc,
            word: *word,
            rs: *rs,
            rt: *rt,
            rd: *rd,
            rs_value: *rs_value,
            rt_value: *rt_value,
            rd_value: *rd_value,
            halted: *halted,
        }),
        Event::DmemWrite { .. } => None,
    }
}

fn validate_instruction(row: Instruction) -> Result<(), String> {
    let (_, rs, rt, rd, _, _) = decode(row.word);
    let operands = [
        (row.rs, row.rs_value),
        (row.rt, row.rt_value),
        (row.rd, row.rd_value),
    ];
    let aliases_match = operands.iter().enumerate().all(|(index, &(reg, value))| {
        (reg != 0 || value == 0)
            && operands[index + 1..]
                .iter()
                .all(|&(other_reg, other_value)| reg != other_reg || value == other_value)
    });
    require(
        row.phase != 0
            && row.pc <= 0x0ffc
            && row.pc.is_multiple_of(4)
            && (row.rs, row.rt, row.rd) == (rs, rt, rd)
            && aliases_match,
        "invalid RSP scalar instruction state",
    )
}

fn load_spec(op: u32) -> Option<(usize, bool)> {
    match op {
        0x20 => Some((1, true)),
        0x24 => Some((1, false)),
        0x21 => Some((2, true)),
        0x25 => Some((2, false)),
        0x23 | 0x27 => Some((4, false)),
        _ => None,
    }
}

fn store_spec(op: u32) -> Option<(usize, RspStoreKind)> {
    match op {
        0x28 => Some((1, RspStoreKind::Sb)),
        0x29 => Some((2, RspStoreKind::Sh)),
        0x2b => Some((4, RspStoreKind::Sw)),
        _ => None,
    }
}

fn offsets(base: u32, immediate: i16, width: usize) -> Vec<u16> {
    let address = base.wrapping_add_signed(i32::from(immediate));
    (0..width)
        .map(|lane| (address.wrapping_add(lane as u32) & 0x0fff) as u16)
        .collect()
}

fn read(memory: &[u8], lanes: &[u16], signed: bool) -> u32 {
    let raw = lanes.iter().fold(0u32, |value, lane| {
        (value << 8) | u32::from(memory[usize::from(*lane)])
    });
    match (lanes.len(), signed) {
        (1, true) => (raw as u8 as i8 as i32) as u32,
        (2, true) => (raw as u16 as i16 as i32) as u32,
        _ => raw,
    }
}

fn same_instruction(begin: Instruction, end: Instruction) -> bool {
    (
        end.context,
        end.phase,
        end.pc,
        end.word,
        end.rs,
        end.rt,
        end.rd,
    ) == (
        begin.context,
        begin.phase,
        begin.pc,
        begin.word,
        begin.rs,
        begin.rt,
        begin.rd,
    )
}

/// Replays a trusted complete capture of the bounded scalar protocol.
/// The expected digest must come from an external complete-source receipt.
pub fn inspect_rsp_scalar_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<RspScalarLineageReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "RSP scalar source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported RSP scalar history format",
    )?;

    let mut phases = BTreeMap::<u32, &[u8]>::new();
    for phase in &history.phases {
        require(
            phase.phase != 0
                && phase.initial_dmem.len() == 4096
                && phases.insert(phase.phase, &phase.initial_dmem).is_none(),
            "invalid/duplicate RSP scalar phase",
        )?;
    }
    require(!phases.is_empty(), "RSP scalar history has no phases")?;

    let mut active = None::<Active>;
    let mut current_phase = None::<u32>;
    let mut seen_phases = BTreeSet::<u32>::new();
    let mut memory = Vec::<u8>::new();
    let mut origins = Vec::<Option<DmemByteSource>>::new();
    let mut registers: [Option<Lineage>; 32] = std::array::from_fn(|_| None);
    let mut stores = Vec::<RspScalarStoreWitness>::new();
    let mut instruction_contexts = 0usize;
    let mut dmem_write_effects = 0usize;
    let mut load_generation = 0u64;

    for (index, event) in history.events.iter().enumerate() {
        require(
            event.ordinal() == index as u64 + 1,
            "noncontiguous/reordered RSP scalar source ordinals",
        )?;
        match event {
            Event::Instruction { begin: true, .. } => {
                let row = instruction(event).expect("instruction event");
                validate_instruction(row)?;
                require(
                    active.is_none() && row.context == row.ordinal,
                    "invalid RSP scalar begin context",
                )?;
                if current_phase != Some(row.phase) {
                    if let Some(previous) = current_phase {
                        require(row.phase > previous, "RSP scalar phase reused/reordered")?;
                    }
                    let initial = phases
                        .get(&row.phase)
                        .ok_or("RSP scalar instruction references undeclared phase")?;
                    memory = initial.to_vec();
                    origins = (0..4096)
                        .map(|offset| {
                            Some(DmemByteSource {
                                phase: row.phase,
                                offset: offset as u16,
                            })
                        })
                        .collect();
                    registers = std::array::from_fn(|_| None);
                    current_phase = Some(row.phase);
                    seen_phases.insert(row.phase);
                }
                active = Some(Active {
                    begin: row,
                    sinks: Vec::new(),
                });
            }
            Event::DmemWrite {
                ordinal,
                context,
                phase,
                pc,
                offset,
                bytes,
                value,
            } => {
                let scope = active.as_mut().ok_or("unscoped RSP scalar DMEM write")?;
                require(
                    (*context, *phase, *pc)
                        == (scope.begin.context, scope.begin.phase, scope.begin.pc)
                        && *offset < 4096
                        && *bytes == 1
                        && *value <= u32::from(u8::MAX),
                    "invalid RSP scalar DMEM write",
                )?;
                scope.sinks.push(Sink {
                    ordinal: *ordinal,
                    offset: *offset,
                    bytes: *bytes,
                    value: *value,
                });
                dmem_write_effects += 1;
            }
            Event::Instruction { begin: false, .. } => {
                let end = instruction(event).expect("instruction event");
                validate_instruction(end)?;
                let scope = active.take().ok_or("RSP scalar end without begin")?;
                require(
                    same_instruction(scope.begin, end),
                    "RSP scalar end context mismatch",
                )?;
                instruction_contexts += 1;
                let begin = scope.begin;
                let (op, _, rt, rd, immediate, funct) = decode(begin.word);

                if let Some((width, signed)) = load_spec(op) {
                    require(scope.sinks.is_empty(), "RSP scalar load wrote DMEM")?;
                    require(rt != 0, "RSP scalar load to r0 is outside captured scope")?;
                    let lanes = offsets(begin.rs_value, immediate, width);
                    let value = read(&memory, &lanes, signed);
                    require(end.rt_value == value, "RSP scalar load result mismatch")?;
                    load_generation += 1;
                    registers[usize::from(rt)] = Some(Lineage {
                        generation: load_generation,
                        load_context: begin.context,
                        width,
                        sources: lanes
                            .iter()
                            .map(|lane| origins[usize::from(*lane)])
                            .collect(),
                    });
                    continue;
                }

                if let Some((width, kind)) = store_spec(op) {
                    require(
                        scope.sinks.len() == width,
                        "RSP scalar store has incomplete/excess DMEM effects",
                    )?;
                    let lanes = offsets(begin.rs_value, immediate, width);
                    let values = begin.rt_value.to_be_bytes()[4 - width..].to_vec();
                    for (sink, (lane, value)) in scope
                        .sinks
                        .iter()
                        .zip(lanes.iter().copied().zip(values.iter().copied()))
                    {
                        require(
                            sink.bytes == 1
                                && sink.offset == u32::from(lane)
                                && sink.value == u32::from(value),
                            "RSP scalar store effect mismatch",
                        )?;
                    }
                    let lineage = (rt != 0)
                        .then(|| registers[usize::from(rt)].as_ref())
                        .flatten()
                        .filter(|lineage| lineage.width == width);
                    let sources = lineage
                        .map(|lineage| lineage.sources.clone())
                        .unwrap_or_else(|| vec![None; width]);
                    let bytes: Vec<_> = scope
                        .sinks
                        .iter()
                        .zip(lanes.iter().copied())
                        .zip(values.iter().copied())
                        .zip(sources.iter().copied())
                        .map(
                            |(((sink, destination_offset), value), source)| RspScalarStoreByte {
                                sink_ordinal: sink.ordinal,
                                destination_offset,
                                value,
                                source,
                            },
                        )
                        .collect();
                    for byte in &bytes {
                        memory[usize::from(byte.destination_offset)] = byte.value;
                        origins[usize::from(byte.destination_offset)] = byte.source;
                    }
                    stores.push(RspScalarStoreWitness {
                        phase: begin.phase,
                        context: begin.context,
                        instruction_ordinal: begin.ordinal,
                        pc: begin.pc,
                        kind,
                        source_register: rt,
                        value: begin.rt_value,
                        producer_load_context: lineage.map(|lineage| lineage.load_context),
                        producer_load_generation: lineage.map(|lineage| lineage.generation),
                        bytes,
                    });
                    require(
                        (end.rs_value, end.rt_value, end.rd_value)
                            == (begin.rs_value, begin.rt_value, begin.rd_value),
                        "RSP scalar store changed captured GPR state",
                    )?;
                    continue;
                }

                if op == 0x0d {
                    require(scope.sinks.is_empty(), "RSP ORI wrote DMEM")?;
                    let result = begin.rs_value | u32::from(begin.word as u16);
                    require(rt != 0 && end.rt_value == result, "RSP ORI result mismatch")?;
                    registers[usize::from(rt)] = None;
                    continue;
                }

                if op == 0 && funct == 0x21 {
                    require(scope.sinks.is_empty(), "RSP ADDU wrote DMEM")?;
                    let result = begin.rs_value.wrapping_add(begin.rt_value);
                    require(
                        rd != 0 && end.rd_value == result,
                        "RSP ADDU result mismatch",
                    )?;
                    registers[usize::from(rd)] = None;
                    continue;
                }

                if begin.word == 0x0000_000d {
                    require(
                        scope.sinks.is_empty() && end.halted,
                        "RSP BREAK did not halt cleanly",
                    )?;
                    continue;
                }

                return Err(format!(
                    "unsupported RSP scalar instruction {:08x}",
                    begin.word
                ));
            }
        }
    }

    require(active.is_none(), "truncated RSP scalar instruction context")?;
    require(
        seen_phases.len() == phases.len(),
        "declared RSP scalar phase has no captured execution",
    )?;

    Ok(RspScalarLineageReport {
        format: history.format,
        source_sha256: digest,
        phases: phases.len(),
        instruction_contexts,
        dmem_write_effects,
        load_generations: load_generation,
        stores,
        primitive_read_coverage_certified: false,
        gpr_writer_coverage_certified: false,
        source_storage_ancestry_certified: false,
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

pub fn verify_rsp_scalar_report(
    report: &RspScalarLineageReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_rsp_scalar_history(source, expected_sha256)?,
        "RSP scalar report differs from complete source replay",
    )
}

#[cfg(test)]
mod tests;
