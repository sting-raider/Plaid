#!/usr/bin/env python3
"""Build and execute actual IMEM -> SP write-DMA -> RDRAM lineage fixture."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

from source_guard import check as source_check
from verify import replay, reject_forgeries

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-rsp-imem-dma-egress"
DRIVER = HERE / "driver.cpp"
OBSERVER = HERE / "observer.hpp"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def load_builder():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wrappers():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = []
    for name, enabled in (("baseline", 0), ("sensor", 1)):
        path = OUTPUT / f"{name}.cpp"
        path.write_text(
            f"#define PLAID_IMEM_EGRESS_SENSOR {enabled}\n#include \"{DRIVER}\"\n",
            encoding="utf-8",
            newline="\n",
        )
        files.append(path)
    return files


def invoke(exe: Path, disabled: bool = False) -> tuple[str, dict]:
    env = dict(os.environ)
    if disabled:
        env["PLAID_IMEM_EGRESS_DISABLE"] = "1"
    else:
        env.pop("PLAID_IMEM_EGRESS_DISABLE", None)
    raw = subprocess.check_output([str(exe)], text=True, env=env, timeout=30)
    lines = [line for line in raw.splitlines() if line.startswith("{")]
    assert len(lines) == 1, raw
    return raw, json.loads(lines[0])


def worker():
    audit = source_check()
    builder = load_builder()
    baseline_source, sensor_source = wrappers()
    extras = (DRIVER, OBSERVER, HERE / "verify.py", HERE / "source_guard.py", Path(__file__))

    baseline = builder.build(
        baseline_source,
        OUTPUT / "baseline-build",
        extra_sources=extras,
    )
    sensor = builder.build(
        sensor_source,
        OUTPUT / "sensor-build",
        raw_fetch_access=True,
        physical_fetch_access=True,
        rdram_scalar_access=True,
        sp_backing_access=True,
        extra_sources=extras,
    )

    baseline_raw, baseline_result = invoke(baseline)
    disabled_raw, disabled_result = invoke(sensor, disabled=True)
    enabled_raw, enabled_result = invoke(sensor)
    repeat_raw, repeat_result = invoke(sensor)

    assert baseline_result["events"] == []
    assert disabled_result["events"] == []
    assert baseline_result["state"] == disabled_result["state"] == enabled_result["state"] == repeat_result["state"]
    assert enabled_raw == repeat_raw and enabled_result == repeat_result

    summary = replay({"events": enabled_result["events"]}, enabled_result["state"], enforce_contract=True)
    summary["forgeries_rejected"] = reject_forgeries({"events": enabled_result["events"]}, enabled_result["state"])
    summary["neutrality"] = True
    summary["repeat_deterministic"] = True
    summary["revision"] = REV
    summary["event_sha256"] = hashlib.sha256(
        json.dumps(enabled_result["events"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    result = {
        "audit": audit,
        "summary": summary,
        "runs": {
            "baseline": baseline_result,
            "disabled": disabled_result,
            "enabled": enabled_result,
            "repeat": repeat_result,
        },
        "inputs": {
            "driver_sha256": hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
            "observer_sha256": hashlib.sha256(OBSERVER.read_bytes()).hexdigest(),
            "verify_sha256": hashlib.sha256((HERE / "verify.py").read_bytes()).hexdigest(),
            "source_guard_sha256": hashlib.sha256((HERE / "source_guard.py").read_bytes()).hexdigest(),
        },
    }
    path = OUTPUT / "results.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, sort_keys=True))
    print("RESULT_SHA256=" + hashlib.sha256(path.read_bytes()).hexdigest())
    print("TRACE_SHA256=" + hashlib.sha256(enabled_raw.encode()).hexdigest())
    print("PASS executable IMEM writer generations export through completed reverse SP DMA effects")


def main():
    if os.name == "nt":
        script = subprocess.check_output(
            ["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()],
            text=True,
        ).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
        return
    worker()


if __name__ == "__main__":
    main()
