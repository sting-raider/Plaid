use plaid_core::{
    exception_roots::{
        ExceptionClass, ExceptionRootInput, KernelAddressMode, resolve_exception_root,
    },
    pif_history::PifBackingFetchSample,
    program::{GuestVirtualAddr, PhysicalAddr},
};

fn bev1_general_root() -> GuestVirtualAddr {
    resolve_exception_root(ExceptionRootInput {
        class: ExceptionClass::General,
        bev: true,
        exl: false,
        kernel_mode: KernelAddressMode::Bits32,
    })
    .root
}

fn naive_address_value_match(
    root: GuestVirtualAddr,
    fetched_word: u32,
    sample: &PifBackingFetchSample,
) -> bool {
    sample.pc == root && sample.word == fetched_word && sample.matches_supplied_firmware
}

#[test]
fn current_coalesced_sample_cannot_authenticate_a_selected_root_fetch() {
    let root = bev1_general_root();
    let prior_backed_fetch = PifBackingFetchSample {
        pc: root,
        physical: PhysicalAddr(0x1fc0_0380),
        word: 0x2402_0007,
        offset: 0x380,
        matches_supplied_firmware: true,
        first_fetch: 4,
        last_fetch: 4,
        first_read_ordinal: 19,
        last_read_ordinal: 19,
        observations: 1,
    };

    // Model the validated SI-latch counterexample: fetch 5 has the same root
    // address and returned instruction bits as an earlier PIF-backed fetch, but
    // fetch 5 itself has no PIF backing read. Address/value matching therefore
    // assigns the earlier origin to the wrong occurrence.
    assert!(naive_address_value_match(
        root,
        0x2402_0007,
        &prior_backed_fetch
    ));
    assert_ne!(prior_backed_fetch.first_fetch, 5);
}

#[test]
fn multiple_identical_backed_observations_are_not_an_exact_fetch_receipt() {
    let root = bev1_general_root();
    let coalesced = PifBackingFetchSample {
        pc: root,
        physical: PhysicalAddr(0x1fc0_0380),
        word: 0x2402_0007,
        offset: 0x380,
        matches_supplied_firmware: true,
        first_fetch: 4,
        last_fetch: 8,
        first_read_ordinal: 19,
        last_read_ordinal: 41,
        observations: 2,
    };

    assert!(naive_address_value_match(root, 0x2402_0007, &coalesced));
    assert_ne!(coalesced.first_fetch, coalesced.last_fetch);
    assert!(coalesced.observations > 1);
}
