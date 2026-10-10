#!/usr/bin/env python3
"""Build and execute the exact-pinned ares RSP reset/NMI fixture twice."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "target/ares-rsp-reset-imem-lifetime"
DRIVER = HERE / "driver.cpp"

spec = importlib.util.spec_from_file_location("plaid_ares_oracle", ROOT / "spikes/003-ares-oracle/run.py")
oracle = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(oracle)

oracle.build(DRIVER, OUT)
exe = OUT / "oracle"
first = subprocess.check_output([str(exe)], text=True).strip()
second = subprocess.check_output([str(exe)], text=True).strip()
if first != second:
    raise SystemExit("reference output was not deterministic")
data = json.loads(first)
assert data["nmi"]["preserved"] is True
assert data["nmi"]["busy"] == 1 and data["nmi"]["full"] == 1
assert data["soft_reset"]["cleared"] is True
assert data["equal_payload_reset"]["state_reset"] is True
assert data["equal_payload_reset"]["before"] == data["equal_payload_reset"]["after"]
assert data["cold_power"]["cleared"] is True
result = {
    "ares_revision": oracle.REV,
    "driver_sha256": hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
    "stdout_sha256": hashlib.sha256((first + "\n").encode()).hexdigest(),
    "result": data,
}
OUT.mkdir(parents=True, exist_ok=True)
path = OUT / "results.json"
path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
print(path)
print("STDOUT_SHA256=" + result["stdout_sha256"])
print("RESULT_SHA256=" + hashlib.sha256(path.read_bytes()).hexdigest())
print("REFERENCE_EXECUTION_PASS")
