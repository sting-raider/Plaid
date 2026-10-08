"""Capture/recheck PI boot sources, prior complete chronology and checkpoints."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from verify import inspect

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT/"target/ares-boot-pi-history-spike"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024*1024):
            sha.update(chunk)
    return sha.hexdigest()


def capture(budget, variant):
    boot = load("boot", ROOT/"spikes/008-ares-pif-boot/run.py")
    history = load("history", ROOT/"spikes/027-ares-boot-history/run.py")
    root = OUTPUT/variant; root.mkdir(parents=True, exist_ok=True)
    pi = variant == "pi"
    observer = HERE/"observer.hpp" if pi else ROOT/"spikes/027-ares-boot-history/observer.hpp"
    options = dict(cache_fill_access=True, cache_operation_access=True, rdram_burst_access=True,
                   rdram_scalar_access=True, fetch_boundary_access=True)
    if pi:
        options["pi_dma_access"] = True
    return boot.worker(budget, driver=HERE/"driver.cpp" if pi else ROOT/"spikes/027-ares-boot-history/driver.cpp",
                       output_root=root, boot_inputs=history.PROFILE, cache_policy="selected_icache_line_at_prologue",
                       build_options=options, observer_sources=(observer, ROOT/"spikes/027-ares-boot-history/observer.hpp",
                           ROOT/"spikes/011-ares-cache-fetch/driver.cpp"), run_timeout=600)


def verify(budget):
    boot = load("boot", ROOT/"spikes/008-ares-pif-boot/run.py")
    history = load("history", ROOT/"spikes/027-ares-boot-history/run.py")
    original, current = OUTPUT/"baseline"/str(budget), OUTPUT/"pi"/str(budget)
    source = boot.ROM.read_bytes()
    assert hashlib.sha256(source).hexdigest() == history.ROM_SHA
    assert digest(boot.FIRMWARE) == history.FW_SHA
    checkpoints = []
    for output in (original, current):
        states = [json.loads((output/f"{mode}.json").read_text()) for mode in ("plain", "traced", "repeat")]
        assert states[0] == states[1] == states[2]
        receipt = json.loads((output/"results.json").read_text())
        assert receipt["final_state"] == states[0] and receipt["trace_sha256"] == digest(output/"traced.ndjson")
        checkpoints.append(states[0])
        boot.equal_files(output/"traced.ndjson", output/"repeat.ndjson")
        boot.equal_files(output/"traced.ndjson.history.ndjson", output/"repeat.ndjson.history.ndjson")
        assert not (output/"plain.ndjson.history.ndjson").exists()
        boot.equal_files(output/"plain.messages", output/"traced.messages")
        boot.equal_files(output/"traced.messages", output/"repeat.messages")
    assert checkpoints[0] == checkpoints[1]
    boot.equal_files(original/"traced.ndjson", current/"traced.ndjson")
    boot.equal_files(original/"traced.messages", current/"traced.messages")
    raw = current/"traced.ndjson.history.ndjson"
    projection = current/"v0-projection.ndjson"
    with projection.open("wb") as file:
        result = inspect(history.records(raw), source, file)
    boot.equal_files(original/"traced.ndjson.history.ndjson", projection)
    prior = history.verify(projection, current/"traced.ndjson", budget)
    assert prior == history.verify(original/"traced.ndjson.history.ndjson", original/"traced.ndjson", budget)
    result.update(history_sha256=digest(raw), history_bytes=raw.stat().st_size,
                  v0_projection_sha256=digest(projection), paired_fetch_sha256=digest(current/"traced.ndjson"),
                  prior_inspection=prior, checkpoint_unchanged=True, guest_completion_claimed=False,
                  production_identity_promoted=False)
    path = current/"pi-history-results.json"
    path.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, sort_keys=True))
    print("PASS: PI source/effect contexts retain complete v0/v5 projections and baseline/disabled/repeated checkpoint; scheduled completion remains explicit")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=610000)
    parser.add_argument("--capture", choices=("baseline", "pi"), help="capture one independent variant; verify both afterwards")
    parser.add_argument("--verify-existing", action="store_true")
    options = parser.parse_args()
    assert 0 < options.budget <= 1000000 and not (options.capture and options.verify_existing)
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script, *sys.argv[1:]], check=True)
    elif options.capture:
        capture(options.budget, options.capture)
    else:
        if not options.verify_existing:
            capture(options.budget, "baseline"); capture(options.budget, "pi")
        verify(options.budget)


if __name__ == "__main__":
    main()
