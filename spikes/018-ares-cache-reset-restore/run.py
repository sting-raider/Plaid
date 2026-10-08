"""Run the pinned ares cache reset/restore lineage counterexample."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-cache-reset-restore-spike"


def worker():
    spec = importlib.util.spec_from_file_location("builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    baseline = builder.build(Path(__file__).with_name("baseline.cpp"), OUTPUT / "baseline",
        extra_sources=(Path(__file__).with_name("fixture.cpp"),))
    traced = builder.build(Path(__file__).with_name("driver.cpp"), OUTPUT / "traced",
        raw_fetch_access=True, physical_fetch_access=True, cache_fill_access=True,
        extra_sources=(Path(__file__).with_name("fixture.cpp"), ROOT / "spikes/012-ares-cache-fill/observer.hpp"))
    baseline_raw = subprocess.check_output([str(baseline), "plain"], text=True, timeout=30)
    traced_raw = subprocess.check_output([str(traced), "traced"], text=True, timeout=30)
    repeat_raw = subprocess.check_output([str(traced), "traced"], text=True, timeout=30)
    assert traced_raw == repeat_raw
    base, result = json.loads(baseline_raw), json.loads(traced_raw)
    assert base["state"] == result["state"]
    assert result["fill_count"] == 3
    assert result["naive_post_restore_fill"] == 2
    assert result["state"]["s0"] == 2
    assert result["state"]["ram0"] == result["state"]["line_word0"] == 0x24100002
    (OUTPUT / "baseline.json").write_text(json.dumps(base, indent=2) + "\n")
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print("PASS: restore resurrects cache state without a fill; tuple matcher crosses the restore boundary; reset forces a new fill; baseline/traced state match")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
