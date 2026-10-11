//! Bounded normalization of completed VR4300 SC/SCD direct storage effects.
//!
//! This module deliberately does not predict LL/SC reservation success. A decoded
//! conditional-store attempt creates no mutation witness unless an independently
//! observed direct storage sink completed. Cached direct effects remain
//! cache-resident; later D-cache writeback is separate provenance.
use crate::cpu_mutation::CpuMutationDomain;
use crate::program::{GuestVirtualAddr, PhysicalAddr};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConditionalStoreKind {
    Sc,
    Scd,
}

impl ConditionalStoreKind {
    fn width(self) -> usize {
        match self {
            Self::Sc => 4,
            Self::Scd => 8,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DecodedConditionalStore {
    pub kind: ConditionalStoreKind,
    pub base_register: u8,
    pub source_register: u8,
    pub immediate: i16,
}

/// A completed direct SC/SCD storage effect supplied by a lower observer.
///
/// `payload` is the semantic guest-order payload of the conditional store.
/// `physical_destination` and `domain` are observed sink facts; this verifier does
/// not reconstruct a TLB mapping or infer cacheability from the virtual address.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CompletedConditionalStoreEffect {
    pub effect_ordinal: u64,
    pub virtual_destination: GuestVirtualAddr,
    pub physical_destination: PhysicalAddr,
    pub domain: CpuMutationDomain,
    pub payload: Vec<u8>,
}

/// Captured architectural source state used only for consistency checking.
///
/// Equal values do not establish register-generation or storage ancestry.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConditionalStoreSource {
    pub register: u8,
    pub value_before: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ConditionalStoreMutationWitness {
    pub effect_ordinal: u64,
    pub kind: ConditionalStoreKind,
    pub source: ConditionalStoreSource,
    pub virtual_destination: GuestVirtualAddr,
    pub physical_destination: PhysicalAddr,
    pub domain: CpuMutationDomain,
    pub payload: Vec<u8>,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

/// Decode only the two conditional-store families covered by the validated contract.
pub fn decode_conditional_store(word: u32) -> Option<DecodedConditionalStore> {
    let kind = match word >> 26 {
        0x38 => ConditionalStoreKind::Sc,
        0x3c => ConditionalStoreKind::Scd,
        _ => return None,
    };
    Some(DecodedConditionalStore {
        kind,
        base_register: ((word >> 21) & 31) as u8,
        source_register: ((word >> 16) & 31) as u8,
        immediate: word as i16,
    })
}

/// Verify one independently observed completed direct SC/SCD effect.
///
/// `gpr_before` must be the architectural GPR snapshot before the instruction;
/// SC/SCD overwrite `rt` with their success result after the attempt, so the
/// post-instruction value is not source provenance. `None` means no completed
/// direct sink was observed and therefore creates no mutation witness.
///
/// The caller must independently authenticate capture completeness, effect
/// ordering, mapping/physical identity and register ancestry. A later D-cache
/// line writeback is not a direct conditional-store effect and must be composed
/// through separate resident-writer lineage.
pub fn verify_conditional_store_effect(
    instruction_word: u32,
    gpr_before: &[u64; 32],
    effect: Option<&CompletedConditionalStoreEffect>,
) -> Result<Option<ConditionalStoreMutationWitness>, String> {
    let decoded =
        decode_conditional_store(instruction_word).ok_or("not a supported conditional store")?;
    let Some(effect) = effect else {
        return Ok(None);
    };

    require(
        effect.effect_ordinal != 0,
        "invalid conditional-store effect ordinal",
    )?;

    let expected_virtual = GuestVirtualAddr(
        gpr_before[usize::from(decoded.base_register)]
            .wrapping_add_signed(i64::from(decoded.immediate)),
    );
    require(
        effect.virtual_destination == expected_virtual,
        "conditional-store virtual destination mismatch",
    )?;

    let width = decoded.kind.width();
    require(
        effect.virtual_destination.0.is_multiple_of(width as u64),
        "completed conditional-store effect is misaligned",
    )?;
    require(
        effect.physical_destination.0.is_multiple_of(width as u32),
        "completed conditional-store physical effect is misaligned",
    )?;
    require(
        u64::from(effect.physical_destination.0) + width as u64 <= 0x0080_0000,
        "conditional-store effect outside bounded RDRAM",
    )?;

    let source_value = gpr_before[usize::from(decoded.source_register)];
    let expected_payload = match decoded.kind {
        ConditionalStoreKind::Sc => (source_value as u32).to_be_bytes().to_vec(),
        ConditionalStoreKind::Scd => source_value.to_be_bytes().to_vec(),
    };
    require(
        effect.payload.len() == width,
        "conditional-store effect width mismatch",
    )?;
    require(
        effect.payload == expected_payload,
        "conditional-store payload/source mismatch",
    )?;

    Ok(Some(ConditionalStoreMutationWitness {
        effect_ordinal: effect.effect_ordinal,
        kind: decoded.kind,
        source: ConditionalStoreSource {
            register: decoded.source_register,
            value_before: source_value,
        },
        virtual_destination: effect.virtual_destination,
        physical_destination: effect.physical_destination,
        domain: effect.domain,
        payload: expected_payload,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn encode(kind: ConditionalStoreKind, base: u8, rt: u8, immediate: i16) -> u32 {
        let opcode = match kind {
            ConditionalStoreKind::Sc => 0x38,
            ConditionalStoreKind::Scd => 0x3c,
        };
        (opcode << 26)
            | (u32::from(base) << 21)
            | (u32::from(rt) << 16)
            | u32::from(immediate as u16)
    }

    fn state() -> [u64; 32] {
        let mut gpr = [0; 32];
        gpr[1] = 0xffff_ffff_a000_2000;
        gpr[9] = 0x1122_3344_5566_7788;
        gpr
    }

    fn effect(
        domain: CpuMutationDomain,
        virtual_destination: u64,
        physical_destination: u32,
        payload: &[u8],
    ) -> CompletedConditionalStoreEffect {
        CompletedConditionalStoreEffect {
            effect_ordinal: 7,
            virtual_destination: GuestVirtualAddr(virtual_destination),
            physical_destination: PhysicalAddr(physical_destination),
            domain,
            payload: payload.to_vec(),
        }
    }

    #[test]
    fn sc_backing_effect_uses_low_word_of_pre_instruction_rt() {
        let gpr = state();
        let witness = verify_conditional_store_effect(
            encode(ConditionalStoreKind::Sc, 1, 9, 0),
            &gpr,
            Some(&effect(
                CpuMutationDomain::Backing,
                0xffff_ffff_a000_2000,
                0x2000,
                &[0x55, 0x66, 0x77, 0x88],
            )),
        )
        .unwrap()
        .unwrap();
        assert_eq!(witness.kind, ConditionalStoreKind::Sc);
        assert_eq!(witness.source.register, 9);
        assert_eq!(witness.source.value_before, 0x1122_3344_5566_7788);
        assert_eq!(witness.payload, [0x55, 0x66, 0x77, 0x88]);
        assert_eq!(witness.domain, CpuMutationDomain::Backing);
    }

    #[test]
    fn scd_cache_resident_effect_uses_full_pre_instruction_rt() {
        let mut gpr = state();
        gpr[1] = 0xffff_ffff_8000_2000;
        let witness = verify_conditional_store_effect(
            encode(ConditionalStoreKind::Scd, 1, 9, 0),
            &gpr,
            Some(&effect(
                CpuMutationDomain::CacheResident,
                0xffff_ffff_8000_2000,
                0x2000,
                &[0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88],
            )),
        )
        .unwrap()
        .unwrap();
        assert_eq!(witness.kind, ConditionalStoreKind::Scd);
        assert_eq!(witness.domain, CpuMutationDomain::CacheResident);
        assert_eq!(witness.payload.len(), 8);
    }

    #[test]
    fn absent_completed_effect_creates_no_writer() {
        let gpr = state();
        assert_eq!(
            verify_conditional_store_effect(encode(ConditionalStoreKind::Sc, 1, 9, 0), &gpr, None,)
                .unwrap(),
            None
        );
    }

    #[test]
    fn architectural_success_flag_cannot_substitute_for_pre_store_payload() {
        let gpr = state();
        let forged = effect(
            CpuMutationDomain::Backing,
            0xffff_ffff_a000_2000,
            0x2000,
            &[0, 0, 0, 1],
        );
        assert_eq!(
            verify_conditional_store_effect(
                encode(ConditionalStoreKind::Sc, 1, 9, 0),
                &gpr,
                Some(&forged),
            )
            .unwrap_err(),
            "conditional-store payload/source mismatch"
        );
    }

    #[test]
    fn same_value_completed_effect_remains_a_first_class_event() {
        let gpr = state();
        let observed = effect(
            CpuMutationDomain::Backing,
            0xffff_ffff_a000_2000,
            0x2000,
            &[0x55, 0x66, 0x77, 0x88],
        );
        let witness = verify_conditional_store_effect(
            encode(ConditionalStoreKind::Sc, 1, 9, 0),
            &gpr,
            Some(&observed),
        )
        .unwrap()
        .unwrap();
        assert_eq!(witness.effect_ordinal, 7);
    }

    #[test]
    fn destination_forgery_is_rejected() {
        let gpr = state();
        let forged = effect(
            CpuMutationDomain::Backing,
            0xffff_ffff_a000_3000,
            0x3000,
            &[0x55, 0x66, 0x77, 0x88],
        );
        assert_eq!(
            verify_conditional_store_effect(
                encode(ConditionalStoreKind::Sc, 1, 9, 0),
                &gpr,
                Some(&forged),
            )
            .unwrap_err(),
            "conditional-store virtual destination mismatch"
        );
    }

    #[test]
    fn completed_misaligned_effect_is_rejected() {
        let mut gpr = state();
        gpr[1] += 1;
        let forged = effect(
            CpuMutationDomain::Backing,
            0xffff_ffff_a000_2001,
            0x2001,
            &[0x55, 0x66, 0x77, 0x88],
        );
        assert_eq!(
            verify_conditional_store_effect(
                encode(ConditionalStoreKind::Sc, 1, 9, 0),
                &gpr,
                Some(&forged),
            )
            .unwrap_err(),
            "completed conditional-store effect is misaligned"
        );
    }

    #[test]
    fn later_cache_line_writeback_is_not_a_direct_sc_effect() {
        let gpr = state();
        let forged = effect(
            CpuMutationDomain::Backing,
            0xffff_ffff_a000_2000,
            0x2000,
            &[0x55, 0x66, 0x77, 0x88, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        );
        assert_eq!(
            verify_conditional_store_effect(
                encode(ConditionalStoreKind::Sc, 1, 9, 0),
                &gpr,
                Some(&forged),
            )
            .unwrap_err(),
            "conditional-store effect width mismatch"
        );
    }

    #[test]
    fn effect_outside_bounded_rdram_is_rejected() {
        let gpr = state();
        let forged = effect(
            CpuMutationDomain::Backing,
            0xffff_ffff_a000_2000,
            0x0080_0000,
            &[0x55, 0x66, 0x77, 0x88],
        );
        assert_eq!(
            verify_conditional_store_effect(
                encode(ConditionalStoreKind::Sc, 1, 9, 0),
                &gpr,
                Some(&forged),
            )
            .unwrap_err(),
            "conditional-store effect outside bounded RDRAM"
        );
    }

    #[test]
    fn zero_effect_ordinal_is_rejected() {
        let gpr = state();
        let mut forged = effect(
            CpuMutationDomain::Backing,
            0xffff_ffff_a000_2000,
            0x2000,
            &[0x55, 0x66, 0x77, 0x88],
        );
        forged.effect_ordinal = 0;
        assert_eq!(
            verify_conditional_store_effect(
                encode(ConditionalStoreKind::Sc, 1, 9, 0),
                &gpr,
                Some(&forged),
            )
            .unwrap_err(),
            "invalid conditional-store effect ordinal"
        );
    }

    #[test]
    fn unsupported_store_opcode_is_rejected() {
        let gpr = state();
        let ordinary_sd = 0x3f_u32 << 26 | 1_u32 << 21 | 9_u32 << 16;
        assert_eq!(
            verify_conditional_store_effect(ordinary_sd, &gpr, None).unwrap_err(),
            "not a supported conditional store"
        );
    }

    #[test]
    fn base_equal_to_rt_uses_the_pre_instruction_snapshot() {
        let mut gpr = [0; 32];
        gpr[9] = 0xffff_ffff_a000_2000;
        let witness = verify_conditional_store_effect(
            encode(ConditionalStoreKind::Sc, 9, 9, 0),
            &gpr,
            Some(&effect(
                CpuMutationDomain::Backing,
                0xffff_ffff_a000_2000,
                0x2000,
                &[0xa0, 0x00, 0x20, 0x00],
            )),
        )
        .unwrap()
        .unwrap();
        assert_eq!(witness.source.value_before, 0xffff_ffff_a000_2000);
        assert_eq!(witness.payload, [0xa0, 0x00, 0x20, 0x00]);
    }
}
