use plaid_core::{
    cpu_mutation::{
        CompletedCop1StoreEffect, Cop1SourceLane, CpuMutationDomain, verify_cop1_store_effect,
    },
    program::{GuestVirtualAddr, PhysicalAddr},
};

fn swc1(base: u8, ft: u8, immediate: i16) -> u32 {
    (0x39 << 26) | (u32::from(base) << 21) | (u32::from(ft) << 16) | u32::from(immediate as u16)
}

fn state() -> ([u64; 32], [u64; 32]) {
    let mut gpr = [0; 32];
    gpr[1] = 0xffff_ffff_a000_2000;
    let mut fpr = [0; 32];
    fpr[0] = 0x1122_3344_5566_7788;
    fpr[1] = 0xdead_beef_1122_3344;
    (gpr, fpr)
}

fn effect(payload: &[u8]) -> CompletedCop1StoreEffect {
    CompletedCop1StoreEffect {
        effect_ordinal: 41,
        virtual_destination: GuestVirtualAddr(0xffff_ffff_a000_2000),
        physical_destination: PhysicalAddr(0x2000),
        domain: CpuMutationDomain::Backing,
        payload: payload.to_vec(),
    }
}

#[test]
fn impossible_zero_register_cannot_supply_a_store_destination() {
    let (mut gpr, fpr) = state();
    gpr[0] = gpr[1];
    let observed = effect(&[0x55, 0x66, 0x77, 0x88]);
    for base in [0, 1] {
        assert!(
            verify_cop1_store_effect(swc1(base, 0, 0), &gpr, &fpr, false, true, Some(&observed))
                .is_err()
        );
    }
    assert!(verify_cop1_store_effect(swc1(1, 0, 0), &gpr, &fpr, false, true, None).is_err());
}

#[test]
fn cu1_disabled_context_cannot_claim_completed_sink() {
    let (gpr, fpr) = state();
    let observed = effect(&[0x55, 0x66, 0x77, 0x88]);
    assert_eq!(
        verify_cop1_store_effect(swc1(1, 0, 0), &gpr, &fpr, false, false, Some(&observed))
            .unwrap_err(),
        "completed COP1 effect while CU1 disabled"
    );
}

#[test]
fn cu1_disabled_without_sink_creates_no_writer() {
    let (gpr, fpr) = state();
    assert_eq!(
        verify_cop1_store_effect(swc1(1, 0, 0), &gpr, &fpr, false, false, None).unwrap(),
        None
    );
}

#[test]
fn equal_payload_does_not_collapse_fr_source_identity() {
    let (gpr, fpr) = state();
    let observed = effect(&[0x11, 0x22, 0x33, 0x44]);

    let fr0 = verify_cop1_store_effect(swc1(1, 1, 0), &gpr, &fpr, false, true, Some(&observed))
        .unwrap()
        .unwrap();
    let fr1 = verify_cop1_store_effect(swc1(1, 1, 0), &gpr, &fpr, true, true, Some(&observed))
        .unwrap()
        .unwrap();

    assert_eq!(fr0.payload, fr1.payload);
    assert_eq!(fr0.source.storage_fpr, 0);
    assert_eq!(fr0.source.lane, Cop1SourceLane::High32);
    assert_eq!(fr1.source.storage_fpr, 1);
    assert_eq!(fr1.source.lane, Cop1SourceLane::Low32);
    assert_ne!(fr0.source, fr1.source);
}

#[test]
fn lower_observer_domain_remains_part_of_identity() {
    let (gpr, fpr) = state();
    let mut resident = effect(&[0x55, 0x66, 0x77, 0x88]);
    resident.domain = CpuMutationDomain::CacheResident;
    let backing = effect(&[0x55, 0x66, 0x77, 0x88]);

    let resident =
        verify_cop1_store_effect(swc1(1, 0, 0), &gpr, &fpr, false, true, Some(&resident))
            .unwrap()
            .unwrap();
    let backing = verify_cop1_store_effect(swc1(1, 0, 0), &gpr, &fpr, false, true, Some(&backing))
        .unwrap()
        .unwrap();

    assert_eq!(resident.payload, backing.payload);
    assert_ne!(resident.domain, backing.domain);
}

#[test]
fn payload_equality_cannot_override_selected_fpr_bytes() {
    let (gpr, fpr) = state();
    let forged = effect(&[0x11, 0x22, 0x33, 0x44]);
    assert_eq!(
        verify_cop1_store_effect(swc1(1, 0, 0), &gpr, &fpr, false, true, Some(&forged))
            .unwrap_err(),
        "COP1 store payload/source mismatch"
    );
}
