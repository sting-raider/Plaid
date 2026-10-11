//! Decoded-context-bound CPU SB/SH attribution for completed CPU-visible SP Word sinks.
//!
//! The validated SP-memory path does not preserve the nominal one/two-byte ISA
//! width: successful CPU SB/SH transactions can become one complete aligned
//! 32-bit SP-memory sink and the sink value is derived from the unmasked low
//! 32 bits of `rt`. This module therefore verifies an independently observed
//! completed SP Word effect. It never creates a writer from opcode execution,
//! equal bytes, current SP memory, or address equality alone.
//!
//! Physical translation before the reverse-endian lane transform is supplied by
//! an independent mapping witness. This verifier does not reconstruct TLB state,
//! authenticate that witness, prove the lower observer complete, or establish
//! ultimate GPR ancestry, executable lifetime, mutation census, or closure.

use crate::program::{GuestVirtualAddr, PhysicalAddr};
use serde::{Deserialize, Serialize};

const SP_BASE: u32 = 0x0400_0000;
const SP_LIMIT: u32 = 0x0400_2000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CpuSpSubwordKind {
    Sb,
    Sh,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DecodedCpuSpSubwordStore {
    pub kind: CpuSpSubwordKind,
    pub base_register: u8,
    pub source_register: u8,
    pub immediate: i16,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CpuSpBank {
    Dmem,
    Imem,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuSpSubwordContext {
    /// Fresh identity from the authenticated decoded-instruction event stream.
    pub context_ordinal: u64,
    pub pc: GuestVirtualAddr,
    pub instruction_word: u32,
    /// Pre-store architectural GPR snapshot for this exact decoded context.
    pub gpr: [u64; 32],
    /// VR4300 reverse-endian address-lane mode for this exact context.
    pub reverse_endian: bool,
}

/// One independently observed completed CPU-originated SP Word sink.
///
/// `virtual_destination` is the CPU address seen by the lower store path.
/// `translated_physical` is the physical SP-memory address before the CPU's
/// reverse-endian subword lane XOR. The remaining fields describe the completed
/// normalized SP Word transaction after that lane transform. `effect_ordinal`
/// and `producer_context` use the same authenticated ordered event namespace as
/// `CpuSpSubwordContext::context_ordinal`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CompletedCpuSpWordEffect {
    pub effect_ordinal: u64,
    pub producer_context: u64,
    pub virtual_destination: GuestVirtualAddr,
    pub translated_physical: PhysicalAddr,
    pub sink_word_address: PhysicalAddr,
    pub bank: CpuSpBank,
    pub offset: u32,
    pub value: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuSpSubwordMutationWitness {
    pub context_ordinal: u64,
    pub effect_ordinal: u64,
    pub pc: GuestVirtualAddr,
    pub kind: CpuSpSubwordKind,
    pub base_register: u8,
    pub source_register: u8,
    pub virtual_destination: GuestVirtualAddr,
    pub translated_physical: PhysicalAddr,
    pub device_physical: PhysicalAddr,
    pub sink_word_address: PhysicalAddr,
    pub bank: CpuSpBank,
    pub offset: u32,
    /// Exact low 32 source bits consumed by the validated SP adapter rule.
    pub source_u32: u32,
    pub value: u32,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

/// Decode only the integer subword store families covered by this contract.
pub fn decode_cpu_sp_subword_store(word: u32) -> Option<DecodedCpuSpSubwordStore> {
    let kind = match word >> 26 {
        0x28 => CpuSpSubwordKind::Sb,
        0x29 => CpuSpSubwordKind::Sh,
        _ => return None,
    };
    Some(DecodedCpuSpSubwordStore {
        kind,
        base_register: ((word >> 21) & 31) as u8,
        source_register: ((word >> 16) & 31) as u8,
        immediate: word as i16,
    })
}

fn bank_and_offset(address: u32) -> Option<(CpuSpBank, u32)> {
    if !(SP_BASE..SP_LIMIT).contains(&address) {
        return None;
    }
    let bank = if address & 0x1000 == 0 {
        CpuSpBank::Dmem
    } else {
        CpuSpBank::Imem
    };
    Some((bank, address & 0x0ffc))
}

fn expected_sink(
    decoded: DecodedCpuSpSubwordStore,
    translated: PhysicalAddr,
    source_u32: u32,
    reverse_endian: bool,
) -> Result<(PhysicalAddr, PhysicalAddr, CpuSpBank, u32, u32), String> {
    require(
        (SP_BASE..SP_LIMIT).contains(&translated.0),
        "translated CPU subword target outside bounded SP memory",
    )?;

    let lane_xor = if reverse_endian {
        match decoded.kind {
            CpuSpSubwordKind::Sb => 7,
            CpuSpSubwordKind::Sh => 6,
        }
    } else {
        0
    };
    let device = PhysicalAddr(translated.0 ^ lane_xor);
    let (bank, offset) = bank_and_offset(device.0)
        .ok_or_else(|| "post-endian CPU subword target outside bounded SP memory".to_string())?;
    let sink_word = PhysicalAddr(device.0 & !3);
    let lane = device.0 & 3;
    let shift = match decoded.kind {
        CpuSpSubwordKind::Sb => (3 - lane) * 8,
        CpuSpSubwordKind::Sh => {
            require(lane == 0 || lane == 2, "invalid aligned SH SP sink lane")?;
            if lane == 0 { 16 } else { 0 }
        }
    };
    let value = source_u32 << shift;
    Ok((device, sink_word, bank, offset, value))
}

/// Verify one completed CPU SB/SH -> SP Word effect against its exact decoded
/// execution context.
///
/// `None` means no completed sink was observed, so no mutation witness is minted.
/// This is also the required result for faulting/aborted attempts. The caller must
/// separately authenticate mapping provenance, the ordered context/effect stream,
/// GPR ancestry, and completeness of all relevant writers.
pub fn verify_cpu_sp_subword_effect(
    context: &CpuSpSubwordContext,
    effect: Option<&CompletedCpuSpWordEffect>,
) -> Result<Option<CpuSpSubwordMutationWitness>, String> {
    let decoded = decode_cpu_sp_subword_store(context.instruction_word)
        .ok_or("not a supported CPU SP subword store")?;
    require(
        context.context_ordinal != 0,
        "invalid CPU SP decoded context ordinal",
    )?;
    require(context.gpr[0] == 0, "nonzero architectural zero register")?;
    require(
        context.pc.0.is_multiple_of(4),
        "misaligned CPU instruction PC",
    )?;

    let virtual_destination = GuestVirtualAddr(
        context.gpr[usize::from(decoded.base_register)]
            .wrapping_add_signed(i64::from(decoded.immediate)),
    );
    let faulting_alignment =
        decoded.kind == CpuSpSubwordKind::Sh && !virtual_destination.0.is_multiple_of(2);

    let Some(effect) = effect else {
        return Ok(None);
    };
    require(
        !faulting_alignment,
        "completed CPU SP effect for faulting misaligned SH",
    )?;
    require(effect.effect_ordinal != 0, "invalid CPU SP effect ordinal")?;
    require(
        effect.producer_context == context.context_ordinal,
        "CPU SP effect producer-context mismatch",
    )?;
    require(
        effect.effect_ordinal > context.context_ordinal,
        "CPU SP effect precedes decoded producer context",
    )?;
    require(
        effect.virtual_destination == virtual_destination,
        "CPU SP virtual destination mismatch",
    )?;

    let source_u32 = context.gpr[usize::from(decoded.source_register)] as u32;
    let (device, sink_word, bank, offset, value) = expected_sink(
        decoded,
        effect.translated_physical,
        source_u32,
        context.reverse_endian,
    )?;

    require(
        effect.sink_word_address == sink_word,
        "CPU SP completed Word address mismatch",
    )?;
    require(effect.bank == bank, "CPU SP completed bank mismatch")?;
    require(effect.offset == offset, "CPU SP completed offset mismatch")?;
    require(
        effect.value == value,
        "CPU SP completed payload/source mismatch",
    )?;

    Ok(Some(CpuSpSubwordMutationWitness {
        context_ordinal: context.context_ordinal,
        effect_ordinal: effect.effect_ordinal,
        pc: context.pc,
        kind: decoded.kind,
        base_register: decoded.base_register,
        source_register: decoded.source_register,
        virtual_destination,
        translated_physical: effect.translated_physical,
        device_physical: device,
        sink_word_address: sink_word,
        bank,
        offset,
        source_u32,
        value,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn encode(kind: CpuSpSubwordKind, base: u8, source: u8, immediate: i16) -> u32 {
        let opcode = match kind {
            CpuSpSubwordKind::Sb => 0x28,
            CpuSpSubwordKind::Sh => 0x29,
        };
        (opcode << 26)
            | (u32::from(base) << 21)
            | (u32::from(source) << 16)
            | u32::from(immediate as u16)
    }

    fn context(
        kind: CpuSpSubwordKind,
        immediate: i16,
        reverse_endian: bool,
    ) -> CpuSpSubwordContext {
        let mut gpr = [0; 32];
        gpr[1] = 0xffff_ffff_a400_1000;
        gpr[2] = 0x1122_3344_5566_7788;
        CpuSpSubwordContext {
            context_ordinal: 11,
            pc: GuestVirtualAddr(0xffff_ffff_8000_1000),
            instruction_word: encode(kind, 1, 2, immediate),
            gpr,
            reverse_endian,
        }
    }

    fn effect(
        producer_context: u64,
        virtual_destination: u64,
        translated: u32,
        sink: u32,
        bank: CpuSpBank,
        offset: u32,
        value: u32,
    ) -> CompletedCpuSpWordEffect {
        CompletedCpuSpWordEffect {
            effect_ordinal: 17,
            producer_context,
            virtual_destination: GuestVirtualAddr(virtual_destination),
            translated_physical: PhysicalAddr(translated),
            sink_word_address: PhysicalAddr(sink),
            bank,
            offset,
            value,
        }
    }

    #[test]
    fn sb_plus_one_uses_unmasked_source_and_full_word_sink() {
        let ctx = context(CpuSpSubwordKind::Sb, 1, false);
        let observed = effect(
            11,
            0xffff_ffff_a400_1001,
            0x0400_1001,
            0x0400_1000,
            CpuSpBank::Imem,
            0,
            0x7788_0000,
        );
        let witness = verify_cpu_sp_subword_effect(&ctx, Some(&observed))
            .unwrap()
            .unwrap();
        assert_eq!(witness.source_register, 2);
        assert_eq!(witness.source_u32, 0x5566_7788);
        assert_eq!(witness.value, 0x7788_0000);
        assert_eq!(witness.sink_word_address, PhysicalAddr(0x0400_1000));
    }

    #[test]
    fn sh_lane_two_replaces_complete_word() {
        let ctx = context(CpuSpSubwordKind::Sh, 2, false);
        let observed = effect(
            11,
            0xffff_ffff_a400_1002,
            0x0400_1002,
            0x0400_1000,
            CpuSpBank::Imem,
            0,
            0x5566_7788,
        );
        let witness = verify_cpu_sp_subword_effect(&ctx, Some(&observed))
            .unwrap()
            .unwrap();
        assert_eq!(witness.value, 0x5566_7788);
    }

    #[test]
    fn reverse_endian_address_lane_is_part_of_identity() {
        let ctx = context(CpuSpSubwordKind::Sb, 0, true);
        let observed = effect(
            11,
            0xffff_ffff_a400_1000,
            0x0400_1000,
            0x0400_1004,
            CpuSpBank::Imem,
            4,
            0x5566_7788,
        );
        let witness = verify_cpu_sp_subword_effect(&ctx, Some(&observed))
            .unwrap()
            .unwrap();
        assert_eq!(witness.device_physical, PhysicalAddr(0x0400_1007));
        assert_eq!(witness.offset, 4);
    }

    #[test]
    fn nominal_byte_mask_payload_is_rejected() {
        let ctx = context(CpuSpSubwordKind::Sb, 1, false);
        let forged = effect(
            11,
            0xffff_ffff_a400_1001,
            0x0400_1001,
            0x0400_1000,
            CpuSpBank::Imem,
            0,
            0x0088_0000,
        );
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, Some(&forged)).unwrap_err(),
            "CPU SP completed payload/source mismatch"
        );
    }

    #[test]
    fn same_value_effect_cannot_borrow_another_context() {
        let ctx = context(CpuSpSubwordKind::Sb, 3, false);
        let forged = effect(
            12,
            0xffff_ffff_a400_1003,
            0x0400_1003,
            0x0400_1000,
            CpuSpBank::Imem,
            0,
            0x5566_7788,
        );
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, Some(&forged)).unwrap_err(),
            "CPU SP effect producer-context mismatch"
        );
    }

    #[test]
    fn reordered_effect_is_rejected() {
        let ctx = context(CpuSpSubwordKind::Sb, 3, false);
        let mut forged = effect(
            11,
            0xffff_ffff_a400_1003,
            0x0400_1003,
            0x0400_1000,
            CpuSpBank::Imem,
            0,
            0x5566_7788,
        );
        forged.effect_ordinal = 10;
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, Some(&forged)).unwrap_err(),
            "CPU SP effect precedes decoded producer context"
        );
    }

    #[test]
    fn virtual_destination_forgery_is_rejected() {
        let ctx = context(CpuSpSubwordKind::Sb, 3, false);
        let forged = effect(
            11,
            0xffff_ffff_a400_1103,
            0x0400_1003,
            0x0400_1000,
            CpuSpBank::Imem,
            0,
            0x5566_7788,
        );
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, Some(&forged)).unwrap_err(),
            "CPU SP virtual destination mismatch"
        );
    }

    #[test]
    fn bank_label_forgery_is_rejected() {
        let ctx = context(CpuSpSubwordKind::Sb, 3, false);
        let forged = effect(
            11,
            0xffff_ffff_a400_1003,
            0x0400_1003,
            0x0400_1000,
            CpuSpBank::Dmem,
            0,
            0x5566_7788,
        );
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, Some(&forged)).unwrap_err(),
            "CPU SP completed bank mismatch"
        );
    }

    #[test]
    fn offset_forgery_is_rejected() {
        let ctx = context(CpuSpSubwordKind::Sb, 3, false);
        let forged = effect(
            11,
            0xffff_ffff_a400_1003,
            0x0400_1003,
            0x0400_1000,
            CpuSpBank::Imem,
            0x1000,
            0x5566_7788,
        );
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, Some(&forged)).unwrap_err(),
            "CPU SP completed offset mismatch"
        );
    }

    #[test]
    fn sink_address_forgery_is_rejected() {
        let ctx = context(CpuSpSubwordKind::Sb, 3, false);
        let forged = effect(
            11,
            0xffff_ffff_a400_1003,
            0x0400_1003,
            0x0400_1004,
            CpuSpBank::Imem,
            0,
            0x5566_7788,
        );
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, Some(&forged)).unwrap_err(),
            "CPU SP completed Word address mismatch"
        );
    }

    #[test]
    fn faulting_sh_mints_no_writer_and_rejects_forged_effect() {
        let ctx = context(CpuSpSubwordKind::Sh, 1, false);
        assert_eq!(verify_cpu_sp_subword_effect(&ctx, None).unwrap(), None);
        let forged = effect(
            11,
            0xffff_ffff_a400_1001,
            0x0400_1001,
            0x0400_1000,
            CpuSpBank::Imem,
            0,
            0x7788_0000,
        );
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, Some(&forged)).unwrap_err(),
            "completed CPU SP effect for faulting misaligned SH"
        );
    }

    #[test]
    fn absent_aligned_effect_mints_no_writer() {
        let ctx = context(CpuSpSubwordKind::Sb, 0, false);
        assert_eq!(verify_cpu_sp_subword_effect(&ctx, None).unwrap(), None);
    }

    #[test]
    fn same_payload_successes_keep_distinct_generations() {
        let first_ctx = context(CpuSpSubwordKind::Sb, 3, false);
        let mut second_ctx = first_ctx.clone();
        second_ctx.context_ordinal = 12;
        let first = effect(
            11,
            0xffff_ffff_a400_1003,
            0x0400_1003,
            0x0400_1000,
            CpuSpBank::Imem,
            0,
            0x5566_7788,
        );
        let mut second = effect(
            12,
            0xffff_ffff_a400_1003,
            0x0400_1003,
            0x0400_1000,
            CpuSpBank::Imem,
            0,
            0x5566_7788,
        );
        second.effect_ordinal = 18;
        let first = verify_cpu_sp_subword_effect(&first_ctx, Some(&first))
            .unwrap()
            .unwrap();
        let second = verify_cpu_sp_subword_effect(&second_ctx, Some(&second))
            .unwrap()
            .unwrap();
        assert_eq!(first.value, second.value);
        assert_ne!(first.context_ordinal, second.context_ordinal);
        assert_ne!(first.effect_ordinal, second.effect_ordinal);
    }

    #[test]
    fn translated_target_outside_bounded_sp_memory_is_rejected() {
        let ctx = context(CpuSpSubwordKind::Sb, 0, false);
        let forged = effect(
            11,
            0xffff_ffff_a400_1000,
            0x03ff_ffff,
            0x03ff_fffc,
            CpuSpBank::Dmem,
            0xffc,
            0x8800_0000,
        );
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, Some(&forged)).unwrap_err(),
            "translated CPU subword target outside bounded SP memory"
        );
    }

    #[test]
    fn zero_generation_identities_are_rejected() {
        let mut ctx = context(CpuSpSubwordKind::Sb, 0, false);
        ctx.context_ordinal = 0;
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, None).unwrap_err(),
            "invalid CPU SP decoded context ordinal"
        );

        let ctx = context(CpuSpSubwordKind::Sb, 0, false);
        let mut observed = effect(
            11,
            0xffff_ffff_a400_1000,
            0x0400_1000,
            0x0400_1000,
            CpuSpBank::Imem,
            0,
            0x8800_0000,
        );
        observed.effect_ordinal = 0;
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, Some(&observed)).unwrap_err(),
            "invalid CPU SP effect ordinal"
        );
    }

    #[test]
    fn non_subword_store_is_rejected() {
        let mut ctx = context(CpuSpSubwordKind::Sb, 0, false);
        ctx.instruction_word = 0xac22_0000; // SW r2,0(r1)
        assert_eq!(
            verify_cpu_sp_subword_effect(&ctx, None).unwrap_err(),
            "not a supported CPU SP subword store"
        );
    }

    #[test]
    fn decode_preserves_source_and_immediate() {
        let decoded =
            decode_cpu_sp_subword_store(encode(CpuSpSubwordKind::Sh, 5, 17, -12)).unwrap();
        assert_eq!(decoded.kind, CpuSpSubwordKind::Sh);
        assert_eq!(decoded.base_register, 5);
        assert_eq!(decoded.source_register, 17);
        assert_eq!(decoded.immediate, -12);
    }
}
