#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/plaid-core/src/program.rs")
text = path.read_text()
needle = '''            refs(&l.evidence)?;
            if let Some(copy) = &l.copy_event
'''
replacement = '''            refs(&l.evidence)?;
            if !self.regions.iter().any(|r| {
                r.image == l.image
                    && r.generation == l.generation
                    && r.range == l.destination
                    && r.rom_offset == Some(l.rom_offset)
            }) {
                return Err("load has no matching executable region".into());
            }
            if let Some(copy) = &l.copy_event
'''

if replacement in text:
    print("candidate fix already applied")
elif text.count(needle) != 1:
    raise SystemExit(f"expected exactly one validation anchor, found {text.count(needle)}")
else:
    path.write_text(text.replace(needle, replacement))
    print("applied candidate load-region binding guard")
