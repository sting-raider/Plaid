//! A `jr` through a register that holds the entry `$ra` is a checked return
//! (ADR-0244); any other write to that register leaves the site open.
use plaid_core::{
    GuestAddr,
    data_roots::discover_address_taken,
    discovery::CodeImage,
    program::{CodeAddress, PhysicalAddr, ProgramMap, RomIdentity, RomOffset},
};

const BASE: u32 = 0x8000_0000;
const JAL_F: u32 = 0x0c00_0000 | (BASE + 4 * 4) >> 2 & 0x03ff_ffff;
const JAL_G: u32 = 0x0c00_0000 | (BASE + 9 * 4) >> 2 & 0x03ff_ffff;
const SAVE: u32 = 0x03e0_9825; // or s3, ra, zero
const JR_S3: u32 = 0x0260_0008;

/// main calls f; f saves `$ra` in s3, calls g and returns through s3.
fn map(f: [u32; 5]) -> ProgramMap {
    let mut words = vec![JAL_F, 0, 0x03e0_0008, 0];
    words.extend(f);
    words.extend([0x03e0_0008, 0]); // g
    let image = CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "saved-ra".into(),
            generation: 0,
        },
        words,
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
        holes: Vec::new(),
        slots: Vec::new(),
    };
    let rom = RomIdentity {
        sha256: "e".repeat(64),
        size: 4096,
    };
    let bytes: Vec<u8> = image.words.iter().flat_map(|w| w.to_be_bytes()).collect();
    discover_address_taken(
        rom,
        &bytes,
        &image,
        &[GuestAddr(BASE)],
        &[],
        None,
        &Default::default(),
        100,
    )
    .unwrap()
    .map
}

fn return_targets(map: &ProgramMap) -> Option<Vec<u32>> {
    let site = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc.0 == BASE + 7 * 4)?;
    let proof = map.evidence.get(site.closed_proof.as_ref()?)?;
    (proof.producer == plaid_core::returns::PRODUCER)
        .then(|| site.candidates.keys().map(|c| c.pc.0).collect())
}

#[test]
fn a_saved_ra_return_closes_only_when_the_copy_is_the_entry_ra() {
    assert_eq!(
        return_targets(&map([SAVE, JAL_G, 0, JR_S3, 0])),
        Some(vec![BASE + 8])
    );
    // copied after the call overwrote $ra
    assert_eq!(return_targets(&map([JAL_G, 0, SAVE, JR_S3, 0])), None);
    // the copy is not the only write to s3
    assert_eq!(
        return_targets(&map([SAVE, JAL_G, 0x2673_0004, JR_S3, 0])),
        None
    );
    // s3 never holds $ra
    assert_eq!(return_targets(&map([0, JAL_G, 0, JR_S3, 0])), None);
}
