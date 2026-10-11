//! Bounded compiler-time replay of captured CPU Word copies and XORI transforms.
//! Source binding is distinct from sensor completeness or executable lifetime.
use crate::{
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-cpu-copy-history-v0";

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
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "CPU copy source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(
        history.format == FORMAT,
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
    for (index, store) in contexts.iter().enumerate() {
        let (op, _, sr, _) = decode(store.begin.word);
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
        let Some(read) = load.effect else {
            continue;
        };
        let write = store.effect.expect("validated store effect");
        let mask = transform.map(|t| t.begin.word as u16);
        require(
            write.value == read.value ^ u32::from(mask.unwrap_or(0)),
            "CPU def-use payload mismatch",
        )?;
        witnesses.push(WordCopyWitness {
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
        });
    }
    Ok(CpuCopyReport {
        format: FORMAT.into(),
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
