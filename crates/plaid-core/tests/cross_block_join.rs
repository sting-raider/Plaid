use plaid_core::{GuestAddr, discovery::*, indirect::*, program::*};

fn image(words: Vec<u32>) -> CodeImage {
    CodeImage {
        base: CodeAddress {
            pc: GuestAddr(0x80000000),
            image: "cross-block-join".into(),
            generation: 0,
        },
        words,
        rom_offset: None,
        physical_start: None,
    }
}

fn map(i: &CodeImage) -> ProgramMap {
    direct_cfg(
        RomIdentity {
            sha256: "a".repeat(64),
            size: 4096,
        },
        i,
        &[i.base.pc],
        256,
    )
    .unwrap()
    .map
}

fn diamond(right_imm: u16) -> CodeImage {
    image(vec![
        0x3c088000,             // lui   t0,0x8000
        0x15200004,             // bnez  t1,right
        0x00000000,             // nop
        0x35080040,             // ori   t0,t0,0x40   (left)
        0x0800000a,             // j     join
        0x00000000,             // nop
        0x35080000 | u32::from(right_imm), // ori t0,t0,right_imm
        0x0800000a,             // j     join
        0x00000000,             // nop
        0x00000000,             // padding
        0x01000008,             // join: jr t0
        0x00000000,             // nop
    ])
}

#[test]
fn baseline_equal_two_predecessor_join_is_not_certified() {
    let i = diamond(0x0040);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = m.indirect_sites.first().unwrap();
    assert_eq!(s.site.pc.0, 0x80000028);
    assert!(s.closed_proof.is_none());
    assert!(s.candidates.is_empty());
}

#[test]
fn divergent_two_predecessor_join_is_not_certified() {
    let i = diamond(0x0080);
    let m = analyze_indirect(&map(&i), &i).unwrap();
    let s = m.indirect_sites.first().unwrap();
    assert!(s.closed_proof.is_none());
    assert!(s.candidates.is_empty());
}
