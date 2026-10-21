use plaid_lower::rsp::{lower_rsp, plausible_overlay, plausible_text, reachable_words};

fn reach(words: &[u32], imem: u32) -> plaid_lower::rsp::RspReachability {
    reachable_words(
        &words
            .iter()
            .flat_map(|w| w.to_be_bytes())
            .collect::<Vec<_>>(),
        imem,
    )
    .unwrap()
}

#[test]
fn fetch_closure_includes_branches_and_delay_slots_but_excludes_data_after_halt() {
    // Both conditional arms, a jump and its slot, then BREAK with code bits.
    let r = reach(
        &[0x1400_0002, 0, 0x0800_0025, 0, 0x0001_000d, 13, 0xffff_ffff],
        0x80,
    );
    assert_eq!(r.words, vec![0x80, 0x84, 0x88, 0x8c, 0x90, 0x94]);
    assert!(!r.indirect);
    assert!(r.exits.is_empty());
}

#[test]
fn startup_mask_stops_at_indirect_jumps_and_retains_other_pending_arms() {
    let r = reach(&[0x03e0_0008, 0, 13, 0xffff_ffff], 0x80);
    assert!(r.indirect);
    assert_eq!(r.words, vec![0x80, 0x84]);
    assert!(r.exits.is_empty());
    let r = reach(&[0x1400_0003, 0, 0x03e0_0008, 0, 13], 0x80);
    assert_eq!(r.words, vec![0x80, 0x84, 0x88, 0x8c, 0x90]);
    assert!(r.indirect);
}

#[test]
fn closure_tracks_exits_and_independent_entry_into_a_delay_slot() {
    let r = reach(&[0x0800_0021, 0, 13], 0x80);
    assert_eq!(r.words, vec![0x80, 0x84, 0x88]);
    let r = reach(&[0x0800_0000, 0], 0x80);
    assert_eq!(r.exits, vec![0]);
    assert!(reachable_words(&[0; 3], 0).is_err());
    assert!(reachable_words(&[0; 8], 0xffc).is_err());
}

#[test]
fn content_filter_requires_rsp_operations_and_decodable_entry_words() {
    let mut words = [0u32; 64];
    assert!(!plausible_text(
        &words
            .iter()
            .flat_map(|w| w.to_be_bytes())
            .collect::<Vec<_>>()
    ));
    words[0] = 0x4008_3000; // mfc0 t0, SP_DMA_BUSY
    words[1] = 0x4080_3800; // mtc0 zero, SP_SEMAPHORE
    words[2] = 0x0000_000d; // break
    let bytes: Vec<_> = words.iter().flat_map(|w| w.to_be_bytes()).collect();
    assert!(plausible_text(&bytes));
    assert!(
        lower_rsp(&bytes, 0, "synthetic_rom")
            .unwrap()
            .stubs
            .is_empty()
    );
    words[3] = 0xffff_ffff;
    assert!(!plausible_text(
        &words
            .iter()
            .flat_map(|w| w.to_be_bytes())
            .collect::<Vec<_>>()
    ));
    assert!(!plausible_text(&bytes[..64]));
}

#[test]
fn table_named_overlays_need_only_code_and_one_rsp_operation() {
    let bytes = |words: &[u32]| {
        words
            .iter()
            .flat_map(|w| w.to_be_bytes())
            .collect::<Vec<_>>()
    };
    let mut words = [0u32; 26]; // 104 bytes, below the whole-text minimum
    assert!(!plausible_overlay(&bytes(&words)));
    words[0] = 0x4008_3000; // mfc0 t0, SP_DMA_BUSY
    assert!(plausible_overlay(&bytes(&words)));
    assert!(!plausible_text(&bytes(&words)));
    assert!(!plausible_overlay(&bytes(&words[..15])));
    words[25] = 0xffff_ffff;
    assert!(!plausible_overlay(&bytes(&words)));
}
