//! Source-bound replay of bounded guest CP0 Cause software-interrupt writes.
//!
//! A successful guest MTC0 to Cause replaces only software-pending IP0/IP1.
//! Every observed successful write is a fresh operation generation, including a
//! same-value write. IP2..IP7 are retained as separately produced state; this
//! module does not infer their producer ancestry, interrupt eligibility, vector
//! reachability, handler provenance, sensor completeness, or native readiness.

use crate::{program::GuestVirtualAddr, rom::sha256};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-software-interrupt-history-v0";
const MTC0_CAUSE_BASE: u32 = 0x4080_6800;
const MTC0_CAUSE_MASK: u32 = 0xffe0_ffff;
const SOFTWARE_PENDING_MASK: u8 = 0x03;
const HARDWARE_PENDING_MASK: u8 = 0xfc;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SoftwareInterruptGeneration {
    pub operation_generation: u64,
    pub epoch: u64,
    pub context: u64,
    pub pc: GuestVirtualAddr,
    pub source_register: u8,
    pub raw_cause: u32,
    pub begin_ordinal: u64,
    pub write_ordinal: u64,
    pub end_ordinal: u64,
    pub before_pending: u8,
    pub after_pending: u8,
    /// Bits IP2..IP7 observed on both sides of this Cause write. Their producer
    /// identity remains outside this module.
    pub preserved_hardware_pending: u8,
    pub same_pending_value: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SoftwareInterruptNoWriteAttempt {
    pub epoch: u64,
    pub context: u64,
    pub pc: GuestVirtualAddr,
    pub source_register: u8,
    pub raw_cause: u32,
    pub begin_ordinal: u64,
    pub end_ordinal: u64,
    pub before_pending: u8,
    pub exception_code: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SoftwareInterruptHistoryReport {
    pub format: String,
    pub source_sha256: String,
    pub attempts: usize,
    pub successful_writes: usize,
    pub same_value_generations: usize,
    pub generations: Vec<SoftwareInterruptGeneration>,
    pub no_write_attempts: Vec<SoftwareInterruptNoWriteAttempt>,
    pub sensor_coverage_certified: bool,
    pub hardware_pending_producers_certified: bool,
    pub interrupt_gate_chronology_certified: bool,
    pub handler_provenance_certified: bool,
    pub whole_rom_roots_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    Begin {
        ordinal: u64,
        context: u64,
        epoch: u64,
        pc: GuestVirtualAddr,
        word: u32,
        raw_cause: u32,
        before_pending: u8,
    },
    Write {
        ordinal: u64,
        context: u64,
        raw_cause: u32,
        before_pending: u8,
        after_pending: u8,
    },
    End {
        ordinal: u64,
        context: u64,
        epoch: u64,
        pc: GuestVirtualAddr,
        exception_code: u8,
    },
}

struct Active {
    begin_ordinal: u64,
    context: u64,
    epoch: u64,
    pc: GuestVirtualAddr,
    source_register: u8,
    raw_cause: u32,
    before_pending: u8,
    write: Option<ObservedWrite>,
}

struct ObservedWrite {
    ordinal: u64,
    after_pending: u8,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn decode_mtc0_cause(word: u32) -> Option<u8> {
    if word & MTC0_CAUSE_MASK != MTC0_CAUSE_BASE {
        return None;
    }
    Some(((word >> 16) & 31) as u8)
}

fn apply_guest_cause_write(before_pending: u8, raw_cause: u32) -> u8 {
    (before_pending & HARDWARE_PENDING_MASK) | (((raw_cause >> 8) as u8) & SOFTWARE_PENDING_MASK)
}

/// Inspect an externally authenticated complete source for this bounded sensor.
///
/// The expected hash must come from a separately trusted complete-source receipt.
/// Replaying this source authenticates only the operations represented here. It
/// does not prove that every reachable CP0 Cause write was sensed.
pub fn inspect_software_interrupt_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<SoftwareInterruptHistoryReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "software-interrupt source receipt mismatch",
    )?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported software-interrupt history format",
    )?;

    let mut next_ordinal = 1u64;
    let mut last_epoch = 0u64;
    let mut attempts = 0usize;
    let mut active: Option<Active> = None;
    let mut generations = Vec::new();
    let mut no_write_attempts = Vec::new();

    for event in history.events {
        match event {
            Event::Begin {
                ordinal,
                context,
                epoch,
                pc,
                word,
                raw_cause,
                before_pending,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous software-interrupt event ordinals",
                )?;
                next_ordinal += 1;
                require(active.is_none(), "nested software-interrupt begin")?;
                require(
                    context == ordinal,
                    "software-interrupt context must equal begin ordinal",
                )?;
                require(
                    epoch != 0 && epoch >= last_epoch,
                    "invalid or reordered software-interrupt epoch",
                )?;
                require(pc.0.is_multiple_of(4), "unaligned Cause-write PC")?;
                let source_register =
                    decode_mtc0_cause(word).ok_or("history begin is not decoded MTC0 Cause")?;
                last_epoch = epoch;
                attempts += 1;
                active = Some(Active {
                    begin_ordinal: ordinal,
                    context,
                    epoch,
                    pc,
                    source_register,
                    raw_cause,
                    before_pending,
                    write: None,
                });
            }
            Event::Write {
                ordinal,
                context,
                raw_cause,
                before_pending,
                after_pending,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous software-interrupt event ordinals",
                )?;
                next_ordinal += 1;
                let current = active
                    .as_mut()
                    .ok_or("Cause write without active instruction")?;
                require(context == current.context, "Cause write context mismatch")?;
                require(current.write.is_none(), "duplicate Cause write boundary")?;
                require(
                    raw_cause == current.raw_cause,
                    "Cause write operand mismatch",
                )?;
                require(
                    before_pending == current.before_pending,
                    "Cause write pre-state mismatch",
                )?;
                let expected_after = apply_guest_cause_write(before_pending, raw_cause);
                require(
                    after_pending == expected_after,
                    "Cause write pending-bit ownership mismatch",
                )?;
                current.write = Some(ObservedWrite {
                    ordinal,
                    after_pending,
                });
            }
            Event::End {
                ordinal,
                context,
                epoch,
                pc,
                exception_code,
            } => {
                require(
                    ordinal == next_ordinal,
                    "noncontiguous software-interrupt event ordinals",
                )?;
                next_ordinal += 1;
                let current = active
                    .take()
                    .ok_or("software-interrupt end without active instruction")?;
                require(
                    (context, epoch, pc) == (current.context, current.epoch, current.pc),
                    "software-interrupt end context mismatch",
                )?;
                require(exception_code <= 31, "invalid Cause-write exception code")?;

                if let Some(write) = current.write {
                    require(
                        exception_code == 0,
                        "faulting Cause write cannot carry a successful write boundary",
                    )?;
                    let after_pending = write.after_pending;
                    generations.push(SoftwareInterruptGeneration {
                        operation_generation: generations.len() as u64 + 1,
                        epoch: current.epoch,
                        context: current.context,
                        pc: current.pc,
                        source_register: current.source_register,
                        raw_cause: current.raw_cause,
                        begin_ordinal: current.begin_ordinal,
                        write_ordinal: write.ordinal,
                        end_ordinal: ordinal,
                        before_pending: current.before_pending,
                        after_pending,
                        preserved_hardware_pending: current.before_pending & HARDWARE_PENDING_MASK,
                        same_pending_value: current.before_pending == after_pending,
                    });
                } else {
                    require(
                        exception_code != 0,
                        "successful MTC0 Cause lacks an observed write boundary",
                    )?;
                    no_write_attempts.push(SoftwareInterruptNoWriteAttempt {
                        epoch: current.epoch,
                        context: current.context,
                        pc: current.pc,
                        source_register: current.source_register,
                        raw_cause: current.raw_cause,
                        begin_ordinal: current.begin_ordinal,
                        end_ordinal: ordinal,
                        before_pending: current.before_pending,
                        exception_code,
                    });
                }
            }
        }
    }

    require(
        active.is_none(),
        "truncated software-interrupt instruction context",
    )?;
    let same_value_generations = generations
        .iter()
        .filter(|generation| generation.same_pending_value)
        .count();

    Ok(SoftwareInterruptHistoryReport {
        format: history.format,
        source_sha256: digest,
        attempts,
        successful_writes: generations.len(),
        same_value_generations,
        generations,
        no_write_attempts,
        sensor_coverage_certified: false,
        hardware_pending_producers_certified: false,
        interrupt_gate_chronology_certified: false,
        handler_provenance_certified: false,
        whole_rom_roots_certified: false,
        native_complete: false,
    })
}

pub fn verify_software_interrupt_report(
    report: &SoftwareInterruptHistoryReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_software_interrupt_history(source, expected_sha256)?,
        "software-interrupt report differs from complete source replay",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};

    const PC: u64 = 0xffff_ffff_a000_0000;
    const MTC0_T0_CAUSE: u32 = 0x4088_6800;

    fn encoded_source(events: Vec<Value>) -> Vec<u8> {
        serde_json::to_vec(&json!({"format": FORMAT, "events": events})).unwrap()
    }

    fn begin(ordinal: u64, epoch: u64, raw_cause: u32, before_pending: u8) -> Value {
        json!({
            "record": "begin",
            "ordinal": ordinal,
            "context": ordinal,
            "epoch": epoch,
            "pc": PC,
            "word": MTC0_T0_CAUSE,
            "raw_cause": raw_cause,
            "before_pending": before_pending
        })
    }

    fn write(
        ordinal: u64,
        context: u64,
        raw_cause: u32,
        before_pending: u8,
        after_pending: u8,
    ) -> Value {
        json!({
            "record": "write",
            "ordinal": ordinal,
            "context": context,
            "raw_cause": raw_cause,
            "before_pending": before_pending,
            "after_pending": after_pending
        })
    }

    fn end(ordinal: u64, context: u64, epoch: u64, exception_code: u8) -> Value {
        json!({
            "record": "end",
            "ordinal": ordinal,
            "context": context,
            "epoch": epoch,
            "pc": PC,
            "exception_code": exception_code
        })
    }

    fn inspect(events: Vec<Value>) -> Result<SoftwareInterruptHistoryReport, String> {
        let source = encoded_source(events);
        let digest = sha256(&source);
        inspect_software_interrupt_history(&source, &digest)
    }

    #[test]
    fn decodes_only_mtc0_cause_and_retains_source_register() {
        assert_eq!(decode_mtc0_cause(MTC0_T0_CAUSE), Some(8));
        assert_eq!(decode_mtc0_cause(0x4089_6800), Some(9));
        assert_eq!(decode_mtc0_cause(0x4008_6800), None); // MFC0 Cause
        assert_eq!(decode_mtc0_cause(0x4088_6000), None); // MTC0 Status
        assert_eq!(decode_mtc0_cause(0x4088_6801), None); // unsupported select/low bits
    }

    #[test]
    fn reproduces_exhaustive_research_pending_ownership_model() {
        let mut same_value_writes = 0u64;
        for before in 0u16..=u8::MAX.into() {
            for raw in 0u32..=u16::MAX.into() {
                let before = before as u8;
                let after = apply_guest_cause_write(before, raw);
                assert_eq!(
                    after & HARDWARE_PENDING_MASK,
                    before & HARDWARE_PENDING_MASK
                );
                assert_eq!(after & SOFTWARE_PENDING_MASK, ((raw >> 8) as u8) & 3);
                if after == before {
                    same_value_writes += 1;
                }
            }
        }
        assert_eq!(same_value_writes, 4_194_304);
    }

    #[test]
    fn successful_write_mints_generation_without_stealing_hardware_bits() {
        let report = inspect(vec![
            begin(1, 7, 0x0000_0200, 0x85),
            write(2, 1, 0x0000_0200, 0x85, 0x86),
            end(3, 1, 7, 0),
        ])
        .unwrap();
        assert_eq!(report.attempts, 1);
        assert_eq!(report.successful_writes, 1);
        let generation = &report.generations[0];
        assert_eq!(generation.operation_generation, 1);
        assert_eq!(generation.source_register, 8);
        assert_eq!(generation.before_pending, 0x85);
        assert_eq!(generation.after_pending, 0x86);
        assert_eq!(generation.preserved_hardware_pending, 0x84);
        assert!(!generation.same_pending_value);
        assert!(!report.hardware_pending_producers_certified);
        assert!(!report.interrupt_gate_chronology_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn same_value_writes_are_distinct_operation_generations() {
        let report = inspect(vec![
            begin(1, 1, 0x0000_0100, 0x81),
            write(2, 1, 0x0000_0100, 0x81, 0x81),
            end(3, 1, 1, 0),
            begin(4, 1, 0x0000_0100, 0x81),
            write(5, 4, 0x0000_0100, 0x81, 0x81),
            end(6, 4, 1, 0),
        ])
        .unwrap();
        assert_eq!(report.same_value_generations, 2);
        assert_eq!(report.generations[0].operation_generation, 1);
        assert_eq!(report.generations[1].operation_generation, 2);
        assert_ne!(report.generations[0].context, report.generations[1].context);
    }

    #[test]
    fn hostile_cause_payload_cannot_acquire_ip2_through_ip7_ownership() {
        assert_eq!(apply_guest_cause_write(0xa5, 0x0000_fc00), 0xa4);
        assert_eq!(apply_guest_cause_write(0x80, 0xffff_ffff), 0x83);
        assert_eq!(apply_guest_cause_write(0x04, 0), 0x04);
    }

    #[test]
    fn faulting_attempt_mints_no_writer_generation() {
        let report = inspect(vec![begin(1, 2, 0x300, 0x40), end(2, 1, 2, 11)]).unwrap();
        assert_eq!(report.attempts, 1);
        assert!(report.generations.is_empty());
        assert_eq!(report.no_write_attempts.len(), 1);
        assert_eq!(report.no_write_attempts[0].exception_code, 11);
    }

    #[test]
    fn successful_attempt_without_effect_boundary_is_rejected() {
        assert_eq!(
            inspect(vec![begin(1, 1, 0x100, 0), end(2, 1, 1, 0)]).unwrap_err(),
            "successful MTC0 Cause lacks an observed write boundary"
        );
    }

    #[test]
    fn fabricated_hardware_pending_mutation_is_rejected() {
        assert_eq!(
            inspect(vec![
                begin(1, 1, 0x100, 0x04),
                write(2, 1, 0x100, 0x04, 0x09),
                end(3, 1, 1, 0),
            ])
            .unwrap_err(),
            "Cause write pending-bit ownership mismatch"
        );
    }

    #[test]
    fn equal_value_operand_decoy_is_rejected_by_write_context() {
        assert_eq!(
            inspect(vec![
                begin(1, 1, 0x100, 0x01),
                write(2, 1, 0x200, 0x01, 0x02),
                end(3, 1, 1, 0),
            ])
            .unwrap_err(),
            "Cause write operand mismatch"
        );
    }

    #[test]
    fn reordered_or_deleted_events_fail_closed() {
        assert_eq!(
            inspect(vec![
                begin(1, 1, 0x100, 0),
                write(3, 1, 0x100, 0, 1),
                end(4, 1, 1, 0),
            ])
            .unwrap_err(),
            "noncontiguous software-interrupt event ordinals"
        );
        assert_eq!(
            inspect(vec![begin(1, 1, 0x100, 0), write(2, 1, 0x100, 0, 1),]).unwrap_err(),
            "truncated software-interrupt instruction context"
        );
    }

    #[test]
    fn source_hash_and_report_are_rechecked() {
        let source = encoded_source(vec![
            begin(1, 1, 0x100, 0),
            write(2, 1, 0x100, 0, 1),
            end(3, 1, 1, 0),
        ]);
        let digest = sha256(&source);
        let mut report = inspect_software_interrupt_history(&source, &digest).unwrap();
        assert_eq!(
            inspect_software_interrupt_history(&source, &"0".repeat(64)).unwrap_err(),
            "software-interrupt source receipt mismatch"
        );
        report.generations[0].operation_generation = 99;
        assert_eq!(
            verify_software_interrupt_report(&report, &source, &digest).unwrap_err(),
            "software-interrupt report differs from complete source replay"
        );
    }
}
