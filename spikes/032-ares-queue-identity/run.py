"""Execute baseline/disabled/repeated actual pinned queue and source replays."""
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
import subprocess
from prepare import generate
from verify import verify

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT / ".refs/ares"
OUTPUT = ROOT / "target/ares-queue-identity"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def worker():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REF / "LICENSE", OUTPUT / "LICENSE")
    header = OUTPUT / "include/nall/priority-queue.hpp"
    generate(REF, header)
    baseline = OUTPUT / "baseline"
    observed = OUTPUT / "observed"
    common = ["g++", "-O1", "-std=c++20", "-I", str(REF / "nall"), str(HERE / "probe.cpp")]
    subprocess.run(common + ["-DPLAID_QUEUE_SENSOR=0", "-o", str(baseline)], check=True)
    subprocess.run(common[:3] + ["-I", str(OUTPUT / "include")] + common[3:] +
                   ["-DPLAID_QUEUE_SENSOR=1", "-o", str(observed)], check=True)
    def run(exe, mode):
        return subprocess.check_output([str(exe), mode], text=True, timeout=10)
    base = json.loads(run(baseline, "plain"))
    disabled = json.loads(run(observed, "plain"))
    raw = run(observed, "traced")
    assert raw == run(observed, "traced")
    enabled = json.loads(raw)
    state = {k: v for k, v in enabled.items() if k != "events"}
    assert base["events"] == disabled["events"] == []
    assert {k: v for k, v in base.items() if k != "events"} == state
    assert {k: v for k, v in disabled.items() if k != "events"} == state
    assert state["dispatches"] == [1,0,1,0,0,1,1,1,1,1]
    assert state["boundaries"] == [3,4,4,5,6,8,10]
    result = verify(enabled["events"])
    assert result["successful_insertions"] == 523 and result["rejected_insertions"] == 1
    assert [e["token"] for e in result["identified_dispatch_candidates"]] == [2,3,1,6,519,520,521,522,523]
    assert result["unknown_valid_removals"] == 1
    assert result["identified_canceled_removals"] == 514 and result["unknown_invalid_removals"] == 0
    # Mutations preserve syntax and attack identity, validity, deadlines and moves.
    for kind, field, value in ((4,"token",1),(5,"event",1),(8,"valid",True),(3,"other",511),(7,"token",9999)):
        forged = copy.deepcopy(enabled["events"])
        candidates = [e for e in forged if e["kind"] == kind and e[field] != value]
        assert candidates
        candidates[0][field] = value
        try: verify(forged)
        except AssertionError: pass
        else: raise AssertionError(("accepted forgery", kind, field))
    receipt = dict(revision=REV, raw_records=len(enabled["events"]), result=result,
                   reported_baseline_disabled_repeat_equal=True, state=state,
                   cpu_device_dispatch_certified=False, hardware_timing_claimed=False)
    path = OUTPUT / "results.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    (OUTPUT / "traced.json").write_text(raw)
    print("RESULT_SHA256=" + hashlib.sha256(path.read_bytes()).hexdigest())
    print(json.dumps(result, indent=2))
    print("PASS: actual queue identities survive heap movement/cancellation/save; restore loses unsupported identities")


if __name__ == "__main__":
    if os.name == "nt":
        path = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", path], check=True)
    else: worker()
