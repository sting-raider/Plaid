"""Build exact pinned ares and execute the cached code-patch visibility fixture."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
OUT = ROOT / "target/ares-cached-code-patch-visibility"
SOURCE_BLOBS = {
    "ares/n64/cpu/cpu.hpp": "b51000d99e1e8818ad04a8c747a8170b0e98fae8",
    "ares/n64/cpu/dcache.cpp": "4de28e0ad9566d31f47210a997c22fa994785d26",
    "ares/n64/cpu/memory.cpp": "f362ef67ab41ccf57330bbedd6f614e07a61dd17",
    "ares/n64/cpu/interpreter-ipu.cpp": "938ccbd0af1f127439d9859c1fd6be2bbd5222a3",
    "ares/n64/rdram/rdram.hpp": "c718ec2e9b2a78610353562cbc81dd973b278ee2",
}


def source_guard():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    for path, expected in SOURCE_BLOBS.items():
        actual = subprocess.check_output(["git", "hash-object", path], cwd=REF, text=True).strip()
        assert actual == expected, (path, actual, expected)


def build():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.build(HERE / "driver.cpp", OUT)


def run():
    source_guard()
    exe = build()
    raw1 = subprocess.check_output([str(exe)], text=True, timeout=30)
    raw2 = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert raw1 == raw2
    facts = json.loads(raw1)
    assert facts["after_store_fetch"] == 1
    assert facts["after_writeback_fetch"] == 1
    assert facts["after_refill_fetch"] == 2
    assert facts["backing_word"] == 0x24020002
    assert facts["icache_word"] == 0x24020002
    assert facts["dcache_word"] == 0x24020002
    assert facts["dcache_dirty"] == 0
    assert facts["dcache_writebacks"] == 1
    assert facts["exception"] == 0
    canonical = json.dumps(facts, sort_keys=True, separators=(",", ":"))
    print("EVIDENCE_SHA256=" + hashlib.sha256(canonical.encode()).hexdigest())
    print("EVIDENCE_JSON=" + canonical)
    print("PASS: cached SW and completed D-cache writeback remain stale in I-cache until later invalidate/refill")


if __name__ == "__main__":
    run()
