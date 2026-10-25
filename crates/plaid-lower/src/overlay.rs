//! First-entry byte checks for relocatable images (ADR-0172).
//! This emits a verifier, not permission to execute an unclosed overlay.
use plaid_core::overlays::Layout;

/// Emit `plaid_overlay_verify_ID(ram, ram_size, load_address)`, returning one
/// only when RAM contains the entire relocated file and its zeroed BSS.
/// The caller must run it before granting an executable binding. Subsequent
/// data writes are allowed; executable writes must revoke that binding.
///
/// Relocation sites and opcodes are resolved at compile time. Generated code
/// patches expected bytes, never guest RAM, and contains no guest decoder.
/// `compared` bytes from the start are checked: the whole file, or a slot
/// alternate's text (ADR-0185), whose data is the game's to write and which
/// lowered code reads from RAM.
pub fn verifier(
    bytes: &[u8],
    layout: &Layout,
    compared: usize,
    link: u32,
    id: u32,
) -> Result<String, String> {
    verifier_guarded(bytes, layout, compared, link, id, &[])
}

/// Also compare noncontiguous data ranges whose values justify native dispatch.
/// These ranges are protected alongside text after a successful binding.
pub fn verifier_guarded(
    bytes: &[u8],
    layout: &Layout,
    compared: usize,
    link: u32,
    id: u32,
    guarded: &[(u32, u32)],
) -> Result<String, String> {
    let text = (layout.text > 0).then_some((0, layout.text));
    verifier_text_ranges(bytes, layout, compared, link, id, text.as_slice(), guarded)
}

/// Compare every emitted instruction range and immutable dispatch input. A slot's
/// candidate extent may also contain mutable data before or between functions.
/// The lowerer supplies all emitted blocks; gaps never authorize native entry.
pub(crate) fn verifier_text_ranges(
    bytes: &[u8],
    layout: &Layout,
    compared: usize,
    link: u32,
    id: u32,
    text_ranges: &[(u32, u32)],
    guarded: &[(u32, u32)],
) -> Result<String, String> {
    if text_ranges.iter().any(|&(start, end)| {
        start >= end || !start.is_multiple_of(4) || !end.is_multiple_of(4) || end > layout.text
    }) {
        return Err("overlay instruction range lies outside its text".into());
    }
    if guarded.iter().any(|&(start, end)| {
        start >= end
            || !start.is_multiple_of(4)
            || !end.is_multiple_of(4)
            || end as usize > bytes.len()
    }) {
        return Err("overlay guarded data lies outside its source".into());
    }
    if compared < layout.text as usize || compared == 0 || compared > bytes.len() {
        return Err("overlay verifier must compare all executable text within its source".into());
    }
    // Validate encodings, pairs and targets through the canonical model.
    layout.apply(bytes, link, 0x80000000)?;
    let span = layout.file_size + layout.bss;
    let end = link.checked_add(span).ok_or("overlay link overflow")?;
    let words: Vec<u32> = bytes
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| u32::from_be_bytes(*w))
        .collect();
    let get = format!("plaid_overlay_get_{id}");
    let put = format!("plaid_overlay_put_{id}");
    let mut out = format!(
        "#include <stdint.h>\n#include <stddef.h>\n#include <stdlib.h>\n#include <string.h>\n\
static inline uint32_t {get}(const uint8_t *p) {{ return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3]; }}\n\
static inline void {put}(uint8_t *p, uint32_t w) {{ p[0] = (uint8_t)(w >> 24); p[1] = (uint8_t)(w >> 16); p[2] = (uint8_t)(w >> 8); p[3] = (uint8_t)w; }}\n\
int plaid_overlay_verify_{id}(const uint8_t *ram, size_t ram_size, uint32_t base) {{\n\
  static const uint32_t source[] = {{{}}};\n\
  uint8_t *expected; size_t p, i; uint32_t delta; int valid = 1;\n\
  if (!ram || (base & 3u) || base < 0x80000000u || base > 0x{:08x}u) return 0;\n\
  p = base - 0x80000000u;\n\
  if (p > ram_size || {span}u > ram_size - p) return 0;\n\
  expected = (uint8_t *)malloc({}u); if (!expected) return 0;\n\
  for (i = 0; i < sizeof source / sizeof source[0]; i++) {put}(expected + 4 * i, source[i]);\n\
  delta = base - 0x{link:08x}u; (void)delta;\n",
        words
            .iter()
            .map(|w| format!("0x{w:08x}u"))
            .collect::<Vec<_>>()
            .join(","),
        0x80800000 - span,
        bytes.len(),
    );
    let mut highs = [None; 32];
    for r in &layout.relocations {
        let at = r.offset;
        let w = words[at as usize / 4];
        match r.kind {
            2 if w & 0x0f000000 != 0 => {}
            2 => out += &format!("  {put}(expected + {at}, 0x{w:08x}u + delta);\n"),
            4 => {
                let target = 0x80000000 | ((w & 0x03ffffff) << 2);
                out += &format!(
                    "  {put}(expected + {at}, 0x{:08x}u | (((0x{target:08x}u + delta) & 0x0fffffffu) >> 2));\n",
                    w & 0xfc000000
                );
            }
            5 => highs[((w >> 16) & 31) as usize] = Some((at, w)),
            6 => {
                let (hi, original) =
                    highs[((w >> 21) & 31) as usize].ok_or("LO16 lacks register-matched HI16")?;
                let low = w as u16 as i16 as i32 as u32;
                let target = original.wrapping_shl(16).wrapping_add(low);
                // A reused HI observes its previous patch for the segmented
                // pointer test, but reconstructs the target from the original HI.
                out += &format!(
                    "  if (((({get}(expected + {hi}) << 16) + 0x{low:08x}u) & 0x0f000000u) == 0) {{\n"
                );
                if !(link..=end).contains(&target) {
                    out += "    free(expected); return 0;\n";
                } else {
                    out += &format!(
                        "    uint32_t v = 0x{target:08x}u + delta;\n    {put}(expected + {hi}, 0x{:08x}u | ((v + 0x8000u) >> 16));\n    {put}(expected + {at}, 0x{:08x}u | (v & 0xffffu));\n",
                        original & 0xffff0000,
                        w & 0xffff0000
                    );
                }
                out += "  }\n";
            }
            _ => return Err("unsupported overlay relocation".into()),
        }
    }
    for &(start, end) in guarded {
        out += &format!(
            "  if (memcmp(ram + p + {start}u, expected + {start}u, {}u)) valid = 0;\n",
            end - start
        );
    }
    for &(start, end) in text_ranges {
        out += &format!(
            "  if (memcmp(ram + p + {start}u, expected + {start}u, {}u)) valid = 0;\n",
            end - start
        );
    }
    // Non-slot images retain their complete initialized-file comparison.
    if compared > layout.text as usize {
        out += &format!("  if (memcmp(ram + p, expected, {compared}u)) valid = 0;\n");
    }
    out += &format!(
        "  free(expected);\n  for (i = {}u; valid && i < {span}u; i++) if (ram[p + i]) valid = 0;\n  return valid;\n}}\n",
        bytes.len()
    );
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn verifier_cannot_skip_text_or_read_past_its_source() {
        let layout = Layout {
            text: 8,
            data: 4,
            rodata: 0,
            bss: 0,
            file_size: 12,
            relocations: vec![],
        };
        for compared in [0, 4, 7, 13] {
            assert!(verifier(&[0; 12], &layout, compared, 0x80000000, 0).is_err());
        }
        for compared in [8, 12] {
            assert!(verifier(&[0; 12], &layout, compared, 0x80000000, 0).is_ok());
        }
        for guarded in [vec![(8, 16)], vec![(8, 8)], vec![(9, 12)]] {
            assert!(verifier_guarded(&[0; 12], &layout, 8, 0x80000000, 0, &guarded).is_err());
        }
        assert!(verifier_guarded(&[0; 12], &layout, 8, 0x80000000, 0, &[(8, 12)]).is_ok());
        for ranges in [vec![(0, 12)], vec![(4, 4)], vec![(1, 8)], vec![(0, 7)]] {
            assert!(
                verifier_text_ranges(&[0; 12], &layout, 8, 0x80000000, 0, &ranges, &[]).is_err()
            );
        }
    }
}
