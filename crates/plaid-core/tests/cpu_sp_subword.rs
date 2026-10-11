use plaid_core::{
    cpu_sp_subword::{
        CompletedCpuSpWordEffect, CpuSpBank, CpuSpSubwordContext, verify_cpu_sp_subword_effect,
    },
    program::{GuestVirtualAddr, PhysicalAddr},
};

fn zero_source() -> (CpuSpSubwordContext, CompletedCpuSpWordEffect) {
    let mut gpr = [0; 32];
    gpr[1] = 0xffff_ffff_a400_1000;
    (
        CpuSpSubwordContext {
            context_ordinal: 1,
            pc: GuestVirtualAddr(0xffff_ffff_a000_6000),
            instruction_word: 0xa020_0003,
            gpr,
            reverse_endian: false,
        },
        CompletedCpuSpWordEffect {
            effect_ordinal: 2,
            producer_context: 1,
            virtual_destination: GuestVirtualAddr(0xffff_ffff_a400_1003),
            translated_physical: PhysicalAddr(0x0400_1003),
            sink_word_address: PhysicalAddr(0x0400_1000),
            bank: CpuSpBank::Imem,
            offset: 0,
            value: 0,
        },
    )
}

#[test]
fn architectural_zero_is_not_a_forgeable_producer() {
    let (mut context, mut effect) = zero_source();
    assert_eq!(
        verify_cpu_sp_subword_effect(&context, Some(&effect))
            .unwrap()
            .unwrap()
            .source_u32,
        0
    );
    context.gpr[0] = 0x5566_7788;
    effect.value = 0x5566_7788;
    assert!(verify_cpu_sp_subword_effect(&context, Some(&effect)).is_err());
}

#[test]
fn decoded_occurrence_requires_aligned_pc_even_without_sink() {
    let (mut context, _) = zero_source();
    context.pc.0 += 1;
    assert!(verify_cpu_sp_subword_effect(&context, None).is_err());
}

#[test]
fn both_banks_and_endian_modes_preserve_all_lanes_and_faults() {
    for bank in [CpuSpBank::Dmem, CpuSpBank::Imem] {
        for reverse in [false, true] {
            for (opcode, size, xor) in [(0x28, 1, 7), (0x29, 2, 6)] {
                for lane in 0..8 {
                    let (mut context, mut effect) = zero_source();
                    let base = if bank == CpuSpBank::Imem {
                        0x04001000
                    } else {
                        0x04000000
                    };
                    context.gpr[1] = u64::from(base) | 0xffffffffa0000000;
                    context.gpr[2] = 0x1122334412345678;
                    context.instruction_word = opcode << 26 | 1 << 21 | 2 << 16 | lane;
                    context.reverse_endian = reverse;
                    effect.virtual_destination = GuestVirtualAddr(context.gpr[1] + u64::from(lane));
                    effect.translated_physical = PhysicalAddr(base + lane);
                    let offset = if reverse { lane ^ xor } else { lane };
                    effect.sink_word_address = PhysicalAddr(base + (offset & !3));
                    effect.bank = bank;
                    effect.offset = offset & !3;
                    // Independent table from the hardware-facing SPMEM examples.
                    effect.value = if size == 1 {
                        [0x78000000, 0x56780000, 0x34567800, 0x12345678][(offset & 3) as usize]
                    } else if offset & 2 == 0 {
                        0x56780000
                    } else {
                        0x12345678
                    };
                    if size == 2 && lane & 1 != 0 {
                        assert_eq!(verify_cpu_sp_subword_effect(&context, None).unwrap(), None);
                        assert!(verify_cpu_sp_subword_effect(&context, Some(&effect)).is_err());
                    } else {
                        let witness = verify_cpu_sp_subword_effect(&context, Some(&effect))
                            .unwrap()
                            .unwrap();
                        assert_eq!(witness.device_physical.0, base + offset);
                        assert_eq!(witness.value, effect.value);
                        assert_eq!(witness.bank, bank);
                    }
                }
            }
        }
    }
}
