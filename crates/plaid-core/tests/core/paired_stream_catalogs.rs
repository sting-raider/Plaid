use flate2::{Compression, write::DeflateEncoder};
use plaid_core::paired_streams::infer;
use std::io::Write;

type Catalog = Vec<(u32, u32)>;

fn stream(data: &[u8]) -> Vec<u8> {
    let mut encoder = DeflateEncoder::new(Vec::new(), Compression::default());
    encoder.write_all(data).unwrap();
    [
        vec![0x11, 0x72],
        (data.len() as u32).to_be_bytes().to_vec(),
        encoder.finish().unwrap(),
    ]
    .concat()
}

fn init(pairs: &[(u32, u32)]) -> Vec<u32> {
    let mut words = vec![0x3c088030, 0x35081200];
    for (i, &(start, end)) in pairs.iter().enumerate() {
        for (offset, value) in [(8 * i as u32, start), (8 * i as u32 + 4, end)] {
            words.extend([
                0x3c090000 | (value >> 16),
                0x35290000 | (value & 0xffff),
                0xad090000 | offset,
            ]);
        }
    }
    words.extend([0x340a1000, 0x03e00008, 0]);
    words
}

fn fixture() -> (Vec<u8>, Catalog, Catalog) {
    let mut rom = vec![0; 0x5000];
    let mut records = Vec::new();
    let mut catalogs = [Vec::new(), Vec::new()];
    let link = 0x80011000u32;
    for i in 0..4u32 {
        let size = 32 + 16 * i;
        for (j, pairs) in catalogs.iter_mut().enumerate() {
            let bytes = [
                stream(&vec![(i + j as u32) as u8; size as usize]),
                stream(&[0; 16]),
            ]
            .concat();
            let start = 0x2000 + j as u32 * 0x1000 + i * 0x100;
            let end = start + bytes.len() as u32;
            rom[start as usize..end as usize].copy_from_slice(&bytes);
            pairs.push((start, end));
        }
        records.extend(
            [
                0,
                link,
                link + size + 32,
                0,
                0,
                link,
                link + size,
                link + size,
                link + size + 16,
                link + size + 16,
                link + size + 32,
            ]
            .into_iter()
            .flat_map(u32::to_be_bytes),
        );
    }
    let metadata = [stream(&[0; 16]), stream(&records)].concat();
    rom[0x1000..0x1000 + metadata.len()].copy_from_slice(&metadata);
    let [first, second] = catalogs;
    (rom, first, second)
}

fn boot(words: Vec<u32>) -> Vec<u8> {
    words.into_iter().flat_map(u32::to_be_bytes).collect()
}

#[test]
fn missing_final_source_pair_must_not_admit_metadata_prefix() {
    let (rom, pairs, _) = fixture();
    assert_eq!(infer(&rom, &boot(init(&pairs))).len(), 4);
    let truncated = infer(&rom, &boot(init(&pairs[..3])));
    assert!(
        truncated.is_empty(),
        "admitted incomplete catalog: {truncated:?}"
    );
}

#[test]
fn malformed_metadata_row_is_rejected_without_panic() {
    let (mut rom, pairs, _) = fixture();
    let (_, used) = plaid_core::paired_streams::stream(&rom[0x1000..]).unwrap();
    let (mut records, _) = plaid_core::paired_streams::stream(&rom[0x1000 + used..]).unwrap();
    records[36..40].copy_from_slice(&0x80012000u32.to_be_bytes());
    let bytes = [stream(&[0; 16]), stream(&records)].concat();
    rom[0x1000..0x1000 + bytes.len()].copy_from_slice(&bytes);
    assert!(infer(&rom, &boot(init(&pairs))).is_empty());
}

#[test]
fn conflicting_initializer_blocks_must_not_silently_choose_last() {
    let (rom, first, second) = fixture();
    assert_eq!(infer(&rom, &boot(init(&first))).len(), 4);
    assert_eq!(infer(&rom, &boot(init(&second))).len(), 4);
    let combined = boot([init(&first), init(&second)].concat());
    let ambiguous = infer(&rom, &combined);
    assert!(
        ambiguous.is_empty(),
        "discarded one valid initializer: {ambiguous:?}"
    );
}

#[test]
fn identical_initializers_agree_but_partial_or_malformed_conflicts_refuse() {
    let (rom, first, second) = fixture();
    let expected = infer(&rom, &boot(init(&first)));
    assert_eq!(expected.len(), 4);
    assert_eq!(
        infer(&rom, &boot([init(&first), init(&first)].concat())),
        expected
    );
    for mut partial in [vec![second[0]], vec![(0x4fff, 0x5000)]] {
        assert!(infer(&rom, &boot([init(&first), init(&partial)].concat())).is_empty());
        partial[0] = first[0];
        assert_eq!(
            infer(&rom, &boot([init(&first), init(&partial)].concat())),
            expected
        );
    }
}

#[test]
fn conflicting_store_in_one_block_is_retained_for_refusal() {
    let (rom, first, second) = fixture();
    let mut words = init(&first);
    words.truncate(words.len() - 3);
    words.extend([
        0x3c090000 | second[0].0 >> 16,
        0x35290000 | second[0].0 & 0xffff,
        0xad090000,
    ]);
    words.extend([0x340a1000, 0x03e00008, 0]);
    assert!(infer(&rom, &boot(words)).is_empty());
}

#[test]
fn missing_first_source_pair_must_not_admit_metadata_suffix() {
    let (rom, pairs, _) = fixture();
    assert!(infer(&rom, &boot(init(&pairs[1..]))).is_empty());
}
