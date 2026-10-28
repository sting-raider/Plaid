//! Residual dispatch is a validation-only scope (ADR-0218): it accepts unproven
//! indirect sites and nothing else.
use plaid_core::{
    GuestAddr,
    data_roots::discover_address_taken,
    discovery::CodeImage,
    program::{CodeAddress, PhysicalAddr, ProgramMap, RomIdentity, RomOffset},
    solver::{ClosureStatus, Scope, solve},
};

const BASE: u32 = 0x8000_0000;
const F: u32 = BASE + 6 * 4;

/// main jumps through a pointer loaded from the caller's memory: no proof.
fn image() -> CodeImage {
    let words = vec![
        0x3c09_8000,                // lui t1, 0x8000
        0x2529_0000 | (F & 0xffff), // addiu t1, t1, f (address-taken)
        0x8c88_0000,                // lw t0, 0(a0)
        0x0100_0008,                // jr t0
        0,
        0,
        0x2482_0001, // f: addiu v0, a0, 1
        0x03e0_0008, // jr ra
        0,
    ];
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "residual".into(),
            generation: 0,
        },
        words,
        rom_offset: Some(RomOffset(64)),
        physical_start: Some(PhysicalAddr(0)),
        holes: Vec::new(),
        slots: Vec::new(),
    }
}

fn map(image: &CodeImage) -> ProgramMap {
    let rom = RomIdentity {
        sha256: "f".repeat(64),
        size: 4096,
    };
    let bytes: Vec<u8> = image.words.iter().flat_map(|w| w.to_be_bytes()).collect();
    discover_address_taken(
        rom,
        &bytes,
        image,
        &[GuestAddr(BASE)],
        &[],
        None,
        &Default::default(),
        100,
    )
    .unwrap()
    .map
}

fn kinds(map: &ProgramMap, image: &CodeImage, scope: Scope) -> Vec<String> {
    let report = solve(map, std::slice::from_ref(image), scope).unwrap();
    report.blockers.iter().map(|b| b.kind.clone()).collect()
}

#[test]
fn only_the_residual_scope_accepts_an_unproven_indirect_site() {
    let image = image();
    let map = map(&image);
    let default = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImagesGuardedRamAddressTaken,
    )
    .unwrap();
    assert_eq!(default.status, ClosureStatus::Open);
    assert!(default.residual_sites.is_empty());
    assert!(
        default
            .blockers
            .iter()
            .any(|b| b.kind == "unresolved_indirect_site")
    );
    let residual = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImagesGuardedRamResidualDispatch,
    )
    .unwrap();
    assert_eq!(
        residual.status,
        ClosureStatus::Closed,
        "{:?}",
        residual.blockers
    );
    assert!(!residual.native_complete);
    assert_eq!(
        residual
            .residual_sites
            .iter()
            .map(|s| s.pc)
            .collect::<Vec<_>>(),
        [GuestAddr(BASE + 12)]
    );
    assert!(
        residual
            .assumptions
            .iter()
            .any(|a| a.contains("VALIDATION ONLY"))
    );
}

#[test]
fn every_other_blocker_still_refuses_under_the_residual_scope() {
    let mut image = image();
    // SYSCALL remains unsupported; TLBWR now has an explicit bounded contract.
    image.words[4] = 0x0000_000c;
    let map = map(&image);
    let plain = kinds(
        &map,
        &image,
        Scope::DeclaredStaticImagesGuardedRamAddressTaken,
    );
    let other: Vec<_> = plain
        .iter()
        .filter(|k| !k.starts_with("unresolved_indirect"))
        .collect();
    assert!(!other.is_empty(), "{plain:?}");
    let residual = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImagesGuardedRamResidualDispatch,
    )
    .unwrap();
    assert_eq!(residual.status, ClosureStatus::Open);
    assert!(
        residual
            .blockers
            .iter()
            .any(|b| !b.kind.starts_with("unresolved_indirect"))
    );
}

#[test]
fn residual_dispatch_does_not_hide_an_unmapped_candidate() {
    let image = image();
    let mut map = map(&image);
    let original = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc == GuestAddr(BASE + 12))
        .unwrap()
        .clone();
    map.indirect_sites.remove(&original);
    let mut site = original;
    site.candidates.insert(
        CodeAddress {
            pc: GuestAddr(BASE + 0x1000),
            ..image.base.clone()
        },
        map.entries[&image.base].clone(),
    );
    map.indirect_sites.insert(site);
    let report = solve(
        &map,
        &[image],
        Scope::DeclaredStaticImagesGuardedRamResidualDispatch,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(
        report
            .blockers
            .iter()
            .any(|b| b.kind == "unresolved_indirect_target")
    );
}

#[test]
fn residual_dispatch_faults_on_an_sp_memory_candidate_instead_of_refusing() {
    let image = image();
    let mut map = map(&image);
    let original = map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc == GuestAddr(BASE + 12))
        .unwrap()
        .clone();
    map.indirect_sites.remove(&original);
    let mut site = original;
    // CPU code copied into SP DMEM and entered there (uncached KSEG1).
    let dmem = CodeAddress {
        pc: GuestAddr(0xa400_00b0),
        ..image.base.clone()
    };
    site.candidates
        .insert(dmem.clone(), map.entries[&image.base].clone());
    map.indirect_sites.insert(site.clone());
    let residual = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImagesGuardedRamResidualDispatch,
    )
    .unwrap();
    assert!(
        !residual
            .blockers
            .iter()
            .any(|b| b.kind == "unresolved_indirect_target")
    );
    assert!(residual.residual_sites.contains(&site.site));
    // Without residual dispatch the same candidate still refuses closure.
    let strict = solve(
        &map,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImagesGuardedRam,
    )
    .unwrap();
    assert!(
        strict
            .blockers
            .iter()
            .any(|b| b.kind == "unresolved_indirect_target")
    );
    // A target the replay actually took there is still a blocker.
    map.indirect_sites.remove(&site);
    site.observed.insert(dmem, map.entries[&image.base].clone());
    map.indirect_sites.insert(site);
    let observed = solve(
        &map,
        &[image],
        Scope::DeclaredStaticImagesGuardedRamResidualDispatch,
    )
    .unwrap();
    assert!(
        observed
            .blockers
            .iter()
            .any(|b| b.kind == "unresolved_indirect_target")
    );
}
