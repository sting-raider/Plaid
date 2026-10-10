from pathlib import Path

path = Path("crates/plaid-core/src/program.rs")
text = path.read_text()
old = '''            if let Some(o) = &r.overlay
                && self.overlays.get(o).is_none_or(|x| x.image != r.image)
            {
                return Err("unknown or mismatched overlay".into());
            }
'''
new = '''            if let Some(o) = &r.overlay
                && self.overlays.get(o).is_none_or(|x| {
                    x.image != r.image
                        || r.rom_offset != Some(x.rom_offset)
                        || r.range.start != x.load_address
                        || r.range.size != x.size
                })
            {
                return Err("unknown or mismatched overlay".into());
            }
'''
if old not in text:
    if new in text:
        raise SystemExit(0)
    raise SystemExit("expected overlay validator snippet not found")
path.write_text(text.replace(old, new, 1))
