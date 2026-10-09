#!/usr/bin/env python3
"""Guard the exact pinned ares source surfaces used by this experiment."""
from pathlib import Path
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def require(text: str, needle: str, count: int = 1) -> None:
    actual = text.count(needle)
    assert actual == count, (needle, actual, count)


def main() -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip()
    assert head == REV, (head, REV)
    assert subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=REF).returncode == 0

    fpu_path = REF / "ares/n64/cpu/interpreter-fpu.cpp"
    fpu = fpu_path.read_text()
    require(fpu, """auto CPU::LDC1(u8 ft, cr64& rs, s16 imm) -> void {
  if(!scc.status.enable.coprocessor1) return exception.coprocessor1();
  if(auto data = read<Dual>(rs.u64 + imm)) FT(u64) = *data;
}""")
    require(fpu, """auto CPU::LWC1(u8 ft, cr64& rs, s16 imm) -> void {
  if(!scc.status.enable.coprocessor1) return exception.coprocessor1();
  if(auto data = read<Word>(rs.u64 + imm)) FT(u32) = *data;
}""")
    require(fpu, """auto CPU::MTC1(cr64& rt, u8 ft) -> void {
  if(!scc.status.enable.coprocessor1) return exception.coprocessor1();
  FT(s32) = rt.u32;
}""")
    require(fpu, """auto CPU::DMTC1(cr64& rt, u8 fs) -> void {
  if(!scc.status.enable.coprocessor1) return exception.coprocessor1();
  FS(u64) = rt.u64;
}""")
    require(fpu, """auto CPU::SWC1(u8 ft, cr64& rs, s16 imm) -> void {
  if(!scc.status.enable.coprocessor1) return exception.coprocessor1();
  write<Word>(rs.u64 + imm, FT(u32));
}""")
    require(fpu, """auto CPU::SDC1(u8 ft, cr64& rs, s16 imm) -> void {
  if(!scc.status.enable.coprocessor1) return exception.coprocessor1();
  write<Dual>(rs.u64 + imm, FT(u64));
}""")
    require(fpu, "else if(index & 1) {\n    return fpu.r[index & ~1].s32h;")
    require(fpu, "return fpu.r[index & ~1].s64;")

    rdram_path = REF / "ares/n64/rdram/rdram.hpp"
    rdram = rdram_path.read_text()
    require(rdram, "      return Memory::Writable::read<Size>(address);")
    require(rdram, "      self.hidden.update<Size>(address, value);")

    digest = hashlib.sha256(fpu_path.read_bytes() + b"\0" + rdram_path.read_bytes()).hexdigest()
    print("PASS: exact pinned ares COP1/RDRAM source guards")
    print("source_pair_sha256=" + digest)


if __name__ == "__main__":
    main()
