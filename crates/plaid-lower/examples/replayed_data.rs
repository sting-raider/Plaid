//! Authored first-use data contract, consumed by runtime/test_replayed_data.py.
use plaid_core::{
    EvidenceKind, GuestAddr,
    declared_loads::{DeclaredLoad, LoadEncoding, LoadImage},
    discovery::CodeImage,
    pipeline::discover_image_with_loads,
    program::*,
};
use std::{collections::BTreeMap, path::PathBuf};

fn main() {
    let out = PathBuf::from(std::env::args().nth(1).expect("output directory"));
    std::fs::create_dir_all(&out).unwrap();
    for mode in ["init", "tamper", "rewrite"] {
        let base = 0x80000000;
        let mut words = vec![0; 0x1008 / 4];
        words[..8].copy_from_slice(&[
            0x3c088000,
            0x3c098000,
            0x35290080,
            0xad091000,
            0x352900a0,
            0xad091004,
            if mode == "tamper" { 0xad001000 } else { 0 },
            0x24040000,
        ]);
        words[8..18].copy_from_slice(&[
            0x2c890002, 0x1120000e, 0, 0x3c088000, 0x25081000, 0x00045080, 0x010a4021, 0x8d080000,
            0x01000008, 0,
        ]);
        words[0x60 / 4..0x6c / 4].copy_from_slice(&[0x24020000, 0x080003c0, 0]);
        words[0x80 / 4..0x98 / 4].copy_from_slice(&[
            0x2402002a,
            0x3c1c8000,
            0xaf821010,
            if mode == "rewrite" { 0xaf801000 } else { 0 },
            if mode == "rewrite" {
                0x08000008
            } else {
                0x080003c0
            },
            0,
        ]);
        words[0xa0 / 4..0xb4 / 4]
            .copy_from_slice(&[0x24020063, 0x3c1c8000, 0xaf821010, 0x080003c0, 0]);
        words[0xf00 / 4] = 0x1000ffff;
        words[0x1000 / 4..].copy_from_slice(&[base + 0x80, base + 0xa0]);
        let data = GuestRange {
            start: GuestAddr(base + 0x1000),
            size: 8,
        };
        let mut image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(base),
                image: String::new(),
                generation: 0,
            },
            words,
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
            slots: vec![(data.clone(), data.start.0, 0)],
        };
        image.base.image = image.content_identity();
        let id = "authored-data".to_string();
        let spec = LoadImage {
            base_offset: RomOffset(0),
            base: GuestRange {
                start: GuestAddr(base),
                size: 0x1000,
            },
            loads: vec![DeclaredLoad {
                destination: data,
                source: RomOffset(0),
                encoding: LoadEncoding::AresData {
                    entry: GuestAddr(0x60000020),
                    physical: 0x1000,
                },
                evidence: [id.clone()].into(),
                relocatable: false,
                linked: None,
            }],
        };
        let evidence = BTreeMap::from([(
            id,
            Evidence {
                kind: EvidenceKind::Static,
                producer: "authored first-use data contract".into(),
                revision: "0".into(),
                detail: "synthetic replay output; initial preload contains zero data".into(),
            },
        )]);
        let map = discover_image_with_loads(
            RomIdentity {
                sha256: "b".repeat(64),
                size: 0x2000,
            },
            &image,
            &[image.base.pc],
            &[],
            None,
            Some(&(spec, evidence)),
            1000,
        )
        .unwrap()
        .map;
        let raw: Vec<_> = image.words.iter().flat_map(|w| w.to_be_bytes()).collect();
        let mut preload = image.clone();
        preload.words[0x1000 / 4..].fill(0);
        let code = plaid_lower::lower_c_with_preload(
            &map,
            &[image],
            &preload,
            GuestAddr(base),
            &[GuestAddr(base + 0xf00)],
            false,
        )
        .unwrap();
        std::fs::write(out.join(format!("{mode}.c")), code).unwrap();
        std::fs::write(out.join(format!("{mode}.bin")), raw).unwrap();
    }
}
