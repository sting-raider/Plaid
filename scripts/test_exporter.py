"""Build the C sink, check guest facts, and import its actual bytes with Plaid."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    cc = os.environ.get("CC", "gcc")
    cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo.exe")
    (ROOT / "target").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="exporter-", dir=ROOT / "target") as directory:
        directory = Path(directory)
        exe = directory / ("sensor.exe" if os.name == "nt" else "sensor")
        trace = directory / "discovery.ndjson"
        subprocess.run([cc, "-std=c99", "-Wall", "-Wextra", "-Werror", str(ROOT / "instruments/mupen/synthetic_exporter.c"), "-o", str(exe)], check=True)
        env = dict(os.environ, PLAID_TRACE_PATH=str(trace), PLAID_ROM_SHA256="a" * 64, PLAID_ROM_SIZE="4096")
        subprocess.run([str(exe)], env=env, check=True)
        first = trace.read_bytes()
        subprocess.run([str(exe)], env=env, check=True)
        assert trace.read_bytes() == first, "synthetic trace must be deterministic"
        records = [json.loads(line) for line in first.splitlines()]
        assert len(records) == 12
        assert records[-1] == {"record": "end", "event_count": 10}
        assert records[1]["data"]["physical_start"] == 0
        assert records[3]["data"]["words"] == [0x3c088000, 0x35080020, 0x01000008, 0]
        assert records[7]["data"]["delay_slot_entry"] is True
        assert records[8]["data"]["register_mask"] == 16
        assert records[11]["event_count"] == 10
        assert records[10]["data"]["range"] is None
        assert b"host" not in first and b"pointer" not in first
        assert b"entry_bytes_verified" not in first
        subprocess.run([cargo, "run", "--quiet", "-p", "plaid", "--", "check-trace", str(trace)], cwd=ROOT, check=True)
        trace.unlink()
        subprocess.run([str(exe)], env=dict(env, PLAID_ROM_SHA256="invalid"), check=True, capture_output=True)
        assert not trace.exists(), "bad identity must not produce a trace"
        subprocess.run([str(exe)], env=dict(env, PLAID_TRACE_PATH=""), check=True)
        assert not trace.exists(), "disabled sensor must not produce a trace"
    print("Exporter cross-language tests passed")

if __name__ == "__main__":
    main()
