"""Run retained research models/source guards; this is not reference execution."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "target/research-contracts"
CASES = (
    ("fill_join", "spikes/018-ares-fill-rdram-chronology/test_chronology.py"),
    ("cache_order", "spikes/018-ares-cache-order/run.py"),
    ("cache_source_guard", "spikes/018-ares-cache-order/source_guard.py"),
    ("reset_lifetime", "spikes/018-reset-cache-lifetime/model.py"),
    ("restore_contract", "spikes/018-ares-cache-reset-restore/contract_model.py"),
    ("table_aliases", "experiments/pointer_table_immutability_aliases.py"),
    ("cpu_copy", "experiments/cpu-copy-provenance/provenance_harness.py"),
    ("llsc", "experiments/llsc-provenance/llsc_contract.py"),
    ("pif_backing", "experiments/pif-rom-backing/witness_model.py", "--fuzz", "1000000"),
    ("sp_backing", "spikes/024-ares-sp-fetch-backing/source_contract.py"),
    ("partial_word", "spikes/019-ares-swl-swr-mutations/run.py"),
    ("partial_dual", "spikes/025-ares-64bit-stores/model.py"),
    ("uncached_fetch", "spikes/025-ares-rdram-uncached-fetch/source_contract.py"),
    ("uncached_source_guard", "spikes/025-ares-rdram-uncached-fetch/source_guard.py", ".refs/ares"),
)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    for name, path, *args in CASES:
        command = [sys.executable, str(ROOT / path), *args]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60)
        if run.returncode:
            sys.stdout.buffer.write(run.stdout)
            sys.stderr.buffer.write(run.stderr)
            raise RuntimeError(f"research contract failed: {name}")
        (OUTPUT / f"{name}.stdout.txt").write_bytes(run.stdout)
        (OUTPUT / f"{name}.stderr.txt").write_bytes(run.stderr)
        results.append({"name":name,"command":command,
            "stdout_sha256":hashlib.sha256(run.stdout).hexdigest(),
            "stderr_sha256":hashlib.sha256(run.stderr).hexdigest()})
        print(f"PASS {name}")
    (OUTPUT / "results.json").write_text(json.dumps({
        "scope":"standalone source contracts and pinned-source guards; no N64/reference execution",
        "cases":results}, indent=2) + "\n")
    print(f"PASS: {len(results)} retained research contracts/guards; full outputs remain ignored")


if __name__ == "__main__": main()
