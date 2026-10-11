//! Bounded compiler-time replay of captured CPU Word copies and XORI transforms.
//! Source binding is distinct from sensor completeness or executable lifetime.
use crate::{
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const FORMAT: &str = "plaid-cpu-copy-history-v0";
pub const DEFINITION_FORMAT: &str = "plaid-cpu-word-definitions-v0";
pub const LINEAGE_FORMAT: &str = "plaid-cpu-copy-lineage-v0";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    instruction_events: Vec<Instruction>,
    scalar_events: Vec<Scalar>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Instruction {
    begin: bool,
    ordinal: u64,
    context: u64,
    phase: u32,
    pc: GuestVirtualAddr,
    word: u32,
    gpr: [u64; 32],
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Scalar {
    ordinal: u64,
    context: u64,
    phase: u32,
    pc: GuestVirtualAddr,
    write: bool,
    address: PhysicalAddr,
    bytes: u32,
    uncached_cpu: bool,
    value: u32,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LoadKind {
    Lw,
    Lwu,
}

/// Big-endian lane expression, anchored to the parent witness's actual read.
/// The source address is a read location, not an ultimate ROM/backing ancestor.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ByteExpression {
    pub source: PhysicalAddr,
    pub destination: PhysicalAddr,
    pub xor: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WordCopyWitness {
    pub phase: u32,
    pub load_context: u64,
    pub read_ordinal: u64,
    pub transform_context: Option<u64>,
    pub store_context: u64,
    pub write_ordinal: u64,
    pub source: PhysicalAddr,
    pub destination: PhysicalAddr,
    pub source_word: u32,
    pub result_word: u32,
    pub xor_imm: Option<u16>,
    pub load_kind: LoadKind,
    pub byte_expr: [ByteExpression; 4],
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuCopyReport {
    pub format: String,
    pub source_sha256: String,
    pub instruction_contexts: usize,
    pub scalar_effects: usize,
    pub witnesses: Vec<WordCopyWitness>,
    pub source_origin_certified: bool,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

/// A local storage generation minted by one captured successful aligned SW.
/// `generation` is scoped by `phase`; it is intentionally distinct from the
/// source event ordinal. Neither identity implies complete mutation coverage.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CapturedStorageGeneration {
    pub phase: u32,
    pub generation: u64,
    pub write_ordinal: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CapturedWordWrite {
    pub identity: CapturedStorageGeneration,
    pub context: u64,
    pub destination: PhysicalAddr,
    pub value: u32,
}

/// A copy witness joined only to storage writers visible in the same authenticated
/// source and phase. `captured_source_generation=None` means UNKNOWN, not initial
/// or immutable storage.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CapturedWordLineage {
    pub witness: WordCopyWitness,
    /// Latest compatible captured writer, not certified ultimate ancestry.
    /// Contradictory reads cut this candidate until a fresh captured write.
    pub captured_source_generation: Option<CapturedStorageGeneration>,
    pub destination_generation: CapturedStorageGeneration,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuCopyLineageReport {
    pub format: String,
    pub source_format: String,
    pub source_sha256: String,
    pub captured_word_writes: Vec<CapturedWordWrite>,
    pub word_lineage: Vec<CapturedWordLineage>,
    pub source_storage_ancestry_certified: bool,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

struct Context<'a> {
    begin: &'a Instruction,
    end: Option<&'a Instruction>,
    effect: Option<&'a Scalar>,
}
enum Event<'a> {
    Instruction(&'a Instruction),
    Scalar(&'a Scalar),
}
fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}
fn decode(word: u32) -> (u32, usize, usize, i16) {
    (
        word >> 26,
        ((word >> 21) & 31) as usize,
        ((word >> 16) & 31) as usize,
        word as i16,
    )
}
fn address(base: u64, immediate: i16) -> Result<PhysicalAddr, String> {
    let va = base.wrapping_add_signed(i64::from(immediate));
    let pa = (va & 0x1fff_ffff) as u32;
    require(
        (0xffff_ffff_a000_0000..=0xffff_ffff_bfff_ffff).contains(&va)
            && va.is_multiple_of(4)
            && pa <= 0x007f_fffc,
        "copy effect outside aligned identity KSEG1 RDRAM",
    )?;
    Ok(PhysicalAddr(pa))
}

/// The expected hash must come from a separately trusted complete source receipt.
/// Successful replay never certifies that the sensor captured every operation.
pub fn inspect_cpu_copy_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<CpuCopyReport, String> {
    inspect(source, expected_sha256, false)
}

/// Track captured register definitions across unrelated validated instructions.
/// This separate protocol does not relax capture/lifetime completeness gates.
pub fn inspect_cpu_definition_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<CpuCopyReport, String> {
    inspect(source, expected_sha256, true)
}

/// Reuse the strict adjacent-copy replay, then retain every captured successful
/// Word store so overlapping copies can name the exact earlier captured storage
/// generation visible at a later load. Missing captured writers remain UNKNOWN.
pub fn inspect_cpu_copy_lineage(
    source: &[u8],
    expected_sha256: &str,
) -> Result<CpuCopyLineageReport, String> {
    let report = inspect_cpu_copy_history(source, expected_sha256)?;
    lineage(source, report)
}

/// Definition-tracking counterpart of [`inspect_cpu_copy_lineage`].
pub fn inspect_cpu_definition_lineage(
    source: &[u8],
    expected_sha256: &str,
) -> Result<CpuCopyLineageReport, String> {
    let report = inspect_cpu_definition_history(source, expected_sha256)?;
    lineage(source, report)
}

fn inspect(
    source: &[u8],
    expected_sha256: &str,
    definitions: bool,
) -> Result<CpuCopyReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "CPU copy source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(
        history.format
            == if definitions {
                DEFINITION_FORMAT
            } else {
                FORMAT
            },
        "unsupported CPU copy history format",
    )?;
    let mut events: Vec<_> = history
        .instruction_events
        .iter()
        .map(|e| (e.ordinal, Event::Instruction(e)))
        .chain(
            history
                .scalar_events
                .iter()
                .map(|e| (e.ordinal, Event::Scalar(e))),
        )
        .collect();
    events.sort_by_key(|e| e.0);
    let mut contexts = Vec::<Context<'_>>::new();
    let mut active: Option<Context<'_>> = None;
    for (index, (ordinal, event)) in events.into_iter().enumerate() {
        require(
            ordinal == index as u64 + 1,
            "noncontiguous CPU copy source ordinals",
        )?;
        match event {
            Event::Instruction(e) => {
                require(
                    e.phase != 0 && e.pc.0.is_multiple_of(4) && e.gpr[0] == 0,
                    "invalid CPU instruction state",
                )?;
                if e.begin {
                    require(
                        active.is_none() && e.context == e.ordinal,
                        "invalid CPU begin context",
                    )?;
                    if let Some(previous) = contexts.last() {
                        let end = previous.end.expect("completed context");
                        if previous.begin.phase == e.phase {
                            require(
                                end.gpr == e.gpr
                                    && end.ordinal.checked_add(1) == Some(e.ordinal)
                                    && previous.begin.pc.0.checked_add(4) == Some(e.pc.0),
                                "CPU copy register/control continuity mismatch",
                            )?;
                        } else {
                            require(
                                e.phase > previous.begin.phase,
                                "CPU segment reused or reordered",
                            )?;
                        }
                    }
                    active = Some(Context {
                        begin: e,
                        end: None,
                        effect: None,
                    });
                } else {
                    let mut context = active.take().ok_or("CPU end without begin")?;
                    let b = context.begin;
                    require(
                        (e.context, e.phase, e.pc, e.word) == (b.context, b.phase, b.pc, b.word),
                        "CPU end context mismatch",
                    )?;
                    context.end = Some(e);
                    contexts.push(context);
                }
            }
            Event::Scalar(e) => {
                let c = active.as_mut().ok_or("unscoped CPU scalar effect")?;
                require(
                    c.effect.is_none()
                        && (e.context, e.phase, e.pc)
                            == (c.begin.context, c.begin.phase, c.begin.pc),
                    "CPU scalar context mismatch",
                )?;
                c.effect = Some(e);
            }
        }
    }
    require(active.is_none(), "truncated CPU instruction context")?;
    for c in &contexts {
        let b = c.begin;
        let end = c.end.expect("completed context");
        let (op, rs, rt, imm) = decode(b.word);
        let mut expected = b.gpr;
        match op {
            0x23 | 0x27 | 0x2b => {
                if let Some(effect) = c.effect {
                    require(
                        effect.uncached_cpu
                            && effect.bytes == 4
                            && effect.address == address(b.gpr[rs], imm)?
                            && effect.write == (op == 0x2b),
                        "CPU Word effect does not match decoded operation",
                    )?;
                    if op == 0x2b {
                        require(
                            effect.value == b.gpr[rt] as u32,
                            "CPU store payload mismatch",
                        )?;
                    } else if rt != 0 {
                        expected[rt] = if op == 0x23 {
                            (effect.value as i32 as i64) as u64
                        } else {
                            u64::from(effect.value)
                        };
                    }
                } else {
                    require(op != 0x2b, "CPU store missing completed effect")?;
                }
            }
            0x0d | 0x0e => {
                require(c.effect.is_none(), "scalar effect on logical instruction")?;
                if rt != 0 {
                    let imm = u64::from(b.word & 0xffff);
                    expected[rt] = if op == 0x0d {
                        b.gpr[rs] | imm
                    } else {
                        b.gpr[rs] ^ imm
                    };
                }
            }
            _ => require(
                b.word == 0 && c.effect.is_none(),
                "unsupported CPU copy instruction",
            )?,
        }
        require(end.gpr == expected, "CPU instruction result mismatch")?;
    }
    let mut witnesses = Vec::new();
    let mut registers: [Option<(usize, Option<usize>)>; 32] = [None; 32];
    for (index, store) in contexts.iter().enumerate() {
        let (op, _, sr, _) = decode(store.begin.word);
        if definitions {
            if index == 0 || contexts[index - 1].begin.phase != store.begin.phase {
                registers = [None; 32];
            }
            let (_, rs, rt, _) = decode(store.begin.word);
            match op {
                0x23 | 0x27 if rt != 0 => {
                    registers[rt] = store.effect.map(|_| (index, None));
                }
                0x0e if rt != 0 => {
                    registers[rt] = if rs == rt {
                        registers[rs].and_then(|(load, transform)| {
                            transform.is_none().then_some((load, Some(index)))
                        })
                    } else {
                        None
                    };
                }
                0x0d if rt != 0 => registers[rt] = None,
                0x2b => {
                    if let Some((load, transform)) = registers[rt] {
                        witnesses.push(word_witness(
                            &contexts[load],
                            transform.map(|i| &contexts[i]),
                            store,
                        )?);
                    }
                }
                _ => {}
            }
            continue;
        }
        if op != 0x2b || index == 0 {
            continue;
        }
        let previous = &contexts[index - 1];
        let (prev_op, ts, tr, _) = decode(previous.begin.word);
        let (load, transform) = if prev_op == 0x0e && index >= 2 && ts == tr && tr == sr {
            (&contexts[index - 2], Some(previous))
        } else {
            (previous, None)
        };
        let (load_op, _, lr, _) = decode(load.begin.word);
        if !matches!(load_op, 0x23 | 0x27)
            || lr == 0
            || lr != sr
            || load.begin.phase != store.begin.phase
        {
            continue;
        }
        if load.effect.is_none() {
            continue;
        }
        witnesses.push(word_witness(load, transform, store)?);
    }
    Ok(CpuCopyReport {
        format: history.format,
        source_sha256: digest,
        instruction_contexts: contexts.len(),
        scalar_effects: history.scalar_events.len(),
        witnesses,
        source_origin_certified: false,
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

fn lineage(source: &[u8], report: CpuCopyReport) -> Result<CpuCopyLineageReport, String> {
    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(
        history.format == report.format && sha256(source) == report.source_sha256,
        "CPU lineage source differs from validated copy report",
    )?;
    let mut effects: Vec<_> = history.scalar_events.iter().collect();
    effects.sort_by_key(|e| e.ordinal);
    let mut phase = None;
    let mut generation = 0u64;
    let mut latest = BTreeMap::<PhysicalAddr, (CapturedStorageGeneration, u32)>::new();
    let mut read_generations = BTreeMap::<u64, Option<CapturedStorageGeneration>>::new();
    let mut write_generations = BTreeMap::<u64, CapturedStorageGeneration>::new();
    let mut captured_word_writes = Vec::new();
    for effect in effects {
        if phase != Some(effect.phase) {
            require(
                phase.is_none_or(|previous| effect.phase > previous),
                "CPU lineage phase reused or reordered",
            )?;
            phase = Some(effect.phase);
            generation = 0;
            latest.clear();
        }
        if effect.write {
            generation = generation
                .checked_add(1)
                .ok_or("CPU lineage generation overflow")?;
            let identity = CapturedStorageGeneration {
                phase: effect.phase,
                generation,
                write_ordinal: effect.ordinal,
            };
            require(
                write_generations.insert(effect.ordinal, identity).is_none(),
                "duplicate CPU lineage write ordinal",
            )?;
            latest.insert(effect.address, (identity, effect.value));
            captured_word_writes.push(CapturedWordWrite {
                identity,
                context: effect.context,
                destination: effect.address,
                value: effect.value,
            });
        } else {
            if latest
                .get(&effect.address)
                .is_some_and(|(_, value)| *value != effect.value)
            {
                // The sensed read contradicts the captured writer. An unsensed
                // intervening mutation is possible; equal later bits cannot
                // restore the old candidate without a fresh observed write.
                latest.remove(&effect.address);
            }
            require(
                read_generations
                    .insert(
                        effect.ordinal,
                        latest.get(&effect.address).map(|(identity, _)| *identity),
                    )
                    .is_none(),
                "duplicate CPU lineage read ordinal",
            )?;
        }
    }
    let mut word_lineage = Vec::with_capacity(report.witnesses.len());
    for witness in report.witnesses {
        let captured_source_generation = read_generations
            .get(&witness.read_ordinal)
            .copied()
            .ok_or("copy witness read missing captured lineage state")?;
        let destination_generation = write_generations
            .get(&witness.write_ordinal)
            .copied()
            .ok_or("copy witness write missing captured lineage generation")?;
        require(
            destination_generation.phase == witness.phase
                && captured_source_generation.is_none_or(|source| source.phase == witness.phase),
            "copy witness crossed captured storage phase",
        )?;
        word_lineage.push(CapturedWordLineage {
            witness,
            captured_source_generation,
            destination_generation,
        });
    }
    Ok(CpuCopyLineageReport {
        format: LINEAGE_FORMAT.into(),
        source_format: report.format,
        source_sha256: report.source_sha256,
        captured_word_writes,
        word_lineage,
        source_storage_ancestry_certified: false,
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

fn word_witness(
    load: &Context<'_>,
    transform: Option<&Context<'_>>,
    store: &Context<'_>,
) -> Result<WordCopyWitness, String> {
    let load_op = decode(load.begin.word).0;
    let read = load.effect.expect("validated load effect");
    let write = store.effect.expect("validated store effect");
    let mask = transform.map(|t| t.begin.word as u16);
    require(
        write.value == read.value ^ u32::from(mask.unwrap_or(0)),
        "CPU def-use payload mismatch",
    )?;
    Ok(WordCopyWitness {
        phase: store.begin.phase,
        load_context: load.begin.context,
        read_ordinal: read.ordinal,
        transform_context: transform.map(|t| t.begin.context),
        store_context: store.begin.context,
        write_ordinal: write.ordinal,
        source: read.address,
        destination: write.address,
        source_word: read.value,
        result_word: write.value,
        xor_imm: mask,
        load_kind: if load_op == 0x23 {
            LoadKind::Lw
        } else {
            LoadKind::Lwu
        },
        byte_expr: std::array::from_fn(|lane| ByteExpression {
            // Both aligned Word spans were validated inside the 8-MiB bank.
            source: PhysicalAddr(read.address.0 + lane as u32),
            destination: PhysicalAddr(write.address.0 + lane as u32),
            xor: (u32::from(mask.unwrap_or(0)) >> (8 * (3 - lane))) as u8,
        }),
    })
}

pub fn verify_cpu_copy_report(
    report: &CpuCopyReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_cpu_copy_history(source, expected_sha256)?,
        "CPU copy report differs from complete source replay",
    )
}

pub fn verify_cpu_definition_report(
    report: &CpuCopyReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_cpu_definition_history(source, expected_sha256)?,
        "CPU definition report differs from complete source replay",
    )
}

pub fn verify_cpu_copy_lineage_report(
    report: &CpuCopyLineageReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_cpu_copy_lineage(source, expected_sha256)?,
        "CPU copy lineage report differs from complete source replay",
    )
}

pub fn verify_cpu_definition_lineage_report(
    report: &CpuCopyLineageReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_cpu_definition_lineage(source, expected_sha256)?,
        "CPU definition lineage report differs from complete source replay",
    )
}
