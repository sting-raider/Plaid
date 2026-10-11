use plaid_core::{
    program::GuestVirtualAddr,
    watch_roots::{
        WatchAccessInput, WatchAccessKind, WatchAssessment, WatchConfig, WatchNoImmediateReason,
        WatchState, WatchUnresolvedReason, assess_watch_access,
    },
};

fn known(generation: u64, block: u32, trap_load: bool, trap_store: bool) -> WatchState {
    WatchState::Known(WatchConfig {
        generation,
        physical_block: block,
        trap_load,
        trap_store,
    })
}

fn input(
    state: WatchState,
    kind: WatchAccessKind,
    physical_address: Option<u32>,
    exl: Option<bool>,
    bev: Option<bool>,
) -> WatchAccessInput {
    WatchAccessInput {
        state,
        kind,
        physical_address,
        exl,
        bev,
    }
}

#[test]
fn reset_unknown_remains_unresolved_but_cache_is_excluded() {
    let load = assess_watch_access(input(
        WatchState::Unknown,
        WatchAccessKind::Load,
        Some(0x1000),
        Some(false),
        Some(false),
    ))
    .unwrap();
    assert_eq!(
        load,
        WatchAssessment::Unresolved {
            reason: WatchUnresolvedReason::UnknownWatchState,
            watch_generation: None,
        }
    );

    let cache = assess_watch_access(input(
        WatchState::Unknown,
        WatchAccessKind::Cache,
        None,
        None,
        None,
    ))
    .unwrap();
    assert_eq!(
        cache,
        WatchAssessment::NoImmediateWatch {
            reason: WatchNoImmediateReason::CacheExcluded,
            watch_generation: None,
        }
    );
}

#[test]
fn physical_eight_byte_matching_and_access_enable_are_fail_closed() {
    for address in [0x1000, 0x1004] {
        let result = assess_watch_access(input(
            known(1, 0x1000, true, false),
            WatchAccessKind::Load,
            Some(address),
            Some(false),
            Some(false),
        ))
        .unwrap();
        let WatchAssessment::ImmediateWatch(receipt) = result else {
            panic!("matching read must produce the bounded immediate Watch receipt");
        };
        assert_eq!(receipt.exception_code, 23);
        assert_eq!(receipt.watch_generation, 1);
        assert_eq!(receipt.physical_block, 0x1000);
        assert_eq!(receipt.physical_address, address);
        assert_eq!(receipt.root, GuestVirtualAddr(0xffff_ffff_8000_0180));
    }

    let next_block = assess_watch_access(input(
        known(1, 0x1000, true, false),
        WatchAccessKind::Load,
        Some(0x1008),
        Some(false),
        Some(false),
    ))
    .unwrap();
    assert_eq!(
        next_block,
        WatchAssessment::NoImmediateWatch {
            reason: WatchNoImmediateReason::PhysicalBlockMismatch,
            watch_generation: Some(1),
        }
    );

    let wrong_kind = assess_watch_access(input(
        known(2, 0x1000, false, true),
        WatchAccessKind::Load,
        None,
        None,
        None,
    ))
    .unwrap();
    assert_eq!(
        wrong_kind,
        WatchAssessment::NoImmediateWatch {
            reason: WatchNoImmediateReason::AccessDisabled,
            watch_generation: Some(2),
        }
    );
}

#[test]
fn missing_context_and_postponed_timing_never_become_normal_or_immediate() {
    let missing_physical = assess_watch_access(input(
        known(3, 0x2000, true, false),
        WatchAccessKind::Load,
        None,
        Some(false),
        Some(false),
    ))
    .unwrap();
    assert_eq!(
        missing_physical,
        WatchAssessment::Unresolved {
            reason: WatchUnresolvedReason::MissingPhysicalAddress,
            watch_generation: Some(3),
        }
    );

    let unknown_exl = assess_watch_access(input(
        known(3, 0x2000, true, false),
        WatchAccessKind::Load,
        Some(0x2000),
        None,
        Some(false),
    ))
    .unwrap();
    assert_eq!(
        unknown_exl,
        WatchAssessment::Unresolved {
            reason: WatchUnresolvedReason::UnknownExl,
            watch_generation: Some(3),
        }
    );

    let postponed = assess_watch_access(input(
        known(3, 0x2000, true, false),
        WatchAccessKind::Load,
        Some(0x2004),
        Some(true),
        Some(false),
    ))
    .unwrap();
    assert_eq!(
        postponed,
        WatchAssessment::Unresolved {
            reason: WatchUnresolvedReason::PostponedWhileExl,
            watch_generation: Some(3),
        }
    );

    let unknown_bev = assess_watch_access(input(
        known(3, 0x2000, true, false),
        WatchAccessKind::Load,
        Some(0x2000),
        Some(false),
        None,
    ))
    .unwrap();
    assert_eq!(
        unknown_bev,
        WatchAssessment::Unresolved {
            reason: WatchUnresolvedReason::UnknownBev,
            watch_generation: Some(3),
        }
    );
}

#[test]
fn bev_selects_common_general_root_without_erasing_watch_reason() {
    let result = assess_watch_access(input(
        known(4, 0x3000, false, true),
        WatchAccessKind::Store,
        Some(0x3000),
        Some(false),
        Some(true),
    ))
    .unwrap();
    let WatchAssessment::ImmediateWatch(receipt) = result else {
        panic!("matching store must produce Watch receipt");
    };
    assert_eq!(receipt.exception_code, 23);
    assert_eq!(receipt.root, GuestVirtualAddr(0xffff_ffff_bfc0_0380));
}

#[test]
fn same_value_configuration_rewrite_keeps_distinct_generation_identity() {
    let first = assess_watch_access(input(
        known(8, 0x4000, true, false),
        WatchAccessKind::Load,
        Some(0x4000),
        Some(false),
        Some(false),
    ))
    .unwrap();
    let second = assess_watch_access(input(
        known(9, 0x4000, true, false),
        WatchAccessKind::Load,
        Some(0x4000),
        Some(false),
        Some(false),
    ))
    .unwrap();
    assert_ne!(first, second);
    let WatchAssessment::ImmediateWatch(first) = first else {
        unreachable!()
    };
    let WatchAssessment::ImmediateWatch(second) = second else {
        unreachable!()
    };
    assert_eq!((first.watch_generation, second.watch_generation), (8, 9));
}

#[test]
fn malformed_known_configuration_is_rejected() {
    assert!(
        assess_watch_access(input(
            known(0, 0x1000, true, false),
            WatchAccessKind::Load,
            Some(0x1000),
            Some(false),
            Some(false),
        ))
        .is_err()
    );
    assert!(
        assess_watch_access(input(
            known(1, 0x1004, true, false),
            WatchAccessKind::Load,
            Some(0x1004),
            Some(false),
            Some(false),
        ))
        .is_err()
    );
}
