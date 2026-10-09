#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/plaid-core/src/program.rs")
text = path.read_text()
needle = """            if let Some(o) = r.rom_offset {\n                rom_range(o, r.range.size)?;\n            }\n"""
insert = """            if let Some(o) = r.rom_offset {\n                rom_range(o, r.range.size)?;\n            }\n            if let Some(physical) = r.physical_start\n                && u64::from(physical.0) + u64::from(r.range.size) > 1u64 << 32\n            {\n                return Err(\"region physical span overflow\".into());\n            }\n"""
if insert in text:
    print("candidate fix already present")
    raise SystemExit(0)
if text.count(needle) != 1:
    raise SystemExit("expected unique Region ROM-range validation anchor")
path.write_text(text.replace(needle, insert))
print("applied Region physical-span overflow validation")
