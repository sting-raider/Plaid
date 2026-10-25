use plaid_lower::rsp::{
    lower_rsp, plausible_overlay, plausible_program, plausible_short_overlay, plausible_task,
    plausible_text, reachable_words,
};

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
fn task_filter_follows_scalar_prologues_to_rsp_dma_subroutines() {
    let mut words = [0u32; 128];
    words[0] = 0x8c21_0004; // scalar DMEM setup
    words[1] = 0x0c00_0060; // jal IMEM 0x180, beyond the old 256-byte prefix
    words[64..68].copy_from_slice(&[
        0x4008_3000, // mfc0 t0, SP_DMA_BUSY
        0x4080_3800, // mtc0 zero, SP_SEMAPHORE
        0x03e0_0008,
        0, // checked indirect return
    ]);
    let bytes = |w: &[u32]| w.iter().flat_map(|w| w.to_be_bytes()).collect::<Vec<_>>();
    assert!(!plausible_text(&bytes(&words)));
    assert!(plausible_task(&bytes(&words), 0x80));
    for (at, value) in [
        (64, 0xffff_ffff),
        (65, 0),
        (1, 0x0c00_0100),
        (1, 0x0000_000d),
    ] {
        let mut bad = words;
        bad[at] = value;
        assert!(!plausible_task(&bytes(&bad), 0x80), "{at}: {value:08x}");
    }
    assert!(!plausible_task(&bytes(&words[..16]), 0x80));
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

#[test]
fn short_scalar_overlays_require_a_valid_resident_rsp_path() {
    let bytes = |words: &[u32]| {
        words
            .iter()
            .flat_map(|w| w.to_be_bytes())
            .collect::<Vec<_>>()
    };
    let mut resident = vec![0; 0xf80];
    resident[0x180..0x18c].copy_from_slice(&bytes(&[0x4008_3000, 0x03e0_0008, 0]));
    let text = bytes(&[0x3408_0042, 0x0800_0080, 0x2508_0001, 0]);
    assert!(plausible_short_overlay(&text, 0xd00, &resident));
    assert!(!plausible_overlay(&text));
    assert!(!plausible_short_overlay(&text, 0xd04, &resident));
    assert!(!plausible_short_overlay(&text, 0xff8, &resident));
    assert!(!plausible_short_overlay(&text, 0xd00, &resident[..0xf7c]));
    for bad in [0xffff_ffffu32, 0, 0x0800_0000] {
        let mut changed = resident.clone();
        changed[0x180..0x184].copy_from_slice(&bad.to_be_bytes());
        assert!(!plausible_short_overlay(&text, 0xd00, &changed));
    }
    let invalid_slot = bytes(&[0x3408_0042, 0x0800_0080, 0xffff_ffff, 0]);
    assert!(!plausible_short_overlay(&invalid_slot, 0xd00, &resident));
    let indirect_only = bytes(&[0x03e0_0008, 0]);
    assert!(!plausible_short_overlay(&indirect_only, 0xd00, &resident));
}

#[test]
fn a_short_program_followed_by_data_is_plausible_only_when_it_halts() {
    // ori at, 0x4000; mtc0 at, SP_STATUS; break; then pointer-table data.
    let words = [
        0x3401_4000u32,
        0x4081_2000,
        0x0000_000d,
        0x8000_65c0,
        0x8000_6720,
    ];
    let bytes = |w: &[u32]| w.iter().flat_map(|w| w.to_be_bytes()).collect::<Vec<_>>();
    assert!(plausible_program(&bytes(&words), 0x80));
    assert!(!plausible_text(&bytes(&words)));
    let mut changed = words;
    changed[2] = 0; // no BREAK: execution runs into the data and off the text
    assert!(!plausible_program(&bytes(&changed), 0x80));
    let mut changed = words;
    changed[1] = 0x3401_4001; // no RSP-specific instruction
    assert!(!plausible_program(&bytes(&changed), 0x80));
}
