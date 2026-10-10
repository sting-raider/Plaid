#!/usr/bin/env python3
"""Guard the exact pinned ares source assumptions used by this experiment."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not REF.exists():
        raise SystemExit("missing .refs/ares")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip()
    if actual != REV:
        raise SystemExit(f"ares pin mismatch: {actual} != {REV}")

    exceptions_path = REF / "ares/n64/cpu/exceptions.cpp"
    cpu_path = REF / "ares/n64/cpu/cpu.hpp"
    exceptions = exceptions_path.read_text()
    cpu = cpu_path.read_text()

    required_exception = [
        "u64 vectorBase = !self.scc.status.vectorLocation ? (s32)0x8000'0000 : (s32)0xbfc0'0200;",
        "u16 vectorOffset = 0x0180;",
        "self.pipeline.setPc(vectorBase + vectorOffset);",
        "self.pipeline.exception();",
        "self.context.setMode();",
    ]
    for text in required_exception:
        if exceptions.count(text) != 1:
            raise AssertionError(f"exception source drift: {text}")

    trigger = exceptions.split("auto CPU::Exception::trigger", 1)[1].split("auto CPU::Exception::interrupt", 1)[0]
    if "icache" in trigger.lower() or "cache" in trigger.lower():
        raise AssertionError("exception trigger unexpectedly manipulates cache state")

    required_cache = [
        "auto line(u64 vaddr) -> Line& { return lines[vaddr >> 5 & 0x1ff]; }",
        "if(!line.hit(paddr)) {",
        "line.fill(paddr, cpu);",
        "return line.read(paddr);",
        "return valid() && (tagKey & ~1u) == t;",
        "cpu.busReadBurst<ICache>(tag | index, words);",
    ]
    for text in required_cache:
        if text not in cpu:
            raise AssertionError(f"I-cache source drift: {text}")

    print(
        "PASS"
        f" ares={REV}"
        f" exceptions_sha256={digest(exceptions_path)}"
        f" cpu_hpp_sha256={digest(cpu_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
