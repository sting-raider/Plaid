#!/usr/bin/env python3
"""Independent pinned Gopher64 source guard for bounded RSP lane semantics."""
from pathlib import Path
import json
import subprocess
import sys

REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
PATH = "src/device/rsp_su_instructions.rs"
BLOB = "4afc4c9886bf85759e12f61769acbe84a7e33898"


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".refs/gopher64").resolve()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    assert head == REV, (head, REV)
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=root, check=True)
    got = subprocess.check_output(["git", "hash-object", PATH], cwd=root, text=True).strip()
    assert got == BLOB, (got, BLOB)
    text = (root / PATH).read_text(encoding="utf-8")

    snippets = [
        "pub fn lqv(device: &mut device::Device, opcode: u32)",
        "let end = std::cmp::min(16 + element - ((address & 15) as u8), 16);",
        "pub fn lrv(device: &mut device::Device, opcode: u32)",
        "let mut element = 16u8.wrapping_sub(((address & 15) as u8).wrapping_sub(velement(opcode)));",
        "address &= !15;",
        "pub fn sqv(device: &mut device::Device, opcode: u32)",
        "let end = element + (16 - (address & 15)) as u8;",
        "pub fn srv(device: &mut device::Device, opcode: u32)",
        "let end = element + (address & 15) as u8;",
        "let base = (16 - (address & 15)) as u8;",
        "pub fn mtc2(device: &mut device::Device, opcode: u32)",
        "if velement(opcode) != 15 {",
    ]
    missing = [snippet for snippet in snippets if snippet not in text]
    assert not missing, missing
    print(json.dumps({
        "revision": head,
        "path": PATH,
        "blob": got,
        "lqv_lrv_sqv_srv_lane_formulas_correspond": True,
        "mtc2_two_byte_clobber_corresponds": True,
        "note": "source corroboration only; not independent execution or hardware truth",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
