use plaid_core::{
    EvidenceKind, GuestAddr,
    discovery::{CodeImage, direct_cfg},
    program::*,
    solver::{ClosureStatus, Scope, solve},
};

fn image(generation: u64) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x8000_0000),
            image: "entry-verification-test".into(),
            generation,
        },
        // J 0x80000000; NOP. This is a finite, immutable integer/control-flow loop.
        words: vec![0x0800_0000, 0],
        rom_offset: None,
        physical_start: None,
    }
}

fn closed_map(image: &CodeImage) -> ProgramMap {
    direct_cfg(
        RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        },
        image,
        &[image.base.pc],
        100,
    )
    .unwrap()
    .map
}

fn add_entry_verification(map: &mut ProgramMap, image: &CodeImage, epoch: u64) -> EvidenceRefs {
    let id = format!("entry-verify-trace-{epoch}");
    map.evidence.insert(
        id.clone(),
        Evidence {
            kind: EvidenceKind::Trace,
            producer: "synthetic-entry-verification".into(),
            revision: "v0".into(),
            detail: "typed dirty-entry byte verification".into(),
        },
    );
    let refs: EvidenceRefs = [id.clone()].into();
    map.entry_verifications.insert(ObservedEntryVerification {
        entry: image.base.clone(),
        register_mask: 0,
        source_unit: id,
        generation: epoch,
        evidence: refs.clone(),
    });
    refs
}

fn has(report: &plaid_core::solver::SolveReport, kind: &str) -> bool {
    report.blockers.iter().any(|blocker| blocker.kind == kind)
}

#[test]
fn deleting_invalidation_cannot_launder_post_epoch_entry_verification() {
    let image = image(0);

    // Epoch zero is the control: the typed verification does not by itself prove
    // that an invalidation occurred before the byte check.
    let mut epoch_zero = closed_map(&image);
    add_entry_verification(&mut epoch_zero, &image, 0);
    assert_eq!(
        solve(
            &epoch_zero,
            std::slice::from_ref(&image),
            Scope::DeclaredStaticImages,
        )
        .unwrap()
        .status,
        ClosureStatus::Closed,
    );

    // This is the importer chronology encoded by ADR-0022: Invalidate advances
    // the verification epoch before EntryBytesVerified is retained.
    let mut retained = closed_map(&image);
    let refs = add_entry_verification(&mut retained, &image, 1);
    retained.executable_writes.insert(ExecutableWrite {
        range: None,
        kind: WriteKind::Unknown,
        evidence: refs,
    });
    let report = solve(
        &retained,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
    assert!(has(&report, "unresolved_executable_write"));

    // Adversary: delete only the derived invalidation/write blocker while keeping
    // the independently typed verification and its later epoch. ADR-0009 requires
    // this to remain OPEN rather than manufacturing immutable-static closure.
    let mut laundered = retained;
    laundered.executable_writes.clear();
    laundered.validate().unwrap();
    let report = solve(
        &laundered,
        std::slice::from_ref(&image),
        Scope::DeclaredStaticImages,
    )
    .unwrap();
    assert_eq!(report.status, ClosureStatus::Open);
}
