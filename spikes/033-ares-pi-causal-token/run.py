"""Verify pinned ares PI/request/queue source and execute the causal-token model."""
from __future__ import annotations

from pathlib import Path
import hashlib
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT / ".refs/ares"
OUT = ROOT / "target/ares-pi-causal-token"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
BLOBS = {
    "ares/n64/n64.hpp": "33a2a973d6026a8a014231f79a8ab9b98998b703",
    "ares/n64/pi/io.cpp": "2a41a8240e96ea3517bfb1fa67748829a900fb84",
    "ares/n64/pi/dma.cpp": "f2bd415495c6d84da779026b61fbe4c9f6ef7c88",
    "ares/n64/cpu/cpu.cpp": "41964d49c8983ae9a97b25625174cd4c4316c4a8",
    "nall/nall/priority-queue.hpp": "17eb754bccdfd075f8dac206d7c0aafd28d01e37",
}
EXPECTED = [
    "PASS straight_completion token=1",
    "PASS busy_reject_no_token records=1",
    "PASS equal_tuple_cancel_restart old=1 new=2 completions=1",
    "PASS interrupt_clear_preserves_request token=1",
    "PASS queue_full_dma_without_event queue_size=512 immediate_dmas=513 rejected_token=513",
    "PASS differential_fuzz seeds=64 ops_per_seed=20000 total_ops=1280000",
    "RESULT PARTIAL: queue-entry token is sufficient for successful insertions but not universal; request identity must predate queue insertion and record insertion failure.",
]
EXPECTED_OUTPUT_SHA256 = "8f49c659443569004ccc17e377988cdac70d17cb33df669f37ac69667c0f0424"


def check_reference() -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip()
    assert head == REV, (head, REV)
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    for rel, expected in BLOBS.items():
        got = subprocess.check_output(["git", "-c", "core.autocrlf=true", "hash-object", rel], cwd=REF, text=True).strip()
        assert got == expected, (rel, got, expected)


def compile_and_run(extra_flags: list[str], name: str) -> str:
    exe = OUT / name
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-pedantic",
        *extra_flags, str(HERE / "probe.cpp"), "-o", str(exe)
    ], check=True)
    env = os.environ.copy()
    if "sanitize" in name:
        env["ASAN_OPTIONS"] = "detect_leaks=1"
    return subprocess.check_output([str(exe)], text=True, env=env, timeout=30)


def worker() -> None:
    check_reference()
    OUT.mkdir(parents=True, exist_ok=True)
    opt = compile_and_run(["-O2"], "probe")
    repeat = subprocess.check_output([str(OUT / "probe")], text=True, timeout=30)
    assert opt == repeat
    assert opt.splitlines() == EXPECTED
    digest = hashlib.sha256(opt.encode()).hexdigest()
    assert digest == EXPECTED_OUTPUT_SHA256, digest

    sanitized = compile_and_run([
        "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"
    ], "probe-sanitize")
    assert sanitized == opt

    (OUT / "result.txt").write_text(opt)
    print(opt, end="")
    print("OUTPUT_SHA256=" + digest)
    print("PASS source_blobs=5 optimized_repeat_equal=true asan_ubsan_equal=true")


if __name__ == "__main__":
    if os.name == "nt":
        wsl = subprocess.check_output([
            "wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()
        ], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", wsl], check=True)
    else:
        worker()
