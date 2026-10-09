#!/usr/bin/env python3
"""Guard exact pinned ares RSP vector memory/dataflow source used by this spike."""
from pathlib import Path
import json
import subprocess
import sys

REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
BLOBS = {
    "ares/n64/rsp/interpreter-vpu.cpp": "b30d62f63efee6c2287e48637d079eadcba95565",
    "ares/n64/rsp/decoder.cpp": "d3796649659a960d653ecbc739b14277b8c5a7f2",
    "ares/n64/rsp/interpreter.cpp": "cb5940f968efa563c5acf1dd6ed11ff9e6751124",
}


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".refs/ares").resolve()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    assert head == REV, (head, REV)
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=root, check=True)

    observed = {}
    for rel, expected in BLOBS.items():
        got = subprocess.check_output(["git", "hash-object", rel], cwd=root, text=True).strip()
        assert got == expected, (rel, got, expected)
        observed[rel] = got

    vpu = (root / "ares/n64/rsp/interpreter-vpu.cpp").read_text(encoding="utf-8")
    decoder = (root / "ares/n64/rsp/decoder.cpp").read_text(encoding="utf-8")
    interpreter = (root / "ares/n64/rsp/interpreter.cpp").read_text(encoding="utf-8")
    header = (root / "ares/n64/rsp/rsp.hpp").read_text(encoding="utf-8")

    snippets = [
        "auto RSP::LQV(r128& vt, cr32& rs, s8 imm) -> void",
        "auto end = min(16 + e - (address & 15), 16);",
        "auto RSP::LRV(r128& vt, cr32& rs, s8 imm) -> void",
        "auto start = 16 - ((address & 15) - index);",
        "auto RSP::SQV(cr128& vt, cr32& rs, s8 imm) -> void",
        "auto end = start + (16 - (address & 15));",
        "auto RSP::SRV(cr128& vt, cr32& rs, s8 imm) -> void",
        "auto base = 16 - (address & 15);",
        "auto RSP::MTC2(cr32& rt, r128& vs) -> void",
        "if (e != 15) vs.byte(e + 1) = rt.u32 >> 0;",
    ]
    for snippet in snippets:
        assert snippet in vpu, snippet

    for snippet in [
        "op(0x04, LQV, VDef(VT), RUse(RS), Load, UsesDmem);",
        "op(0x05, LRV, VDef(VT), RUse(RS), Load, UsesDmem);",
        "op(0x04, SQV, VUse(VT), RUse(RS), Store, UsesDmem);",
        "op(0x05, SRV, VUse(VT), RUse(RS), Store, UsesDmem);",
        "op(0x04, MTC2, RUse(RT), VDef(VS), Load, Store, VNopGroup);",
    ]:
        assert snippet in decoder, snippet

    for snippet in [
        "#define E     (OP >> 7 & 15)",
        "vu(0x04, LQV, VT, RS, IMMi7);",
        "vu(0x05, LRV, VT, RS, IMMi7);",
        "vu(0x04, SQV, VT, RS, IMMi7);",
        "vu(0x05, SRV, VT, RS, IMMi7);",
        "vu(0x04, MTC2, RT, VS);",
    ]:
        assert snippet in interpreter, snippet

    assert "data[address & maskByte]" in header
    print(json.dumps({
        "revision": head,
        "blobs": observed,
        "byte_backing_wrap_guard": True,
        "vector_load_store_source_guard": True,
        "decoder_guard": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
