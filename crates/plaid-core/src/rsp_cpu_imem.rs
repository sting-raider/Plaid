//! Source-bound composition of decoded RSP writers and CPU IMEM installation.
//! Captured scalar/vector operands are inputs, not ultimate register ancestry.
//! The controlled profile has CPU register/control continuity, explicit RSP
//! reentry phases and no modeled cache, TLB, DMA or restore interleavings.
use crate::{
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-rsp-cpu-imem-history-v0";
pub const PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-scalar-sbv2e0-v0";
pub const DEFINITION_FORMAT: &str = "plaid-rsp-cpu-imem-history-v1";
pub const DEFINITION_PROFILE: &str =
    "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-rsp-cpu-imem-scalar-definitions-sbv2e0-v1";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    profile: String,
    initial_dmem: Vec<u8>,
    initial_imem: Vec<u8>,
    final_dmem: Vec<u8>,
    final_imem: Vec<u8>,
    steps: Vec<CpuStep>,
    events: Vec<Row>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct CpuStep {
    phase: u32,
    index: u32,
    word: u32,
    pc: u64,
    before: Vec<u64>,
    after: Vec<u64>,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Kind {
    CpuBegin,
    CpuEnd,
    RspBegin,
    RspEnd,
    RspSink,
    ForeignSink,
    SpRead,
    SpWrite,
}
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Row {
    kind: Kind,
    ordinal: u64,
    context: u64,
    pc: u64,
    phase: u32,
    word: u32,
    address: u32,
    bank: u32,
    offset: u32,
    bytes: u32,
    value: u64,
    cpu: bool,
    next: u32,
    halted: bool,
    vector_byte: u32,
    gpr: Vec<u64>,
    rgpr: Vec<u32>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum SpByteOrigin {
    Rsp {
        context: u64,
        pc: u16,
        word: u32,
        write_ordinal: u64,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        source_definition: Option<u64>,
    },
    Cpu {
        context: u64,
        pc: GuestVirtualAddr,
        word: u32,
        write_ordinal: u64,
    },
    Unknown {
        cut_ordinal: Option<u64>,
    },
}

/// Parent identity at the actual decoded instruction boundary. Captured inputs
/// remain opaque; equal bits never substitute for an earlier definition.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum RspRegisterParent {
    ArchitecturalZero,
    Definition { context: u64 },
    CapturedInput { register: u8, value: u32 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum RspDefinitionExpression {
    Ori {
        source: RspRegisterParent,
        immediate: u16,
    },
    Addu {
        left: RspRegisterParent,
        right: RspRegisterParent,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspRegisterDefinition {
    pub context: u64,
    pub phase: u32,
    pub pc: u16,
    pub word: u32,
    pub register: u8,
    pub value: u32,
    pub expression: RspDefinitionExpression,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ImemCopyChain {
    pub phase: u32,
    pub load_context: u64,
    pub read_ordinal: u64,
    pub store_context: u64,
    pub write_ordinal: u64,
    pub source_register: u8,
    pub source: PhysicalAddr,
    pub destination: PhysicalAddr,
    pub word: u32,
    pub source_bytes: [SpByteOrigin; 4],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspCpuImemReport {
    pub format: String,
    pub profile: String,
    pub source_sha256: String,
    pub records: usize,
    pub cpu_instructions: usize,
    pub rsp_instructions: usize,
    pub copies: Vec<ImemCopyChain>,
    pub final_imem_writers: Vec<SpByteOrigin>,
    pub final_dmem_sha256: String,
    pub final_imem_sha256: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rsp_definitions: Option<Vec<RspRegisterDefinition>>,
    pub source_ancestry_certified: bool,
    pub mutation_coverage_certified: bool,
    pub imem_execution_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}
#[derive(Clone)]
struct Loaded {
    context: u64,
    read: u64,
    register: usize,
    bits: u64,
    address: PhysicalAddr,
    origins: [SpByteOrigin; 4],
}
fn effect_row(row: &Row) -> Result<(), String> {
    require(
        row.gpr.is_empty()
            && row.rgpr.is_empty()
            && row.next == 0
            && !row.halted
            && row.vector_byte == 0,
        "invalid completed-effect metadata",
    )
}
enum Active {
    Cpu {
        begin: Row,
        read: Option<Loaded>,
        written: bool,
    },
    Rsp {
        begin: Row,
        lanes: Vec<(u16, u8)>,
        consumed: usize,
        breaking: bool,
        expected_gpr: Vec<u32>,
        definition: Option<RspRegisterDefinition>,
    },
}
fn require(ok: bool, why: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(why.into()) }
}
fn sign32(word: u32) -> u64 {
    (word as i32 as i64) as u64
}
fn same(begin: &Row, row: &Row) -> bool {
    (begin.context, begin.pc, begin.phase, begin.word) == (row.context, row.pc, row.phase, row.word)
}
fn boundary(row: &Row, cpu: bool) -> Result<(), String> {
    require(
        row.bytes == 0
            && row.value == 0
            && row.address == 0
            && row.bank == 0
            && row.offset == 0
            && row.cpu == cpu,
        "invalid instruction-boundary metadata",
    )?;
    if cpu {
        require(
            row.gpr.len() == 32
                && row.gpr[0] == 0
                && row.rgpr.is_empty()
                && row.pc.is_multiple_of(4)
                && row.next == 0
                && !row.halted
                && row.vector_byte == 0,
            "invalid CPU architectural snapshot",
        )
    } else {
        require(
            row.rgpr.len() == 32
                && row.rgpr[0] == 0
                && row.gpr.is_empty()
                && row.pc <= 0xffc
                && row.pc.is_multiple_of(4)
                && row.vector_byte <= 255,
            "invalid RSP architectural snapshot",
        )
    }
}
fn payload(value: u64, width: u32) -> Result<Vec<u8>, String> {
    require(
        matches!(width, 1 | 2 | 4 | 8),
        "unsupported completed byte effect width",
    )?;
    require(
        width == 8 || value < (1u64 << (width * 8)),
        "effect value exceeds width",
    )?;
    Ok(value.to_be_bytes()[8 - width as usize..].to_vec())
}
fn store(
    memory: &mut [u8],
    origins: &mut [SpByteOrigin],
    offset: u32,
    data: &[u8],
    origin: SpByteOrigin,
) -> Result<(), String> {
    require(offset < 4096, "SP byte offset outside bank")?;
    for (index, value) in data.iter().copied().enumerate() {
        let address = (offset as usize + index) & 4095;
        require(
            address < memory.len(),
            "effect escapes declared backing snapshot",
        )?;
        memory[address] = value;
        origins[address] = origin.clone();
    }
    Ok(())
}
fn rsp_lanes(row: &Row) -> Result<(Vec<(u16, u8)>, bool), String> {
    let op = row.word >> 26;
    let rs = ((row.word >> 21) & 31) as usize;
    let rt = ((row.word >> 16) & 31) as usize;
    if row.word == 0 || row.word == 13 {
        return Ok((Vec::new(), row.word == 13));
    }
    let (address, data) = match op {
        0x28 | 0x29 | 0x2b => {
            let width = match op {
                0x28 => 1,
                0x29 => 2,
                _ => 4,
            };
            (
                row.rgpr[rs].wrapping_add_signed(i32::from(row.word as i16)),
                payload(u64::from(row.rgpr[rt]) & ((1u64 << (width * 8)) - 1), width)?,
            )
        }
        0x3a => {
            require(
                rt == 2 && (row.word >> 11) & 31 == 0 && (row.word >> 7) & 15 == 0,
                "unsupported vector store source/element",
            )?;
            let immediate = ((row.word & 127) as i32 ^ 64) - 64;
            (
                row.rgpr[rs].wrapping_add_signed(immediate),
                vec![row.vector_byte as u8],
            )
        }
        _ => return Err("unsupported RSP producer instruction".into()),
    };
    Ok((
        data.into_iter()
            .enumerate()
            .map(|(i, value)| (((address.wrapping_add(i as u32)) & 4095) as u16, value))
            .collect(),
        false,
    ))
}

fn is_definition(word: u32) -> bool {
    word >> 26 == 0x0d || (word >> 26 == 0 && word & 63 == 0x21 && (word >> 6) & 31 == 0)
}

fn rsp_definition(row: &Row, registers: &[Option<u64>; 32]) -> Option<RspRegisterDefinition> {
    let rs = ((row.word >> 21) & 31) as usize;
    let rt = ((row.word >> 16) & 31) as usize;
    let parent = |r: usize| {
        if r == 0 {
            RspRegisterParent::ArchitecturalZero
        } else if let Some(context) = registers[r] {
            RspRegisterParent::Definition { context }
        } else {
            RspRegisterParent::CapturedInput {
                register: r as u8,
                value: row.rgpr[r],
            }
        }
    };
    let (register, value, expression) = if row.word >> 26 == 0x0d {
        (
            rt,
            row.rgpr[rs] | u32::from(row.word as u16),
            RspDefinitionExpression::Ori {
                source: parent(rs),
                immediate: row.word as u16,
            },
        )
    } else {
        (
            ((row.word >> 11) & 31) as usize,
            row.rgpr[rs].wrapping_add(row.rgpr[rt]),
            RspDefinitionExpression::Addu {
                left: parent(rs),
                right: parent(rt),
            },
        )
    };
    (register != 0).then_some(RspRegisterDefinition {
        context: row.context,
        phase: row.phase,
        pc: row.pc as u16,
        word: row.word,
        register: register as u8,
        value,
        expression,
    })
}

/// Verify a complete externally committed controlled chronology. No fixture
/// phase numbers, fixed code PCs, payloads or certificate counts are assumed.
pub fn inspect_rsp_cpu_imem_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<RspCpuImemReport, String> {
    require(
        source.len() <= 64 * 1024 * 1024,
        "composed source exceeds supported bound",
    )?;
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "RSP/CPU composition source receipt mismatch",
    )?;
    let h: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    let definitions_enabled = h.format == DEFINITION_FORMAT && h.profile == DEFINITION_PROFILE;
    require(
        (h.format == FORMAT && h.profile == PROFILE) || definitions_enabled,
        "unsupported RSP/CPU composition profile",
    )?;
    require(
        !h.events.is_empty() && h.events.len() <= 1_000_000,
        "invalid composed event count",
    )?;
    require(
        [h.initial_dmem.len(), h.initial_imem.len()]
            .into_iter()
            .all(|len| (4..=4096).contains(&len) && len.is_multiple_of(4)),
        "invalid declared backing snapshots",
    )?;
    let records = h.events.len();
    let mut dmem = h.initial_dmem;
    let mut imem = h.initial_imem;
    let unknown = SpByteOrigin::Unknown { cut_ordinal: None };
    let mut dorig = vec![unknown.clone(); dmem.len()];
    let mut iorig = vec![unknown; imem.len()];
    let mut registers: [Option<Loaded>; 32] = std::array::from_fn(|_| None);
    let mut active: Option<Active> = None;
    let mut previous_cpu: Option<Row> = None;
    let mut previous_rsp: Option<Row> = None;
    let mut rsp_registers = [None; 32];
    let mut rsp_definitions = Vec::new();
    let mut phase = 0;
    let mut copies = Vec::new();
    let mut cpu_instructions = 0;
    let mut rsp_instructions = 0;
    for (index, row) in h.events.into_iter().enumerate() {
        require(
            row.ordinal == index as u64 + 1 && row.phase != 0 && row.phase >= phase,
            "noncontiguous event identity or phase order",
        )?;
        phase = row.phase;
        match row.kind {
            Kind::CpuBegin => {
                require(
                    active.is_none() && row.context == row.ordinal,
                    "invalid CPU begin context",
                )?;
                boundary(&row, true)?;
                if let Some(previous) = &previous_cpu {
                    require(
                        row.gpr == previous.gpr && previous.pc.checked_add(4) == Some(row.pc),
                        "CPU register/control continuity mismatch",
                    )?;
                }
                active = Some(Active::Cpu {
                    begin: row,
                    read: None,
                    written: false,
                });
            }
            Kind::RspBegin => {
                require(
                    active.is_none() && row.context == row.ordinal,
                    "invalid RSP begin context",
                )?;
                boundary(&row, false)?;
                require(
                    !row.halted && u64::from(row.next) == row.pc,
                    "RSP begin is not an active decoded instruction",
                )?;
                if let Some(previous) = &previous_rsp
                    && previous.phase == row.phase
                {
                    require(
                        row.rgpr == previous.rgpr && row.pc == u64::from(previous.next),
                        "RSP same-phase continuity mismatch",
                    )?;
                }
                if previous_rsp
                    .as_ref()
                    .is_none_or(|previous| previous.phase != row.phase)
                {
                    rsp_registers.fill(None);
                }
                let mut expected_gpr = row.rgpr.clone();
                let (lanes, breaking, definition) =
                    if definitions_enabled && is_definition(row.word) {
                        let definition = rsp_definition(&row, &rsp_registers);
                        if let Some(d) = &definition {
                            expected_gpr[d.register as usize] = d.value;
                        }
                        (Vec::new(), false, definition)
                    } else {
                        let (lanes, breaking) = rsp_lanes(&row)?;
                        (lanes, breaking, None)
                    };
                active = Some(Active::Rsp {
                    begin: row,
                    lanes,
                    consumed: 0,
                    breaking,
                    expected_gpr,
                    definition,
                });
            }
            Kind::RspSink => {
                effect_row(&row)?;
                require(
                    row.bytes == 1,
                    "RSP profile requires actual Byte sink callbacks",
                )?;
                let Some(Active::Rsp {
                    begin,
                    lanes,
                    consumed,
                    ..
                }) = &mut active
                else {
                    return Err("RSP sink lacks instruction context".into());
                };
                require(
                    same(begin, &row)
                        && !row.cpu
                        && row.bank == 0
                        && row.address == row.offset
                        && row.gpr.is_empty()
                        && row.rgpr.is_empty(),
                    "RSP sink context/domain mismatch",
                )?;
                let data = payload(row.value, row.bytes)?;
                require(
                    *consumed + data.len() <= lanes.len(),
                    "RSP sink exceeds decoded store",
                )?;
                for (n, value) in data.iter().copied().enumerate() {
                    require(
                        lanes[*consumed + n] == (((row.offset + n as u32) & 4095) as u16, value),
                        "RSP sink differs from decoded operand/lane",
                    )?;
                }
                store(
                    &mut dmem,
                    &mut dorig,
                    row.offset,
                    &data,
                    SpByteOrigin::Rsp {
                        context: row.context,
                        pc: row.pc as u16,
                        word: row.word,
                        write_ordinal: row.ordinal,
                        source_definition: if definitions_enabled
                            && matches!(row.word >> 26, 0x28 | 0x29 | 0x2b)
                        {
                            rsp_registers[((row.word >> 16) & 31) as usize]
                        } else {
                            None
                        },
                    },
                )?;
                *consumed += data.len();
            }
            Kind::ForeignSink => {
                effect_row(&row)?;
                require(
                    !row.cpu
                        && row.bank == 0
                        && row.address == row.offset
                        && row.gpr.is_empty()
                        && row.rgpr.is_empty(),
                    "invalid foreign DMEM sink",
                )?;
                match &active {
                    Some(Active::Cpu { begin, written, .. }) => {
                        require(
                            same(begin, &row) && begin.word >> 26 == 0x2b && !*written,
                            "foreign sink CPU context mismatch",
                        )?;
                        let rs = ((begin.word >> 21) & 31) as usize;
                        let rt = ((begin.word >> 16) & 31) as usize;
                        let address =
                            begin.gpr[rs].wrapping_add_signed(i64::from(begin.word as i16));
                        require(
                            (0xffffffffa4000000..=0xffffffffa403ffff).contains(&address)
                                && address & 3 == 0
                                && address & 0x1000 == 0
                                && row.offset == (address as u32 & 0xffc)
                                && row.bytes == 4
                                && row.value == u64::from(begin.gpr[rt] as u32),
                            "foreign CPU DMEM sink differs from decoded store",
                        )?;
                    }
                    None => require(
                        row.context == 0 && row.word == 0,
                        "foreign sink has stale context",
                    )?,
                    _ => return Err("foreign mutation inside RSP instruction".into()),
                }
                store(
                    &mut dmem,
                    &mut dorig,
                    row.offset,
                    &payload(row.value, row.bytes)?,
                    SpByteOrigin::Unknown {
                        cut_ordinal: Some(row.ordinal),
                    },
                )?;
            }
            Kind::SpRead | Kind::SpWrite => {
                effect_row(&row)?;
                require(
                    row.cpu
                        && row.bytes == 4
                        && row.value <= u64::from(u32::MAX)
                        && (0x04000000..=0x0403ffff).contains(&row.address)
                        && row.address.is_multiple_of(4)
                        && row.bank == (row.address >> 12) & 1
                        && row.offset == row.address & 0xffc
                        && row.gpr.is_empty()
                        && row.rgpr.is_empty(),
                    "invalid normalized CPU SP Word effect",
                )?;
                let mut rt = 0;
                if let Some(Active::Cpu {
                    begin,
                    read,
                    written,
                }) = &mut active
                {
                    require(same(begin, &row), "CPU SP effect context mismatch")?;
                    let op = begin.word >> 26;
                    let rs = ((begin.word >> 21) & 31) as usize;
                    rt = ((begin.word >> 16) & 31) as usize;
                    let virtual_address =
                        begin.gpr[rs].wrapping_add_signed(i64::from(begin.word as i16));
                    require(
                        (0xffffffffa4000000..=0xffffffffa403ffff).contains(&virtual_address)
                            && (virtual_address & 0x1fffffff) == u64::from(row.address),
                        "SP effect does not match decoded direct KSEG1 address",
                    )?;
                    if row.kind == Kind::SpRead {
                        require(
                            op == 0x23 && read.is_none() && !*written,
                            "invalid decoded SP load effect",
                        )?;
                    } else {
                        require(
                            op == 0x2b
                                && read.is_none()
                                && !*written
                                && row.value == u64::from(begin.gpr[rt] as u32),
                            "invalid decoded SP store effect",
                        )?;
                        *written = true;
                    }
                } else {
                    require(
                        active.is_none()
                            && row.kind == Kind::SpWrite
                            && row.context == 0
                            && row.word == 0,
                        "unscoped SP read or stale instruction attribution",
                    )?;
                }
                let (memory, origins) = if row.bank == 0 {
                    (&mut dmem, &mut dorig)
                } else {
                    (&mut imem, &mut iorig)
                };
                let offset = row.offset as usize;
                require(
                    offset + 4 <= memory.len(),
                    "CPU Word escapes declared backing snapshot",
                )?;
                if row.kind == Kind::SpRead {
                    require(
                        memory[offset..offset + 4] == (row.value as u32).to_be_bytes(),
                        "CPU load differs from observed backing",
                    )?;
                    let loaded = Loaded {
                        context: row.context,
                        read: row.ordinal,
                        register: rt,
                        bits: sign32(row.value as u32),
                        address: PhysicalAddr(row.address),
                        origins: std::array::from_fn(|i| origins[offset + i].clone()),
                    };
                    if let Some(Active::Cpu { read, .. }) = &mut active {
                        *read = Some(loaded);
                    }
                } else {
                    let origin = if row.context == 0 {
                        SpByteOrigin::Unknown {
                            cut_ordinal: Some(row.ordinal),
                        }
                    } else {
                        SpByteOrigin::Cpu {
                            context: row.context,
                            pc: GuestVirtualAddr(row.pc),
                            word: row.word,
                            write_ordinal: row.ordinal,
                        }
                    };
                    store(
                        memory,
                        origins,
                        row.offset,
                        &(row.value as u32).to_be_bytes(),
                        origin,
                    )?;
                    if row.bank == 1
                        && row.context != 0
                        && let Some(parent) = &registers[rt]
                    {
                        let Some(Active::Cpu { begin, .. }) = &active else {
                            unreachable!()
                        };
                        require(
                            begin.gpr[rt] == parent.bits,
                            "store source lost captured register definition",
                        )?;
                        copies.push(ImemCopyChain {
                            phase: row.phase,
                            load_context: parent.context,
                            read_ordinal: parent.read,
                            store_context: row.context,
                            write_ordinal: row.ordinal,
                            source_register: rt as u8,
                            source: parent.address,
                            destination: PhysicalAddr(row.address),
                            word: row.value as u32,
                            source_bytes: parent.origins.clone(),
                        });
                    }
                }
            }
            Kind::CpuEnd => {
                boundary(&row, true)?;
                let Some(Active::Cpu {
                    begin,
                    read,
                    written,
                }) = active.take()
                else {
                    return Err("CPU end lacks begin".into());
                };
                require(same(&begin, &row), "CPU end context mismatch")?;
                let mut expected = begin.gpr.clone();
                let op = begin.word >> 26;
                if op == 0x23 {
                    let load = read.ok_or("CPU load lacks completed read")?;
                    require(!written, "load has store effect")?;
                    if load.register != 0 {
                        expected[load.register] = load.bits;
                        let register = load.register;
                        registers[register] = Some(load);
                    }
                } else if op == 0x2b {
                    require(
                        written && read.is_none(),
                        "CPU store lacks its completed sink",
                    )?;
                } else {
                    require(
                        read.is_none() && !written,
                        "scalar effect on CPU register instruction",
                    )?;
                    if begin.word != 0 {
                        require(
                            op == 0 && begin.word & 63 == 0x21 && (begin.word >> 6) & 31 == 0,
                            "unsupported CPU register instruction",
                        )?;
                        let rs = ((begin.word >> 21) & 31) as usize;
                        let rt = ((begin.word >> 16) & 31) as usize;
                        let rd = ((begin.word >> 11) & 31) as usize;
                        if rd != 0 {
                            expected[rd] =
                                sign32((begin.gpr[rs] as u32).wrapping_add(begin.gpr[rt] as u32));
                            registers[rd] = None;
                        }
                    }
                }
                require(row.gpr == expected, "CPU instruction result mismatch")?;
                let step = h
                    .steps
                    .get(cpu_instructions)
                    .ok_or("CPU instruction lacks independent step snapshot")?;
                require(
                    step.index as usize == cpu_instructions
                        && (step.phase, step.word, step.pc) == (begin.phase, begin.word, begin.pc)
                        && step.before == begin.gpr
                        && step.after == row.gpr,
                    "CPU decoder snapshots disagree with independent step",
                )?;
                cpu_instructions += 1;
                previous_cpu = Some(row);
            }
            Kind::RspEnd => {
                boundary(&row, false)?;
                let Some(Active::Rsp {
                    begin,
                    lanes,
                    consumed,
                    breaking,
                    expected_gpr,
                    definition,
                }) = active.take()
                else {
                    return Err("RSP end lacks begin".into());
                };
                require(
                    same(&begin, &row)
                        && consumed == lanes.len()
                        && row.rgpr == expected_gpr
                        && row.vector_byte == begin.vector_byte
                        && row.next == ((begin.pc as u32 + 4) & 4095)
                        && row.halted == breaking,
                    "RSP result/effect census mismatch",
                )?;
                if let Some(definition) = definition {
                    rsp_registers[definition.register as usize] = Some(definition.context);
                    rsp_definitions.push(definition);
                }
                rsp_instructions += 1;
                previous_rsp = Some(row);
            }
        }
    }
    require(active.is_none(), "truncated RSP/CPU instruction context")?;
    require(
        cpu_instructions == h.steps.len(),
        "extra independent CPU step",
    )?;
    require(
        dmem == h.final_dmem && imem == h.final_imem,
        "modeled effects disagree with final backing snapshots",
    )?;
    Ok(RspCpuImemReport {
        format: h.format,
        profile: h.profile,
        source_sha256: digest,
        records,
        cpu_instructions,
        rsp_instructions,
        copies,
        final_imem_writers: iorig,
        final_dmem_sha256: sha256(&dmem),
        final_imem_sha256: sha256(&imem),
        rsp_definitions: definitions_enabled.then_some(rsp_definitions),
        source_ancestry_certified: false,
        mutation_coverage_certified: false,
        imem_execution_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}
pub fn verify_rsp_cpu_imem_report(
    report: &RspCpuImemReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_rsp_cpu_imem_history(source, expected_sha256)?,
        "RSP/CPU IMEM report differs from complete source",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};
    fn row(kind: &str, ordinal: u64, context: u64) -> Value {
        json!({"kind":kind,"ordinal":ordinal,"context":context,"pc":0xffff_ffff_a000_6000u64,
            "phase":1,"word":0,"address":0,"bank":0,"offset":0,"bytes":0,"value":0,
            "cpu":false,"next":0,"halted":false,"vector_byte":0,"gpr":[],"rgpr":[]})
    }
    fn fixture() -> Value {
        let mut rsp = [0u32; 32];
        rsp[1] = 0x1000;
        rsp[2] = 0x11223344;
        let mut cpu = [0u64; 32];
        cpu[16] = 0xffff_ffff_a400_0000;
        let mut rows = Vec::new();
        let mut begin = row("rsp_begin", 1, 1);
        begin["pc"] = json!(0xffc);
        begin["next"] = json!(0xffc);
        begin["word"] = json!(0xac220000u32);
        begin["rgpr"] = json!(rsp);
        rows.push(begin.clone());
        for (index, value) in [0x11, 0x22, 0x33, 0x44].into_iter().enumerate() {
            let mut sink = row("rsp_sink", index as u64 + 2, 1);
            sink["pc"] = json!(0xffc);
            sink["word"] = json!(0xac220000u32);
            sink["address"] = json!(index);
            sink["offset"] = json!(index);
            sink["bytes"] = json!(1);
            sink["value"] = json!(value);
            rows.push(sink);
        }
        begin["kind"] = json!("rsp_end");
        begin["ordinal"] = json!(6);
        begin["next"] = json!(0);
        rows.push(begin);
        let mut load = row("cpu_begin", 7, 7);
        load["word"] = json!(0x8e080000u32);
        load["cpu"] = json!(true);
        load["gpr"] = json!(cpu);
        rows.push(load.clone());
        let mut read = row("sp_read", 8, 7);
        read["word"] = load["word"].clone();
        read["cpu"] = json!(true);
        read["address"] = json!(0x04000000);
        read["bytes"] = json!(4);
        read["value"] = json!(0x11223344);
        rows.push(read);
        cpu[8] = 0x11223344;
        load["kind"] = json!("cpu_end");
        load["ordinal"] = json!(9);
        load["gpr"] = json!(cpu);
        rows.push(load);
        let mut store = row("cpu_begin", 10, 10);
        store["pc"] = json!(0xffff_ffff_a000_6004u64);
        store["word"] = json!(0xae081000u32);
        store["cpu"] = json!(true);
        store["gpr"] = json!(cpu);
        rows.push(store.clone());
        let mut sink = row("sp_write", 11, 10);
        sink["pc"] = store["pc"].clone();
        sink["word"] = store["word"].clone();
        sink["cpu"] = json!(true);
        sink["address"] = json!(0x04001000);
        sink["bank"] = json!(1);
        sink["bytes"] = json!(4);
        sink["value"] = json!(0x11223344);
        rows.push(sink);
        store["kind"] = json!("cpu_end");
        store["ordinal"] = json!(12);
        rows.push(store);
        let starts: Vec<_> = rows.iter().filter(|r| r["kind"] == "cpu_begin").collect();
        let ends: Vec<_> = rows.iter().filter(|r| r["kind"] == "cpu_end").collect();
        let steps:Vec<_>=starts.into_iter().zip(ends).enumerate().map(|(index,(start,end))|json!({
            "phase":start["phase"],"index":index,"word":start["word"],"pc":start["pc"],"before":start["gpr"],"after":end["gpr"]
        })).collect();
        json!({"format":FORMAT,"profile":PROFILE,"initial_dmem":[0,0,0,0],"initial_imem":[0,0,0,0],
            "final_dmem":[17,34,51,68],"final_imem":[17,34,51,68],"steps":steps,"events":rows})
    }
    fn inspect(data: &Value) -> Result<RspCpuImemReport, String> {
        let bytes = serde_json::to_vec(data).unwrap();
        inspect_rsp_cpu_imem_history(&bytes, &sha256(&bytes))
    }
    #[test]
    fn decoded_rsp_address_bit_twelve_still_writes_dmem_then_cpu_installs_imem() {
        let report = inspect(&fixture()).unwrap();
        assert_eq!(report.copies.len(), 1);
        assert_eq!(report.copies[0].read_ordinal, 8);
        assert!(
            report.copies[0]
                .source_bytes
                .iter()
                .all(|origin| matches!(origin, SpByteOrigin::Rsp { context: 1, .. }))
        );
        assert!(!report.imem_execution_certified && !report.native_complete);
    }
    #[test]
    fn breakpoint_or_zero_register_forgery_cannot_claim_a_store() {
        let mut breakpoint = fixture();
        breakpoint["events"][0]["word"] = json!(13);
        breakpoint["events"][5]["word"] = json!(13);
        assert!(inspect(&breakpoint).is_err());
        let mut zero = fixture();
        zero["events"][0]["rgpr"][0] = json!(1);
        assert!(inspect(&zero).is_err());
        let mut cpu_zero = fixture();
        cpu_zero["events"][6]["gpr"][0] = json!(1);
        assert!(inspect(&cpu_zero).is_err());
    }
    #[test]
    fn source_report_and_instruction_effect_deletion_are_bound() {
        let data = fixture();
        let bytes = serde_json::to_vec(&data).unwrap();
        let digest = sha256(&bytes);
        let mut report = inspect_rsp_cpu_imem_history(&bytes, &digest).unwrap();
        report.copies[0].read_ordinal = 1;
        assert!(verify_rsp_cpu_imem_report(&report, &bytes, &digest).is_err());
        assert!(inspect_rsp_cpu_imem_history(&bytes, &"0".repeat(64)).is_err());
        let mut deleted = data;
        deleted["events"].as_array_mut().unwrap().remove(3);
        assert!(inspect(&deleted).is_err());
    }

    fn defined_fixture(repeat: bool) -> Value {
        let mut data = fixture();
        data["format"] = json!(DEFINITION_FORMAT);
        data["profile"] = json!(DEFINITION_PROFILE);
        fn replace(value: &mut Value) {
            match value {
                Value::Array(values) => values.iter_mut().for_each(replace),
                Value::Object(values) => values.values_mut().for_each(replace),
                _ if value.as_u64() == Some(0x11223344) => *value = json!(0x3344),
                _ => {}
            }
        }
        replace(&mut data);
        data["final_dmem"] = json!([0, 0, 0x33, 0x44]);
        data["final_imem"] = data["final_dmem"].clone();
        data["events"][1]["value"] = json!(0);
        data["events"][2]["value"] = json!(0);
        let mut words = vec![0x34023344u32];
        if repeat {
            words.push(0x34023344);
        }
        words.extend([0x00401821, 0x00601021]);
        let mut regs = [0u32; 32];
        regs[1] = 0x1000;
        regs[2] = 0x5555;
        let mut prefix = Vec::new();
        for (n, word) in words.iter().copied().enumerate() {
            let ordinal = prefix.len() as u64 + 1;
            let pc = 0xffc - (words.len() - n) as u32 * 4;
            let mut begin = row("rsp_begin", ordinal, ordinal);
            begin["pc"] = json!(pc);
            begin["next"] = json!(pc);
            begin["word"] = json!(word);
            begin["rgpr"] = json!(regs);
            prefix.push(begin.clone());
            if word >> 26 == 0x0d {
                regs[2] = 0x3344;
            } else if (word >> 11) & 31 == 3 {
                regs[3] = regs[2];
            } else {
                regs[2] = regs[3];
            }
            begin["kind"] = json!("rsp_end");
            begin["ordinal"] = json!(ordinal + 1);
            begin["next"] = json!(pc + 4);
            begin["rgpr"] = json!(regs);
            prefix.push(begin);
        }
        let shift = prefix.len() as u64;
        for r in data["events"].as_array_mut().unwrap() {
            r["ordinal"] = json!(r["ordinal"].as_u64().unwrap() + shift);
            r["context"] = json!(r["context"].as_u64().unwrap() + shift);
            if r["kind"] == "rsp_begin" || r["kind"] == "rsp_end" {
                r["rgpr"] = json!(regs);
            }
            prefix.push(r.clone());
        }
        data["events"] = json!(prefix);
        data
    }

    #[test]
    fn rsp_literal_and_same_value_definitions_reach_imem_on_the_original_clock() {
        for repeat in [false, true] {
            let data = defined_fixture(repeat);
            let report = inspect(&data).unwrap();
            let definitions = report.rsp_definitions.as_ref().unwrap();
            assert_eq!(definitions.len(), if repeat { 4 } else { 3 });
            assert!(matches!(
                definitions[0].expression,
                RspDefinitionExpression::Ori {
                    source: RspRegisterParent::ArchitecturalZero,
                    immediate: 0x3344
                }
            ));
            let last = definitions.last().unwrap();
            assert_eq!(last.value, 0x3344);
            assert!(matches!(last.expression, RspDefinitionExpression::Addu {
                left: RspRegisterParent::Definition { context }, right: RspRegisterParent::ArchitecturalZero
            } if context == definitions[definitions.len() - 2].context));
            assert!(report.copies[0].source_bytes.iter().all(|b| matches!(b,
                SpByteOrigin::Rsp { source_definition: Some(context), .. } if *context == last.context)));
            if repeat {
                assert_ne!(definitions[0].context, definitions[1].context);
            }
            assert!(
                !report.source_ancestry_certified
                    && !report.mutation_coverage_certified
                    && !report.imem_execution_certified
                    && !report.native_complete
            );
        }
    }

    #[test]
    fn rsp_reentry_cuts_definitions_even_when_scalar_values_are_identical() {
        let mut data = defined_fixture(false);
        for r in data["events"].as_array_mut().unwrap().iter_mut().skip(6) {
            r["phase"] = json!(2);
        }
        for step in data["steps"].as_array_mut().unwrap() {
            step["phase"] = json!(2);
        }
        let report = inspect(&data).unwrap();
        assert_eq!(report.rsp_definitions.as_ref().unwrap().len(), 3);
        assert!(report.copies[0].source_bytes.iter().all(|b| matches!(
            b,
            SpByteOrigin::Rsp {
                source_definition: None,
                ..
            }
        )));
    }

    #[test]
    fn rsp_definition_snapshots_profiles_parents_and_store_tags_are_rechecked() {
        let data = defined_fixture(false);
        for mode in 0..4 {
            let mut forged = data.clone();
            match mode {
                0 => forged["events"][1]["rgpr"][2] = json!(0x3345),
                1 => forged["events"][3]["rgpr"][10] = json!(1),
                2 => forged["events"][2]["word"] = json!(0x00401861u32),
                _ => forged["profile"] = json!(PROFILE),
            }
            assert!(inspect(&forged).is_err(), "mode {mode}");
        }
        let bytes = serde_json::to_vec(&data).unwrap();
        let digest = sha256(&bytes);
        let report = inspect(&data).unwrap();
        let mut forged = report.clone();
        if let RspDefinitionExpression::Addu { left, .. } =
            &mut forged.rsp_definitions.as_mut().unwrap()[2].expression
        {
            *left = RspRegisterParent::Definition { context: 999999 };
        }
        assert!(verify_rsp_cpu_imem_report(&forged, &bytes, &digest).is_err());
        let mut forged = report;
        if let SpByteOrigin::Rsp {
            source_definition, ..
        } = &mut forged.copies[0].source_bytes[0]
        {
            *source_definition = None;
        }
        assert!(verify_rsp_cpu_imem_report(&forged, &bytes, &digest).is_err());
        let mut legacy = data;
        legacy["format"] = json!(FORMAT);
        legacy["profile"] = json!(PROFILE);
        assert!(inspect(&legacy).is_err());
    }

    #[test]
    fn rsp_definitions_keep_opaque_incoming_operands_distinct_from_zero() {
        let mut data = defined_fixture(false);
        for index in [0, 1] {
            data["events"][index]["word"] = json!(0x34222344u32);
        }
        let report = inspect(&data).unwrap();
        assert!(matches!(
            report.rsp_definitions.as_ref().unwrap()[0].expression,
            RspDefinitionExpression::Ori {
                source: RspRegisterParent::CapturedInput {
                    register: 1,
                    value: 0x1000
                },
                immediate: 0x2344
            }
        ));
        assert!(!report.source_ancestry_certified);
        let mut encoded = serde_json::to_value(&report).unwrap();
        encoded["rsp_definitions"][0]["expression"]["source"]["invented_root"] = json!(true);
        assert!(serde_json::from_value::<RspCpuImemReport>(encoded).is_err());
    }
}
