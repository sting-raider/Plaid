use plaid_core::cpu_sp_conditional::{
    CompletedCpuSpWordEffect, ScExecutionContext, verify_sc_sp_effect,
};
use plaid_core::program::{GuestVirtualAddr, PhysicalAddr};

fn fixture() -> (ScExecutionContext, CompletedCpuSpWordEffect) {
    let mut gpr = [0; 32];
    gpr[1] = 0xffff_ffff_a400_0000;
    gpr[2] = 0x1122_3344;
    let context = ScExecutionContext {
        context_id: 1,
        pc: GuestVirtualAddr(0xffff_ffff_a000_6000),
        instruction_word: (0x38 << 26) | (1 << 21) | (2 << 16),
        gpr_before: gpr,
    };
    let effect = CompletedCpuSpWordEffect {
        effect_ordinal: 2,
        context_id: 1,
        pc: context.pc,
        virtual_destination: GuestVirtualAddr(gpr[1]),
        physical_destination: PhysicalAddr(0x0400_0000),
        value: gpr[2] as u32,
    };
    (context, effect)
}

#[test]
fn cpu_sp_conditional_rejects_consistent_impossible_register_zero_snapshot() {
    let (mut context, mut effect) = fixture();
    context.instruction_word &= !(31 << 16);
    context.gpr_before[0] = u64::from(effect.value);
    assert!(verify_sc_sp_effect(&context, Some(&effect)).is_err());
    context.gpr_before[0] = 0;
    effect.value = 0;
    assert!(
        verify_sc_sp_effect(&context, Some(&effect))
            .unwrap()
            .is_some()
    );
}

#[test]
fn cpu_sp_conditional_rejects_matching_unaligned_pc_and_effect_before_context() {
    let (mut context, mut effect) = fixture();
    context.pc.0 += 1;
    effect.pc = context.pc;
    assert!(verify_sc_sp_effect(&context, Some(&effect)).is_err());
    context.pc.0 -= 1;
    effect.pc = context.pc;
    effect.effect_ordinal = context.context_id;
    assert!(verify_sc_sp_effect(&context, Some(&effect)).is_err());
}
