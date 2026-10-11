//! Bounded normalization of completed VR4300 Word `SC` mutations to CPU-visible
//! SP DMEM/IMEM.
//!
//! This verifier is effect-driven. A decoded `SC` is an attempt, not a writer.
//! A mutation witness exists only when an independently observed completed SP
//! Word sink is causally joined to that exact execution context. In particular,
//! unchanged destination bytes do not erase a completed writer generation.
//!
//! LL/SC reservation creation, invalidation, address matching and lifetime are
//! deliberately outside this module. The verifier never predicts conditional
//! success from `llbit`, the opcode, or a result register.
use crate::program::{GuestVirtualAddr, PhysicalAddr};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DecodedSc {
    pub base_register: u8,
    pub source_register: u8,
    pub immediate: i16,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ScExecutionContext {
    /// Identity assigned by the complete instruction-context observer.
    pub context_id: u64,
    pub pc: GuestVirtualAddr,
    pub instruction_word: u32,
    /// Architectural GPR values immediately before this instruction executes.
    pub gpr_before: [u64; 32],
}

/// One independently observed completed CPU-origin SP Word sink.
///
/// This is a concrete device-storage effect, not an opcode prediction or a
/// before/after diff. `context_id` and `pc` bind the sink to the instruction
/// context that was active when the lower observer reported completion.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CompletedCpuSpWordEffect {
    pub effect_ordinal: u64,
    pub context_id: u64,
    pub pc: GuestVirtualAddr,
    pub virtual_destination: GuestVirtualAddr,
    pub physical_destination: PhysicalAddr,
    pub value: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ScSpMutationWitness {
    pub effect_ordinal: u64,
    pub context_id: u64,
    pub pc: GuestVirtualAddr,
    pub source_register: u8,
    pub source_value_before: u64,
    pub virtual_destination: GuestVirtualAddr,
    pub physical_destination: PhysicalAddr,
    pub bank: u8,
    pub offset: u16,
    pub value: u32,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

/// Decode only the Word `SC` instruction covered by the validated contract.
pub fn decode_sc(word: u32) -> Option<DecodedSc> {
    if word >> 26 != 0x38 {
        return None;
    }
    Some(DecodedSc {
        base_register: ((word >> 21) & 31) as u8,
        source_register: ((word >> 16) & 31) as u8,
        immediate: word as i16,
    })
}

fn direct_uncached_physical(vaddr: GuestVirtualAddr) -> Option<PhysicalAddr> {
    (0xffff_ffff_a000_0000..=0xffff_ffff_bfff_ffff)
        .contains(&vaddr.0)
        .then_some(PhysicalAddr((vaddr.0 & 0x1fff_ffff) as u32))
}

fn sp_bank_offset(physical: PhysicalAddr) -> Option<(u8, u16)> {
    let relative = physical.0.checked_sub(0x0400_0000)?;
    if relative >= 0x2000 || !relative.is_multiple_of(4) {
        return None;
    }
    Some(((relative >> 12) as u8, (relative & 0x0ffc) as u16))
}

/// Verify one completed Word `SC` -> SP effect against its captured pre-state.
///
/// `None` means no completed sink was observed, so this function creates no
/// writer. That is the correct representation for a failed/faulting attempt in
/// a source whose lower-effect observation is independently known complete.
/// Absence here is not itself a sensor-completeness proof.
///
/// The accepted scope is intentionally narrow: aligned, uncached direct-segment
/// CPU accesses to the 8 KiB DMEM/IMEM backing window. Cached/TLB/reverse-endian
/// aliases and all reservation-policy reasoning remain separate obligations.
pub fn verify_sc_sp_effect(
    context: &ScExecutionContext,
    effect: Option<&CompletedCpuSpWordEffect>,
) -> Result<Option<ScSpMutationWitness>, String> {
    let decoded = decode_sc(context.instruction_word).ok_or("not a Word SC instruction")?;
    require(
        context.context_id != 0,
        "invalid SC execution context identity",
    )?;

    let Some(effect) = effect else {
        return Ok(None);
    };

    require(effect.effect_ordinal != 0, "invalid SC effect ordinal")?;
    require(
        effect.context_id == context.context_id && effect.pc == context.pc,
        "completed SP sink is not bound to this SC execution context",
    )?;

    let base = context.gpr_before[usize::from(decoded.base_register)];
    let source = context.gpr_before[usize::from(decoded.source_register)];
    let expected_virtual = GuestVirtualAddr(base.wrapping_add_signed(i64::from(decoded.immediate)));
    require(
        expected_virtual.0.is_multiple_of(4),
        "completed SC sink has a misaligned virtual destination",
    )?;
    require(
        effect.virtual_destination == expected_virtual,
        "SC virtual destination mismatch",
    )?;

    let expected_physical = direct_uncached_physical(expected_virtual)
        .ok_or("SC destination is outside the bounded uncached direct segment")?;
    require(
        effect.physical_destination == expected_physical,
        "SC physical destination does not match direct mapping",
    )?;
    let (bank, offset) = sp_bank_offset(expected_physical)
        .ok_or("SC completed effect is outside bounded SP DMEM/IMEM")?;

    let expected_value = source as u32;
    require(
        effect.value == expected_value,
        "SC completed sink payload does not match pre-instruction source register",
    )?;

    Ok(Some(ScSpMutationWitness {
        effect_ordinal: effect.effect_ordinal,
        context_id: context.context_id,
        pc: context.pc,
        source_register: decoded.source_register,
        source_value_before: source,
        virtual_destination: expected_virtual,
        physical_destination: expected_physical,
        bank,
        offset,
        value: expected_value,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn encode_sc(base: u8, rt: u8, immediate: i16) -> u32 {
        (0x38 << 26) | (u32::from(base) << 21) | (u32::from(rt) << 16) | u32::from(immediate as u16)
    }

    fn context(immediate: i16, source: u64) -> ScExecutionContext {
        let mut gpr = [0u64; 32];
        gpr[1] = 0xffff_ffff_a400_0000;
        gpr[2] = source;
        ScExecutionContext {
            context_id: 41,
            pc: GuestVirtualAddr(0xffff_ffff_a000_6000),
            instruction_word: encode_sc(1, 2, immediate),
            gpr_before: gpr,
        }
    }

    fn effect(
        context: &ScExecutionContext,
        virtual_destination: u64,
        physical_destination: u32,
        value: u32,
    ) -> CompletedCpuSpWordEffect {
        CompletedCpuSpWordEffect {
            effect_ordinal: 77,
            context_id: context.context_id,
            pc: context.pc,
            virtual_destination: GuestVirtualAddr(virtual_destination),
            physical_destination: PhysicalAddr(physical_destination),
            value,
        }
    }

    #[test]
    fn completed_dmem_and_imem_sinks_create_distinct_witnesses() {
        let dmem = context(0, 0x5566_7788_1122_33bb);
        let dmem_effect = effect(&dmem, 0xffff_ffff_a400_0000, 0x0400_0000, 0x1122_33bb);
        let dmem_witness = verify_sc_sp_effect(&dmem, Some(&dmem_effect))
            .unwrap()
            .unwrap();
        assert_eq!((dmem_witness.bank, dmem_witness.offset), (0, 0));
        assert_eq!(dmem_witness.source_value_before, 0x5566_7788_1122_33bb);

        let imem = context(0x1000, 0xaaaa_bbbb_1122_3344);
        let imem_effect = effect(&imem, 0xffff_ffff_a400_1000, 0x0400_1000, 0x1122_3344);
        let imem_witness = verify_sc_sp_effect(&imem, Some(&imem_effect))
            .unwrap()
            .unwrap();
        assert_eq!((imem_witness.bank, imem_witness.offset), (1, 0));
    }

    #[test]
    fn same_value_completed_sink_is_still_a_writer() {
        let context = context(0, 0x1122_3344);
        // No prior-value comparison participates in writer creation. A lower
        // observer reported that the sink completed, so equal bytes do not erase it.
        let effect = effect(&context, 0xffff_ffff_a400_0000, 0x0400_0000, 0x1122_3344);
        assert!(
            verify_sc_sp_effect(&context, Some(&effect))
                .unwrap()
                .is_some()
        );
    }

    #[test]
    fn absent_completed_sink_creates_no_writer() {
        let context = context(0, 0x1122_3344);
        assert_eq!(verify_sc_sp_effect(&context, None).unwrap(), None);
    }

    #[test]
    fn equal_value_decoy_from_another_context_is_rejected() {
        let context = context(0, 0x1122_3344);
        let mut decoy = effect(&context, 0xffff_ffff_a400_0000, 0x0400_0000, 0x1122_3344);
        decoy.context_id += 1;
        assert_eq!(
            verify_sc_sp_effect(&context, Some(&decoy)).unwrap_err(),
            "completed SP sink is not bound to this SC execution context"
        );
    }

    #[test]
    fn wrong_opcode_or_source_payload_cannot_steal_sc_provenance() {
        let mut wrong_opcode = context(0, 0x1122_3344);
        wrong_opcode.instruction_word = (0x2b << 26) | (1 << 21) | (2 << 16); // SW
        let sink = effect(
            &wrong_opcode,
            0xffff_ffff_a400_0000,
            0x0400_0000,
            0x1122_3344,
        );
        assert_eq!(
            verify_sc_sp_effect(&wrong_opcode, Some(&sink)).unwrap_err(),
            "not a Word SC instruction"
        );

        let context = context(0, 0x1122_3344);
        let wrong_value = effect(&context, 0xffff_ffff_a400_0000, 0x0400_0000, 0x1122_3345);
        assert_eq!(
            verify_sc_sp_effect(&context, Some(&wrong_value)).unwrap_err(),
            "SC completed sink payload does not match pre-instruction source register"
        );
    }

    #[test]
    fn forged_address_mapping_and_sp_bank_are_rejected() {
        let sc_context = context(0, 0x1122_3344);
        let wrong_physical = effect(&sc_context, 0xffff_ffff_a400_0000, 0x0400_1000, 0x1122_3344);
        assert_eq!(
            verify_sc_sp_effect(&sc_context, Some(&wrong_physical)).unwrap_err(),
            "SC physical destination does not match direct mapping"
        );

        let mut outside_sp = context(0, 0x1122_3344);
        outside_sp.gpr_before[1] = 0xffff_ffff_a000_2000;
        let outside_effect = effect(&outside_sp, 0xffff_ffff_a000_2000, 0x0000_2000, 0x1122_3344);
        assert_eq!(
            verify_sc_sp_effect(&outside_sp, Some(&outside_effect)).unwrap_err(),
            "SC completed effect is outside bounded SP DMEM/IMEM"
        );
    }

    #[test]
    fn cached_or_misaligned_claims_fail_closed() {
        let mut cached = context(0, 0x1122_3344);
        cached.gpr_before[1] = 0xffff_ffff_8400_0000;
        let cached_effect = effect(&cached, 0xffff_ffff_8400_0000, 0x0400_0000, 0x1122_3344);
        assert_eq!(
            verify_sc_sp_effect(&cached, Some(&cached_effect)).unwrap_err(),
            "SC destination is outside the bounded uncached direct segment"
        );

        let misaligned = context(1, 0x1122_3344);
        let misaligned_effect =
            effect(&misaligned, 0xffff_ffff_a400_0001, 0x0400_0001, 0x1122_3344);
        assert_eq!(
            verify_sc_sp_effect(&misaligned, Some(&misaligned_effect)).unwrap_err(),
            "completed SC sink has a misaligned virtual destination"
        );
        assert_eq!(verify_sc_sp_effect(&misaligned, None).unwrap(), None);
    }

    #[test]
    fn base_equal_to_source_uses_pre_instruction_state() {
        let mut gpr = [0u64; 32];
        gpr[2] = 0xffff_ffff_a400_0000;
        let context = ScExecutionContext {
            context_id: 9,
            pc: GuestVirtualAddr(0xffff_ffff_a000_7000),
            instruction_word: encode_sc(2, 2, 0),
            gpr_before: gpr,
        };
        let effect = CompletedCpuSpWordEffect {
            effect_ordinal: 10,
            context_id: 9,
            pc: context.pc,
            virtual_destination: GuestVirtualAddr(0xffff_ffff_a400_0000),
            physical_destination: PhysicalAddr(0x0400_0000),
            value: 0xa400_0000,
        };
        let witness = verify_sc_sp_effect(&context, Some(&effect))
            .unwrap()
            .unwrap();
        assert_eq!(witness.value, 0xa400_0000);
    }

    #[test]
    fn zero_identities_and_wrong_pc_are_rejected() {
        let mut zero_id_context = context(0, 0x1122_3344);
        zero_id_context.context_id = 0;
        assert_eq!(
            verify_sc_sp_effect(&zero_id_context, None).unwrap_err(),
            "invalid SC execution context identity"
        );

        let sc_context = context(0, 0x1122_3344);
        let mut sink = effect(&sc_context, 0xffff_ffff_a400_0000, 0x0400_0000, 0x1122_3344);
        sink.pc = GuestVirtualAddr(sink.pc.0 + 4);
        assert_eq!(
            verify_sc_sp_effect(&sc_context, Some(&sink)).unwrap_err(),
            "completed SP sink is not bound to this SC execution context"
        );
    }
}
