//! Bounded compiler-time replay of authenticated TLB translation-context writers.
//!
//! This module tracks ordered context-writer generations only. It does not prove
//! installed-entry coverage, PageMask geometry, resident-cache byte provenance,
//! executable lifetime, or a complete CPU/COP0 writer census.
use crate::{program::GuestVirtualAddr, rom::sha256};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-tlb-context-history-v0";
pub const REPORT_FORMAT: &str = "plaid-tlb-context-report-v0";

const MTC0_ENTRYHI_MASK: u32 = 0xffe0_ffff;
const MTC0_ENTRYHI_VALUE: u32 = 0x4080_5000;
const TLBR_WORD: u32 = 0x4200_0001;
const TLBP_WORD: u32 = 0x4200_0008;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct SelectedEntry {
    index: u32,
    generation: u64,
    asid: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
enum Operation {
    Mtc0EntryHi {
        ordinal: u64,
        pc: GuestVirtualAddr,
        word: u32,
        gpr: [u64; 32],
        post_asid: u8,
    },
    Tlbr {
        ordinal: u64,
        pc: GuestVirtualAddr,
        word: u32,
        index: u32,
        pre_asid: u8,
        post_asid: u8,
        selected: Option<SelectedEntry>,
    },
    Tlbp {
        ordinal: u64,
        pc: GuestVirtualAddr,
        word: u32,
        pre_asid: u8,
        post_asid: u8,
    },
}

impl Operation {
    fn ordinal(&self) -> u64 {
        match self {
            Self::Mtc0EntryHi { ordinal, .. }
            | Self::Tlbr { ordinal, .. }
            | Self::Tlbp { ordinal, .. } => *ordinal,
        }
    }

    fn pc(&self) -> GuestVirtualAddr {
        match self {
            Self::Mtc0EntryHi { pc, .. } | Self::Tlbr { pc, .. } | Self::Tlbp { pc, .. } => *pc,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    operations: Vec<Operation>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ContextWriterKind {
    Mtc0EntryHi,
    Tlbr,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TranslationContextGeneration {
    pub generation: u64,
    pub source_ordinal: u64,
    pub pc: GuestVirtualAddr,
    pub writer: ContextWriterKind,
    pub asid: u8,
    pub selected_entry_index: Option<u32>,
    pub selected_entry_generation: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TranslationContextReport {
    pub format: String,
    pub source_sha256: String,
    pub operations: usize,
    pub generations: Vec<TranslationContextGeneration>,
    pub active_generation: Option<u64>,
    pub source_receipt_verified: bool,
    pub sensor_coverage_certified: bool,
    pub installed_mapping_history_certified: bool,
    pub resident_cache_history_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok {
        Ok(())
    } else {
        Err(message.into())
    }
}

/// Replay an already captured finite context-writer source.
///
/// `expected_sha256` must come from a separately trusted complete-source receipt.
/// Matching it authenticates these bytes; it does not certify that the sensor saw
/// every hardware/guest context mutation outside the declared capture scope.
pub fn inspect_tlb_context_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<TranslationContextReport, String> {
    let digest = sha256(source);
    require(digest == expected_sha256, "TLB context source receipt mismatch")?;

    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(history.format == FORMAT, "unsupported TLB context history format")?;

    let mut generations = Vec::new();
    for (index, operation) in history.operations.iter().enumerate() {
        require(
            operation.ordinal() == index as u64 + 1,
            "noncontiguous TLB context source ordinals",
        )?;
        require(
            operation.pc().0.is_multiple_of(4),
            "unaligned TLB context source PC",
        )?;

        match operation {
            Operation::Mtc0EntryHi {
                ordinal,
                pc,
                word,
                gpr,
                post_asid,
            } => {
                require(
                    word & MTC0_ENTRYHI_MASK == MTC0_ENTRYHI_VALUE,
                    "forged MTC0 EntryHi source opcode",
                )?;
                require(gpr[0] == 0, "invalid captured CPU register zero")?;
                let rt = ((word >> 16) & 31) as usize;
                require(
                    (gpr[rt] & 0xff) as u8 == *post_asid,
                    "MTC0 EntryHi ASID does not match captured source register",
                )?;
                let generation = generations.len() as u64 + 1;
                generations.push(TranslationContextGeneration {
                    generation,
                    source_ordinal: *ordinal,
                    pc: *pc,
                    writer: ContextWriterKind::Mtc0EntryHi,
                    asid: *post_asid,
                    selected_entry_index: None,
                    selected_entry_generation: None,
                });
            }
            Operation::Tlbr {
                ordinal,
                pc,
                word,
                index,
                pre_asid,
                post_asid,
                selected,
            } => {
                require(*word == TLBR_WORD, "forged TLBR source opcode")?;
                if let Some(entry) = selected {
                    require(
                        entry.index == *index && entry.generation != 0,
                        "TLBR selected-entry identity mismatch",
                    )?;
                    require(
                        entry.asid == *post_asid,
                        "TLBR loaded ASID does not match selected entry",
                    )?;
                    let generation = generations.len() as u64 + 1;
                    generations.push(TranslationContextGeneration {
                        generation,
                        source_ordinal: *ordinal,
                        pc: *pc,
                        writer: ContextWriterKind::Tlbr,
                        asid: *post_asid,
                        selected_entry_index: Some(entry.index),
                        selected_entry_generation: Some(entry.generation),
                    });
                } else {
                    require(
                        pre_asid == post_asid,
                        "TLBR without a successful selected entry changed context",
                    )?;
                }
            }
            Operation::Tlbp {
                word,
                pre_asid,
                post_asid,
                ..
            } => {
                require(*word == TLBP_WORD, "forged TLBP source opcode")?;
                require(
                    pre_asid == post_asid,
                    "TLBP unexpectedly changed translation context",
                )?;
            }
        }
    }

    Ok(TranslationContextReport {
        format: REPORT_FORMAT.into(),
        source_sha256: digest,
        operations: history.operations.len(),
        active_generation: generations.last().map(|generation| generation.generation),
        generations,
        source_receipt_verified: true,
        sensor_coverage_certified: false,
        installed_mapping_history_certified: false,
        resident_cache_history_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mtc0(ordinal: u64, asid: u8) -> Operation {
        let word = 0x4088_5000;
        let mut gpr = [0_u64; 32];
        gpr[8] = u64::from(asid);
        Operation::Mtc0EntryHi {
            ordinal,
            pc: GuestVirtualAddr(0x8000_1000 + ordinal * 4),
            word,
            gpr,
            post_asid: asid,
        }
    }

    fn tlbr(
        ordinal: u64,
        index: u32,
        pre_asid: u8,
        post_asid: u8,
        selected: Option<SelectedEntry>,
    ) -> Operation {
        Operation::Tlbr {
            ordinal,
            pc: GuestVirtualAddr(0x8000_2000 + ordinal * 4),
            word: TLBR_WORD,
            index,
            pre_asid,
            post_asid,
            selected,
        }
    }

    fn tlbp(ordinal: u64, asid: u8) -> Operation {
        Operation::Tlbp {
            ordinal,
            pc: GuestVirtualAddr(0x8000_3000 + ordinal * 4),
            word: TLBP_WORD,
            pre_asid: asid,
            post_asid: asid,
        }
    }

    fn inspect(operations: Vec<Operation>) -> Result<TranslationContextReport, String> {
        let source = serde_json::to_vec(&History {
            format: FORMAT.into(),
            operations,
        })
        .expect("serialize test history");
        let digest = sha256(&source);
        inspect_tlb_context_history(&source, &digest)
    }

    #[test]
    fn same_value_entryhi_writes_mint_fresh_generations() {
        let report = inspect(vec![mtc0(1, 0x22), mtc0(2, 0x22)]).unwrap();
        assert_eq!(report.generations.len(), 2);
        assert_eq!(report.generations[0].generation, 1);
        assert_eq!(report.generations[1].generation, 2);
        assert_eq!(report.generations[0].asid, report.generations[1].asid);
        assert!(!report.sensor_coverage_certified);
        assert!(!report.executable_lifetime_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn same_value_successful_tlbr_is_a_context_generation_but_tlbp_is_not() {
        let report = inspect(vec![
            mtc0(1, 0x11),
            tlbp(2, 0x11),
            tlbr(
                3,
                7,
                0x11,
                0x11,
                Some(SelectedEntry {
                    index: 7,
                    generation: 41,
                    asid: 0x11,
                }),
            ),
        ])
        .unwrap();
        assert_eq!(report.generations.len(), 2);
        let loaded = &report.generations[1];
        assert_eq!(loaded.writer, ContextWriterKind::Tlbr);
        assert_eq!(loaded.selected_entry_index, Some(7));
        assert_eq!(loaded.selected_entry_generation, Some(41));
    }

    #[test]
    fn repeated_tlbr_of_same_entry_still_mints_distinct_context_generations() {
        let selected = SelectedEntry {
            index: 3,
            generation: 9,
            asid: 0x33,
        };
        let report = inspect(vec![
            tlbr(1, 3, 0x22, 0x33, Some(selected.clone())),
            tlbr(2, 3, 0x33, 0x33, Some(selected)),
        ])
        .unwrap();
        assert_eq!(report.generations.len(), 2);
        assert_eq!(report.generations[0].selected_entry_generation, Some(9));
        assert_eq!(report.generations[1].selected_entry_generation, Some(9));
        assert_ne!(report.generations[0].generation, report.generations[1].generation);
    }

    #[test]
    fn unsuccessful_tlbr_does_not_fabricate_a_generation() {
        let report = inspect(vec![mtc0(1, 0x44), tlbr(2, 63, 0x44, 0x44, None)]).unwrap();
        assert_eq!(report.generations.len(), 1);
        assert_eq!(report.active_generation, Some(1));
    }

    #[test]
    fn selected_entry_identity_is_required_for_successful_tlbr() {
        let error = inspect(vec![tlbr(
            1,
            5,
            0x11,
            0x22,
            Some(SelectedEntry {
                index: 6,
                generation: 8,
                asid: 0x22,
            }),
        )])
        .unwrap_err();
        assert!(error.contains("selected-entry identity"));
    }

    #[test]
    fn no_selected_entry_cannot_hide_a_context_change() {
        let error = inspect(vec![tlbr(1, 63, 0x11, 0x22, None)]).unwrap_err();
        assert!(error.contains("changed context"));
    }

    #[test]
    fn forged_mtc0_opcode_is_rejected() {
        let mut operation = mtc0(1, 0x11);
        let Operation::Mtc0EntryHi { word, .. } = &mut operation else {
            unreachable!();
        };
        *word = 0x4088_6000;
        let error = inspect(vec![operation]).unwrap_err();
        assert!(error.contains("forged MTC0 EntryHi"));
    }

    #[test]
    fn mtc0_asid_must_match_captured_source_register() {
        let mut operation = mtc0(1, 0x11);
        let Operation::Mtc0EntryHi { gpr, .. } = &mut operation else {
            unreachable!();
        };
        gpr[8] = 0x22;
        let error = inspect(vec![operation]).unwrap_err();
        assert!(error.contains("captured source register"));
    }

    #[test]
    fn missing_or_reordered_source_ordinals_remain_unknown() {
        let error = inspect(vec![mtc0(1, 0x11), mtc0(3, 0x22)]).unwrap_err();
        assert!(error.contains("noncontiguous"));

        let error = inspect(vec![mtc0(2, 0x22), mtc0(1, 0x11)]).unwrap_err();
        assert!(error.contains("noncontiguous"));
    }

    #[test]
    fn complete_source_receipt_mismatch_is_rejected() {
        let source = serde_json::to_vec(&History {
            format: FORMAT.into(),
            operations: vec![mtc0(1, 0x11)],
        })
        .unwrap();
        let error = inspect_tlb_context_history(&source, &"0".repeat(64)).unwrap_err();
        assert!(error.contains("source receipt mismatch"));
    }
}
