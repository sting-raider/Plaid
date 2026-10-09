#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/plaid-core/src/program.rs")
text = path.read_text()
needle = '''        for d in &self.dma_observations {\n            rom_range(d.rom_offset, d.size)?;\n            refs(&d.evidence)?;\n            if u64::from(d.physical_destination.0) + u64::from(d.size) > 1u64 << 32 {\n                return Err("DMA destination overflow".into());\n            }\n        }\n        for o in &self.indirect_observations {\n'''
replacement = '''        for d in &self.dma_observations {\n            rom_range(d.rom_offset, d.size)?;\n            refs(&d.evidence)?;\n            if u64::from(d.physical_destination.0) + u64::from(d.size) > 1u64 << 32 {\n                return Err("DMA destination overflow".into());\n            }\n        }\n        // A copy_event is the identity of one observed DMA transaction, even\n        // when one transfer covers several executable subranges. Equivalent\n        // observations may accumulate provenance, but one event cannot name\n        // incompatible source/destination/extent tuples.\n        for load in &self.loads {\n            if let Some(copy) = &load.copy_event {\n                let mut transactions = self\n                    .dma_observations\n                    .iter()\n                    .filter(|d| d.evidence.contains(copy))\n                    .map(|d| (d.rom_offset, d.physical_destination, d.size));\n                if let Some(first) = transactions.next()\n                    && transactions.any(|transaction| transaction != first)\n                {\n                    return Err("load copy event has conflicting observed DMA identity".into());\n                }\n            }\n        }\n        for o in &self.indirect_observations {\n'''
if replacement in text:
    print("candidate fix already applied")
    raise SystemExit(0)
if text.count(needle) != 1:
    raise SystemExit(f"expected exactly one patch site, found {text.count(needle)}")
path.write_text(text.replace(needle, replacement))
print("applied DMA copy-event uniqueness candidate fix")
