use plaid_core::interrupt_roots::{
    MaskableInterruptRootInput, MaskableInterruptRootReceipt, resolve_maskable_interrupt_root,
    verify_maskable_interrupt_root_receipt,
};
use plaid_core::program::GuestVirtualAddr;

fn expected_root(bev: bool) -> GuestVirtualAddr {
    GuestVirtualAddr(if bev {
        0xffff_ffff_bfc0_0380
    } else {
        0xffff_ffff_8000_0180
    })
}

#[test]
fn reproduces_validated_32_case_gate_matrix() {
    let mut cases = 0;
    let mut taken = 0;
    let mut suppressed = 0;

    for bev in [false, true] {
        for bit in 0..8 {
            let pending = 1u8 << bit;
            let input = MaskableInterruptRootInput {
                pending,
                mask: pending,
                ie: true,
                exl: false,
                erl: false,
                bev,
            };
            let receipt = resolve_maskable_interrupt_root(input).expect("matched IP/IM must admit");
            assert_eq!(receipt.input, input);
            assert_eq!(receipt.matched_pending, pending);
            assert_eq!(receipt.root, expected_root(bev));
            cases += 1;
            taken += 1;
        }

        let multi = MaskableInterruptRootInput {
            pending: 0xa5,
            mask: 0x24,
            ie: true,
            exl: false,
            erl: false,
            bev,
        };
        let receipt = resolve_maskable_interrupt_root(multi).expect("one or more matches admit");
        assert_eq!(receipt.input, multi);
        assert_eq!(receipt.matched_pending, 0x24);
        assert_eq!(receipt.root, expected_root(bev));
        cases += 1;
        taken += 1;

        let suppressed_inputs = [
            MaskableInterruptRootInput {
                pending: 0x04,
                mask: 0x08,
                ie: true,
                exl: false,
                erl: false,
                bev,
            },
            MaskableInterruptRootInput {
                pending: 0x55,
                mask: 0xaa,
                ie: true,
                exl: false,
                erl: false,
                bev,
            },
            MaskableInterruptRootInput {
                pending: 0x04,
                mask: 0x04,
                ie: false,
                exl: false,
                erl: false,
                bev,
            },
            MaskableInterruptRootInput {
                pending: 0x04,
                mask: 0x04,
                ie: true,
                exl: true,
                erl: false,
                bev,
            },
            MaskableInterruptRootInput {
                pending: 0x04,
                mask: 0x04,
                ie: true,
                exl: false,
                erl: true,
                bev,
            },
            MaskableInterruptRootInput {
                pending: 0x00,
                mask: 0xff,
                ie: true,
                exl: false,
                erl: false,
                bev,
            },
            MaskableInterruptRootInput {
                pending: 0xff,
                mask: 0x00,
                ie: true,
                exl: false,
                erl: false,
                bev,
            },
        ];

        for input in suppressed_inputs {
            assert_eq!(resolve_maskable_interrupt_root(input), None);
            cases += 1;
            suppressed += 1;
        }
    }

    assert_eq!(cases, 32);
    assert_eq!(taken, 18);
    assert_eq!(suppressed, 14);
}

#[test]
fn receipt_retains_full_state_and_only_enabled_pending_subset() {
    let input = MaskableInterruptRootInput {
        pending: 0xe5,
        mask: 0x24,
        ie: true,
        exl: false,
        erl: false,
        bev: false,
    };
    let receipt = resolve_maskable_interrupt_root(input).expect("0x24 is enabled and pending");

    assert_eq!(receipt.input, input);
    assert_eq!(receipt.matched_pending, 0x24);
    assert_eq!(receipt.root, expected_root(false));
}

#[test]
fn pending_bits_alone_never_manufacture_reachability() {
    for input in [
        MaskableInterruptRootInput {
            pending: 0xff,
            mask: 0x00,
            ie: true,
            exl: false,
            erl: false,
            bev: false,
        },
        MaskableInterruptRootInput {
            pending: 0xff,
            mask: 0xff,
            ie: false,
            exl: false,
            erl: false,
            bev: false,
        },
        MaskableInterruptRootInput {
            pending: 0xff,
            mask: 0xff,
            ie: true,
            exl: true,
            erl: false,
            bev: false,
        },
        MaskableInterruptRootInput {
            pending: 0xff,
            mask: 0xff,
            ie: true,
            exl: false,
            erl: true,
            bev: false,
        },
    ] {
        assert!(resolve_maskable_interrupt_root(input).is_none());
    }
}

#[test]
fn receipt_rechecking_retains_external_state_even_when_numeric_root_is_equal() {
    let input = MaskableInterruptRootInput {
        pending: 0xe5,
        mask: 0x24,
        ie: true,
        exl: false,
        erl: false,
        bev: false,
    };
    let receipt = resolve_maskable_interrupt_root(input).unwrap();
    verify_maskable_interrupt_root_receipt(&receipt, input).unwrap();
    let mut forged = receipt;
    forged.root = expected_root(true);
    assert!(verify_maskable_interrupt_root_receipt(&forged, input).is_err());
    forged = receipt;
    forged.matched_pending = 0xe5;
    assert!(verify_maskable_interrupt_root_receipt(&forged, input).is_err());
    forged = receipt;
    forged.input.pending = 0x24;
    // The edited pending state would produce the same subset/root, but is not
    // the independently supplied state against which this receipt is checked.
    assert_eq!(
        resolve_maskable_interrupt_root(forged.input).unwrap().root,
        receipt.root
    );
    assert!(verify_maskable_interrupt_root_receipt(&forged, input).is_err());
}

#[test]
fn suppressed_boundary_cannot_verify_an_eligible_receipt() {
    let input = MaskableInterruptRootInput {
        pending: 4,
        mask: 4,
        ie: true,
        exl: false,
        erl: false,
        bev: true,
    };
    let receipt = resolve_maskable_interrupt_root(input).unwrap();
    for suppressed in [
        MaskableInterruptRootInput { ie: false, ..input },
        MaskableInterruptRootInput { exl: true, ..input },
        MaskableInterruptRootInput { erl: true, ..input },
        MaskableInterruptRootInput { mask: 0, ..input },
        MaskableInterruptRootInput {
            pending: 0,
            ..input
        },
    ] {
        assert!(verify_maskable_interrupt_root_receipt(&receipt, suppressed).is_err());
    }
}

#[test]
fn serialized_boundary_and_receipt_types_reject_aliases_and_extra_fields() {
    use serde_json::json;
    let input = MaskableInterruptRootInput {
        pending: 4,
        mask: 4,
        ie: true,
        exl: false,
        erl: false,
        bev: false,
    };
    let value = serde_json::to_value(input).unwrap();
    for (field, replacement) in [
        ("pending", json!(256)),
        ("mask", json!(true)),
        ("ie", json!(1)),
        ("native_complete", json!(true)),
    ] {
        let mut forged = value.clone();
        forged[field] = replacement;
        assert!(serde_json::from_value::<MaskableInterruptRootInput>(forged).is_err());
    }
    let mut forged = serde_json::to_value(resolve_maskable_interrupt_root(input).unwrap()).unwrap();
    forged["producer_generation"] = json!(1);
    assert!(serde_json::from_value::<MaskableInterruptRootReceipt>(forged).is_err());
}
