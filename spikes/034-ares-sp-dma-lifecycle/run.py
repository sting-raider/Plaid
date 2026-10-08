#!/usr/bin/env python3
"""Execute the exact-pin ares SP DMA lifecycle fixture and cross-reference guards."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ARES = ROOT / ".refs/ares"
MUPEN = ROOT / ".refs/mupen64plus-core"
GOPHER = ROOT / ".refs/gopher64"
OUT = ROOT / "target/ares-sp-dma-lifecycle"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def load_builder():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("ares_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def by_name(states):
    return {state["name"]: state for state in states}


def worker():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ARES, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=ARES, check=True)
    shutil.rmtree(OUT, ignore_errors=True)
    builder = load_builder()
    exe = builder.build(HERE / "driver.cpp", OUT / "build")

    raw1 = subprocess.check_output([str(exe)], text=True, timeout=45)
    raw2 = subprocess.check_output([str(exe)], text=True, timeout=45)
    assert raw1 == raw2, "reference fixture was not deterministic"
    observed = json.loads(raw1)
    states = by_name(observed["states"])

    b = states["pending_committed_B"]
    assert (b["busy"], b["full"], b["pending"]["pbus"], b["pending"]["dram"], b["pending"]["length"]) == (1,1,0x80,0x2000,0)
    c = states["pending_mutated_to_C"]
    assert (c["busy"], c["full"], c["pending"]["pbus"], c["pending"]["dram"], c["pending"]["length"]) == (1,1,0x100,0x3000,0)
    h = states["after_A_handoff"]
    assert (h["busy"], h["full"], h["current"]["pbus"], h["current"]["dram"]) == (1,0,0x100,0x3000)
    assert states["after_mutated_C_complete"]["busy"] == 0

    before = states["third_before"]
    rewritten = states["third_overwrote_pending"]
    promoted = states["third_promoted"]
    assert (before["busy"], before["full"], before["pending"]["length"]) == (1,1,0)
    assert (rewritten["busy"], rewritten["full"], rewritten["pending"]["pbus"], rewritten["pending"]["dram"], rewritten["pending"]["length"]) == (1,1,0x100,0x3000,8)
    assert (promoted["busy"], promoted["full"], promoted["current"]["pbus"], promoted["current"]["dram"], promoted["current"]["length"]) == (1,0,0x100,0x3000,8)
    assert states["third_complete"]["busy"] == 0

    start = states["multiblock_start"]
    first = states["multiblock_after_first"]
    handoff = states["multiblock_handoff_no_busy_edge"]
    done = states["multiblock_pending_complete"]
    assert (start["busy"], start["full"], start["current"]["count"], start["current"]["dram"]) == (1,1,1,0x4000)
    assert (first["busy"], first["full"], first["current"]["count"], first["current"]["dram"]) == (1,1,0,0x4010)
    assert (handoff["busy"], handoff["full"], handoff["current"]["dram"], handoff["current"]["pbus"]) == (1,0,0x5000,0x300)
    assert (done["busy"], done["full"]) == (0,0)

    wrap_start = states["wrap_start"]
    wrap_done = states["wrap_complete"]
    assert (wrap_start["current"]["pbus"], wrap_start["current"]["length"], wrap_start["busy"]) == (0xff8,8,1)
    assert (wrap_done["current"]["pbus"], wrap_done["busy"], wrap_done["full"]) == (0x008,0,0)

    guard_raw = subprocess.check_output([
        os.fspath(Path(os.sys.executable)), os.fspath(HERE / "source_guard.py"),
        os.fspath(ARES), os.fspath(MUPEN), os.fspath(GOPHER),
    ], text=True)
    source_guard = json.loads(guard_raw)
    assert source_guard["cross_reference_agreement"] is False
    assert source_guard["semantics"]["ares"]["pending_descriptor_mutable_after_full"] is True
    assert source_guard["semantics"]["mupen"]["third_push_rejected_when_full"] is True
    assert source_guard["semantics"]["gopher"]["third_push_rejected_when_full"] is True

    result = {
        "revision": REV,
        "driver_sha256": hashlib.sha256((HERE / "driver.cpp").read_bytes()).hexdigest(),
        "repeat_deterministic": raw1 == raw2,
        "states": observed["states"],
        "final": observed["final"],
        "source_guard": source_guard,
        "conclusions": {
            "ares_pending_is_mutable_while_full": True,
            "ares_third_length_commit_rewrites_pending": True,
            "busy_falling_edge_missing_at_current_to_pending_handoff": True,
            "count_skip_subblocks_share_one_current_descriptor": True,
            "imem_transfer_can_wrap_0xff8_to_0x000": True,
            "mupen_gopher_disagree_with_ares_full_fifo_policy": True,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    result_path = OUT / "results.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("RESULT_SHA256=" + hashlib.sha256(result_path.read_bytes()).hexdigest())
    print("REFERENCE_STDOUT_SHA256=" + hashlib.sha256(raw1.encode()).hexdigest())
    print("PASS: pinned ares pending SP-DMA descriptor mutates/replaces while FULL; handoff hides BUSY edge; count/skip stays one current descriptor; IMEM wraps; Mupen/Gopher full-FIFO semantics disagree")


def main():
    if os.name == "nt":
        script = subprocess.check_output([
            "wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()
        ], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
