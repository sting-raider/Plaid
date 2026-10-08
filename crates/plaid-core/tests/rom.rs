use plaid_core::rom::*;

#[test]
fn all_orders_have_identical_canonical_bytes_identity_and_header() {
    let mut z = vec![0; 4096];
    z[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    z[8..12].copy_from_slice(&0x80000400u32.to_be_bytes());
    z[16..20].copy_from_slice(&0x12345678u32.to_be_bytes());
    z[32..36].copy_from_slice(b"TEST");
    z[59..64].copy_from_slice(&[b'N', b'P', b'D', b'E', 2]);
    let mut v = z.clone();
    for p in v.as_chunks_mut::<2>().0 {
        p.swap(0, 1);
    }
    let mut n = z.clone();
    for p in n.as_chunks_mut::<4>().0 {
        p.reverse();
    }
    let a = CanonicalRom::from_bytes(&z).unwrap();
    for (bytes, order) in [(v, ByteOrder::ByteSwapped), (n, ByteOrder::WordReversed)] {
        let b = CanonicalRom::from_bytes(&bytes).unwrap();
        assert_eq!(a.bytes(), b.bytes());
        assert_eq!(a.identity, b.identity);
        assert_eq!(a.header, b.header);
        assert_eq!(b.source_order, order);
    }
    assert_eq!(a.header.entry.0, 0x80000400);
    assert_eq!(a.header.crc1, 0x12345678);
    assert_eq!(a.header.cartridge_id, *b"PD");
    assert_eq!(a.header.country, b'E');
    assert_eq!(a.header.version, 2);
}

#[test]
fn malformed_and_incomplete_roms_are_errors() {
    for bytes in [
        vec![],
        vec![0; 63],
        vec![0; 64],
        vec![0x80, 0x37, 0x12, 0x40],
    ] {
        assert!(CanonicalRom::from_bytes(&bytes).is_err());
    }
    let mut bytes = vec![0; 65];
    bytes[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
    assert!(CanonicalRom::from_bytes(&bytes).is_err());
}

#[test]
fn hash_matches_published_sha256_test_vector() {
    assert_eq!(
        sha256(b"abc"),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    );
}
