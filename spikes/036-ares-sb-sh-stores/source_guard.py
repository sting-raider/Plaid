#!/usr/bin/env python3
"""Guard the exact pinned ares source contracts used by the SB/SH spike."""
from pathlib import Path
import hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

CONTRACTS = {
    "ares/n64/cpu/interpreter-ipu.cpp": [
        "auto CPU::SB(cr64& rt, cr64& rs, s16 imm) -> void {\n  write<Byte>(rs.u64 + imm, rt.u32);",
        "auto CPU::SH(cr64& rt, cr64& rs, s16 imm) -> void {\n  write<Half>(rs.u64 + imm, rt.u32);",
    ],
    "ares/n64/cpu/memory.cpp": [
        "if (raiseAlignedError && vaddrAlignedError<Size>(vaddr, Dir == Write))",
        "if constexpr(Size == Byte) return paddr ^ 7;",
        "if constexpr(Size == Half) return paddr ^ 6;",
        "if(access.cache) return dcache.write<Size>(access.vaddr, paddr, data), true;",
        "return busWrite<Size>(paddr, data), true;",
    ],
    "ares/n64/cpu/dcache.cpp": [
        "dirty |= ((1 << Size) - 1) << (paddr & 0xF);",
        "template<u32 Size>\nauto CPU::DataCache::write(u64 vaddr, u32 paddr, u64 data) -> void {",
    ],
    "ares/n64/rdram/rdram.hpp": [
        "template<u32 Size>\n    auto write(u32 address, u64 value, RBusDevice device) -> void {",
        "self.hidden.update<Size>(address, value);",
    ],
    "ares/n64/memory/lsb/writable.hpp": [
        "if constexpr(Size == Byte) *(u8* )&data[address & maskByte ^ 3] = value;",
        "if constexpr(Size == Half) *(u16*)&data[address & maskHalf ^ 2] = value;",
    ],
}


def main() -> None:
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    out = {"revision": REV, "files": {}}
    for rel, needles in CONTRACTS.items():
        path = REF / rel
        data = path.read_bytes()
        text = data.decode()
        for needle in needles:
            assert text.count(needle) == 1, (rel, needle, text.count(needle))
        out["files"][rel] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "contracts": len(needles),
        }
    encoded = json.dumps(out, sort_keys=True, separators=(",", ":"))
    print(encoded)
    print("source_guard_sha256=" + hashlib.sha256(encoded.encode()).hexdigest())


if __name__ == "__main__":
    main()
