#!/usr/bin/env python3
"""Guard the exact pinned ares source contract used by the egress witness."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
EXPECTED = {
    "ares/n64/rsp/dma.cpp": "b5d8a1c4b45c2d84c487d98725caa465ac4b5fbea4761beff51ca1a1ba93d7b6",
    "ares/n64/rsp/io.cpp": "60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860",
    "ares/n64/rdram/rdram.hpp": "6a77c2fa0bbb320ff6b2855ea6379541a67096bed6b91cc6cd2697584112b1cf",
}
EXTRA_HASHED = (
    "ares/n64/memory/memory.hpp",
    "ares/n64/memory/lsb/writable.hpp",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check() -> dict:
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    hashes = {name: sha(REF / name) for name in (*EXPECTED, *EXTRA_HASHED)}
    assert {name: hashes[name] for name in EXPECTED} == EXPECTED

    dma = (REF / "ares/n64/rsp/dma.cpp").read_text(encoding="utf-8")
    fragment = """      } else {
        u32 dataLo = dmem.read<Word>(dma.current.pbusAddress + 0);
        u32 dataHi = dmem.read<Word>(dma.current.pbusAddress + 4);
        rdram.ram.write<Word>(dma.current.dramAddress + 0, dataLo, RBusDevice::SP_DMA);
        rdram.ram.write<Word>(dma.current.dramAddress + 4, dataHi, RBusDevice::SP_DMA);
      }
      dma.current.dramAddress += 8;
      dma.current.pbusAddress += 8;"""
    assert dma.count(fragment) == 1
    assert dma.count("if(dma.current.count) {") == 1
    assert dma.count("dma.current.dramAddress += dma.current.skip;") == 1

    io = (REF / "ares/n64/rsp/io.cpp").read_text(encoding="utf-8")
    write_length = """  if(address == 3) {
    //SP_WRITE_LENGTH
    dma.pending.length.bit(3,11) = data.bit( 3,11);
    dma.pending.count            = data.bit(12,19);
    dma.pending.skip.bit(3,11)   = data.bit(23,31);"""
    assert io.count(write_length) == 1
    assert io.count("dma.full.write = 1;") == 1
    assert io.count("dmaTransferStart(thread);") == 2

    rdram = (REF / "ares/n64/rdram/rdram.hpp").read_text(encoding="utf-8")
    completed = """      Memory::Writable::write<Size>(address, value);
      self.hidden.update<Size>(address, value);"""
    assert rdram.count(completed) == 1
    assert rdram.count("if(address >= size) return;") >= 2

    memory = (REF / "ares/n64/memory/memory.hpp").read_text(encoding="utf-8")
    assert memory.count('#include "lsb/readable.hpp"') == 1
    assert memory.count('#include "lsb/writable.hpp"') == 1

    lsb = (REF / "ares/n64/memory/lsb/writable.hpp").read_text(encoding="utf-8")
    assert lsb.count("address & maskByte ^ 3") == 2
    assert lsb.count("address & maskHalf ^ 2") == 2
    assert lsb.count("address & maskWord ^ 0") == 2
    assert "if constexpr(Size == Word) *(u32*)&data[address & maskWord ^ 0] = value;" in lsb

    return {"revision": REV, "sha256": hashes, "n64_memory_layout": "lsb-byte-xor3"}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
    print("PASS exact pinned SP write-DMA, identity-RDRAM, and logical-byte layout source contract")
