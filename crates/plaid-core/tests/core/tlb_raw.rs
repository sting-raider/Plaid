use plaid_core::{
    GuestAddr,
    declared_loads::{DeclaredLoad, LoadEncoding, LoadImage, compose, verify_slots},
    discovery::direct_cfg,
    program::{GuestRange, RomIdentity, RomOffset},
};

fn fixture() -> (Vec<u8>, LoadImage) {
    let mut bytes = vec![0; 0x90];
    let words = [
        0x0c08_0000u32, // JAL E0200000 at architectural E0000000.
        0,
        0x0800_0004, // J E0000010 stays in this alternative.
        0,
        0x03e0_0008,
        0,
        0x3c08_e000, // Source self-address constants must not be relocated.
        0x2508_0010,
    ];
    for (at, word) in words.into_iter().enumerate() {
        bytes[0x40 + at * 4..0x44 + at * 4].copy_from_slice(&word.to_be_bytes());
    }
    bytes[0x80..0x84].copy_from_slice(&0x03e0_0008u32.to_be_bytes());
    let load = |placed, source, linked, size, text_size| DeclaredLoad {
        destination: GuestRange {
            start: GuestAddr(placed),
            size,
        },
        source: RomOffset(source),
        encoding: LoadEncoding::TlbRaw { text_size },
        evidence: Default::default(),
        relocatable: true,
        linked: Some(GuestAddr(linked)),
    };
    (
        bytes,
        LoadImage {
            base_offset: RomOffset(0),
            base: GuestRange {
                start: GuestAddr(0x8000_0000),
                size: 0x40,
            },
            loads: vec![
                load(0x8001_0000, 0x40, 0xe000_0000, 0x40, 0x20),
                load(0x8001_0040, 0x80, 0xe020_0000, 0x10, 0x10),
            ],
        },
    )
}

#[test]
fn unchanged_tlb_bytes_keep_virtual_jump_regions_and_internal_identity() {
    let (bytes, spec) = fixture();
    let (_, image) = compose(&bytes, &spec).unwrap();
    for offset in (0..0x40).step_by(4) {
        let expected = u32::from_be_bytes(bytes[0x40 + offset..0x44 + offset].try_into().unwrap());
        assert_eq!(
            image.word(GuestAddr(0x8001_0000 + offset as u32)),
            Some(expected)
        );
    }
    assert_eq!(
        image.linked_pc(GuestAddr(0x8001_0008)),
        GuestAddr(0xe000_0008)
    );
    assert_eq!(
        image.jump_target(GuestAddr(0x8001_0000), 0x0c08_0000),
        GuestAddr(0xe020_0000)
    );
    assert_eq!(
        image.jump_target(GuestAddr(0x8001_0008), 0x0800_0004),
        GuestAddr(0x8001_0010)
    );
    assert!(image.instruction_word(GuestAddr(0x8001_0020)).is_none());
    assert!(verify_slots(&image, Some(&spec)));
    let discovery = direct_cfg(
        RomIdentity {
            sha256: "0".repeat(64),
            size: bytes.len() as u64,
        },
        &image,
        &[GuestAddr(0x8001_0000), GuestAddr(0x8001_0040)],
        100,
    )
    .unwrap();
    assert!(
        discovery
            .map
            .direct_edges
            .iter()
            .any(|edge| edge.site.pc == GuestAddr(0x8001_0000)
                && edge.target.pc == GuestAddr(0xe020_0000))
    );
    assert!(
        !discovery
            .map
            .direct_edges
            .iter()
            .any(|edge| edge.target.pc == GuestAddr(0x8020_0000))
    );
}

#[test]
fn mapped_relative_branches_leave_storage_at_the_virtual_page_boundary() {
    let (mut bytes, mut spec) = fixture();
    spec.loads[1].linked = Some(GuestAddr(0xe000_0100));
    // The two virtual fragments are nearby, but independently placed.
    bytes[0x40..0x44].copy_from_slice(&0x1000_003fu32.to_be_bytes());
    bytes[0x80..0x84].copy_from_slice(&0x1000_ffbfu32.to_be_bytes());
    let (_, image) = compose(&bytes, &spec).unwrap();
    assert_eq!(
        image.branch_target(GuestAddr(0x8001_0000), 0x1000_0003),
        GuestAddr(0x8001_0010)
    );
    assert_eq!(
        image.branch_target(GuestAddr(0x8001_0000), 0x1000_007f),
        GuestAddr(0xe000_0200)
    );
    let d = plaid_core::pipeline::discover_image(
        RomIdentity {
            sha256: "0".repeat(64),
            size: bytes.len() as u64,
        },
        &image,
        &[GuestAddr(0x8001_0000)],
        1000,
    )
    .unwrap();
    for (site, target) in [(0x8001_0000, 0xe000_0100), (0x8001_0040, 0xe000_0000)] {
        assert!(
            d.map
                .direct_edges
                .iter()
                .any(|e| e.site.pc == GuestAddr(site) && e.target.pc == GuestAddr(target)),
            "branch at {site:08x} must name virtual target {target:08x}"
        );
    }
    assert!(
        d.map
            .blocks
            .iter()
            .any(|b| b.start.pc == GuestAddr(0x8001_0040))
    );
    assert!(
        !d.map
            .direct_edges
            .iter()
            .any(|e| e.target.pc == GuestAddr(0x8001_0100))
    );
}

#[test]
fn tlb_load_refuses_nonvirtual_links_missing_slots_and_bad_text_bounds() {
    let (bytes, spec) = fixture();
    for mode in 0..6 {
        let mut changed = spec.clone();
        let load = &mut changed.loads[0];
        match mode {
            0 => load.linked = Some(GuestAddr(0x8000_4000)),
            1 => load.linked = None,
            2 => load.relocatable = false,
            3 => load.encoding = LoadEncoding::TlbRaw { text_size: 0x44 },
            4 => load.encoding = LoadEncoding::TlbRaw { text_size: 0 },
            _ => load.linked = Some(GuestAddr(0x7fff_fff0)),
        }
        assert!(compose(&bytes, &changed).is_err(), "mode {mode}");
    }
    let (_, image) = compose(&bytes, &spec).unwrap();
    let mut changed = spec;
    changed.loads[0].encoding = LoadEncoding::TlbRaw { text_size: 0x24 };
    assert!(!verify_slots(&image, Some(&changed)));
}

#[test]
fn linked_register_and_direct_calls_discover_alternates_and_return_continuations() {
    let (mut bytes, spec) = fixture();
    for (n, word) in [0x3c19_e000u32, 0x0320_f809, 0, 0x0800_0003, 0]
        .into_iter()
        .enumerate()
    {
        bytes[n * 4..n * 4 + 4].copy_from_slice(&word.to_be_bytes());
    }
    let (_, image) = compose(&bytes, &spec).unwrap();
    let discovery = plaid_core::pipeline::discover_image(
        RomIdentity {
            sha256: "0".repeat(64),
            size: bytes.len() as u64,
        },
        &image,
        &[image.base.pc],
        1000,
    )
    .unwrap();
    for at in [0x8001_0000, 0x8001_0040] {
        assert!(
            discovery
                .map
                .blocks
                .iter()
                .any(|b| b.start.pc == GuestAddr(at))
        );
    }
    let calls = plaid_core::returns::ra_calls(&discovery.map, &image);
    assert!(
        calls
            .iter()
            .any(|(site, target)| site.pc == GuestAddr(0x8000_0004)
                && target.pc == GuestAddr(0x8001_0000))
    );
    assert!(
        calls
            .iter()
            .any(|(site, target)| site.pc == GuestAddr(0x8001_0000)
                && target.pc == GuestAddr(0x8001_0040))
    );
    let shim_return = discovery
        .map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc == GuestAddr(0x8001_0040))
        .unwrap();
    assert!(
        plaid_core::returns::Closure::new(&discovery.map, &image).verify(
            &discovery.map,
            &image,
            shim_return
        )
    );
}

#[test]
fn mapped_register_tail_discovers_bound_text_without_rewriting_guest_target() {
    let (mut bytes, spec) = fixture();
    for (n, word) in [0x3c19_e020u32, 0x0320_0008, 0].into_iter().enumerate() {
        bytes[n * 4..n * 4 + 4].copy_from_slice(&word.to_be_bytes());
    }
    let (_, image) = compose(&bytes, &spec).unwrap();
    let d = plaid_core::pipeline::discover_image(
        RomIdentity {
            sha256: "0".repeat(64),
            size: bytes.len() as u64,
        },
        &image,
        &[image.base.pc],
        1000,
    )
    .unwrap();
    assert!(
        d.map
            .blocks
            .iter()
            .any(|b| b.start.pc == GuestAddr(0x8001_0040))
    );
    let site = d
        .map
        .indirect_sites
        .iter()
        .find(|s| s.site.pc == GuestAddr(0x8000_0004))
        .unwrap();
    assert!(
        site.candidates
            .keys()
            .any(|a| a.pc == GuestAddr(0xe020_0000))
    );
    assert!(plaid_core::indirect::verify_constant(&d.map, &image, site));
    let mut map = d.map;
    let mut spec = spec;
    let evidence = map.evidence.keys().next().unwrap().clone();
    for load in &mut spec.loads {
        load.evidence = [evidence.clone()].into();
    }
    map.load_images.insert(image.base.image.clone(), spec);
    let check = |map: &plaid_core::program::ProgramMap| {
        plaid_core::solver::solve(
            map,
            std::slice::from_ref(&image),
            plaid_core::solver::Scope::DeclaredStaticImagesGuardedRam,
        )
        .unwrap()
        .blockers
        .iter()
        .any(|b| {
            b.kind == "unresolved_indirect_target"
                && b.site
                    .as_ref()
                    .is_some_and(|s| s.pc == GuestAddr(0x80000004))
        })
    };
    assert!(!check(&map));
    map.load_images.clear();
    assert!(check(&map));
}

#[test]
fn replay_mapped_layout_cannot_disable_or_escape_physical_guards() {
    let (bytes, spec) = fixture();
    let mut load = spec.loads[0].clone();
    load.source = RomOffset(0);
    let data = &bytes[0x40..0x80];
    let encoding = |entry, physical| LoadEncoding::AresTlb {
        entry: GuestAddr(entry),
        physical,
        text_size: 0x20,
    };
    load.encoding = encoding(0xe0000000, 0x2000);
    assert!(load.layout(data).is_ok());
    for (entry, physical) in [
        (0xe0000000, u32::MAX),
        (0xe0000000, 0x800000),
        (0xe0000000, 0x2002),
        (0xe0000020, 0x2000),
        (0xe0000002, 0x2000),
    ] {
        load.encoding = encoding(entry, physical);
        assert!(load.layout(data).is_err());
    }
    load.encoding = encoding(0xe0000000, 0x2000);
    load.source = RomOffset(4);
    assert!(load.layout(data).is_err());
}

#[test]
fn native_bodies_stop_before_a_tail_leaves_their_binding() {
    let (mut bytes, spec) = fixture();
    for (offset, words) in [
        (0usize, vec![0x3c19_e000u32, 0x0320_f809, 0, 0x0800_0003, 0]),
        (0x20, vec![0x03e0_0008, 0]),
        (0x40, vec![0x3c19_8000, 0x2739_0020, 0x0320_0008, 0]),
    ] {
        for (n, word) in words.into_iter().enumerate() {
            bytes[offset + n * 4..offset + n * 4 + 4].copy_from_slice(&word.to_be_bytes());
        }
    }
    let (_, image) = compose(&bytes, &spec).unwrap();
    let d = plaid_core::pipeline::discover_image(
        RomIdentity {
            sha256: "0".repeat(64),
            size: bytes.len() as u64,
        },
        &image,
        &[image.base.pc],
        1000,
    )
    .unwrap();
    let entry = image.address(GuestAddr(0x8001_0000));
    let target = image.address(GuestAddr(0x8000_0020));
    assert!(plaid_core::returns::function_body(&d.map, &image, &entry).contains(&target));
    let bodies = plaid_core::returns::function_bodies_partitioned(
        &d.map,
        &image,
        [&entry],
        |a| {
            image.slots.iter().position(|(range, _, _)| {
                u64::from(a.pc.0) >= u64::from(range.start.0) && u64::from(a.pc.0) < range.end()
            })
        },
        &Default::default(),
    );
    assert!(bodies[&entry].contains(&entry));
    assert!(!bodies[&entry].contains(&target));
}
