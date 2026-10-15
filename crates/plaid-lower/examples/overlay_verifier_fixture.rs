//! Synthetic native verifier contract; no ROM or reference game bytes.
use plaid_core::overlays::Layout;

fn main() {
    let mut words: Vec<u32> = vec![
        0x3c088080, 0x3c098080, 0x25080030, 0x25290034, 0x250a0038, 0x0c20000a, 0x03e00008, 0,
        0x3c0b0600, 0x256b1234, 0x03e00008, 0, 0x80800034, 0x06001234, 0, 0,
    ];
    words.extend([
        48, 16, 0, 16, 10, 0x45000000, 0x45000004, 0x46000008, 0x4600000c, 0x46000010, 0x44000014,
        0x45000020, 0x46000024, 0x82000000, 0x82000004, 64,
    ]);
    let bytes: Vec<u8> = words.into_iter().flat_map(u32::to_be_bytes).collect();
    let layout = Layout::parse(&bytes).unwrap();
    let mut c = String::from(
        "#include <stdlib.h>\nstatic int fail_alloc;\nstatic void *test_alloc(size_t n) { return fail_alloc ? NULL : malloc(n); }\n#define malloc test_alloc\n",
    );
    c += &plaid_lower::overlay::verifier(&bytes, 0x80800000, 7).unwrap();
    // Multiple generated verifiers must coexist in one translation unit.
    c += &plaid_lower::overlay::verifier(&bytes, 0x80800000, 8).unwrap();
    let data_only: Vec<u8> = [0u32, 0, 0, 1, 0, 24]
        .into_iter()
        .flat_map(u32::to_be_bytes)
        .collect();
    c += &plaid_lower::overlay::verifier(&data_only, 0x80800000, 9).unwrap();
    c += "#include <assert.h>\nstatic uint8_t ram[0x800000];\nint main(void) { size_t i;\n";
    for base in [
        0x80000000u32,
        0x80001000,
        0x80017ff0,
        0x803fffe0,
        0x807fff70,
    ] {
        let expected = layout.relocate(&bytes, 0x80800000, base).unwrap();
        let word = |at| u32::from_be_bytes(expected[at..at + 4].try_into().unwrap());
        assert_eq!(word(0), 0x3c080000 | ((base + 56 + 0x8000) >> 16));
        assert_eq!(word(4), 0x3c090000 | ((base + 52 + 0x8000) >> 16));
        assert_eq!(word(8), 0x25080000 | ((base + 48) & 0xffff));
        assert_eq!(word(16), 0x250a0000 | ((base + 56) & 0xffff));
        assert_eq!(word(20), 0x0c000000 | (((base + 40) & 0x0fffffff) >> 2));
        assert_eq!(word(32), 0x3c0b0600);
        assert_eq!(word(36), 0x256b1234);
        assert_eq!(word(48), base + 52);
        assert_eq!(word(52), 0x06001234);
        c += &format!(
            "{{ static const uint8_t expected[] = {{{}}}; size_t p = {}u;\nmemcpy(ram + p, expected, sizeof expected);\n",
            expected
                .iter()
                .map(u8::to_string)
                .collect::<Vec<_>>()
                .join(","),
            base - 0x80000000
        );
        c += &format!(
            "assert(plaid_overlay_verify_7(ram, sizeof ram, 0x{base:08x}u));\n\
assert(plaid_overlay_verify_8(ram, sizeof ram, 0x{base:08x}u));\n\
fail_alloc = 1; assert(!plaid_overlay_verify_7(ram, sizeof ram, 0x{base:08x}u)); fail_alloc = 0;\n\
assert(!plaid_overlay_verify_7(ram, p + sizeof expected - 1, 0x{base:08x}u));\n\
for (i = 0; i < sizeof expected; i++) {{ ram[p+i] ^= 1; assert(!plaid_overlay_verify_7(ram, sizeof ram, 0x{base:08x}u)); ram[p+i] ^= 1; }}\n\
assert(memcmp(ram + p, expected, sizeof expected) == 0);\n}}\n"
        );
    }
    c += &format!(
        "{{ static const uint8_t data[] = {{{}}}; memcpy(ram, data, sizeof data); ram[sizeof data] = 0; assert(plaid_overlay_verify_9(ram, sizeof ram, 0x80000000u)); ram[sizeof data] = 1; assert(!plaid_overlay_verify_9(ram, sizeof ram, 0x80000000u)); }}\n",
        data_only
            .iter()
            .map(u8::to_string)
            .collect::<Vec<_>>()
            .join(",")
    );
    c += "assert(!plaid_overlay_verify_7(NULL, sizeof ram, 0x80000000u));\n\
assert(!plaid_overlay_verify_7(ram, sizeof ram, 0x7ffffffcu));\n\
assert(!plaid_overlay_verify_7(ram, sizeof ram, 0x80000001u));\n\
assert(!plaid_overlay_verify_7(ram, sizeof ram, 0x807ffffcu));\n\
assert(!plaid_overlay_verify_7(ram, sizeof ram, 0xa0000000u));\nreturn 0; }\n";
    print!("{c}");
}
