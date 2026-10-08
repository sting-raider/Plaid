"""Check actual ROM reads, PI latch rejection and exact fetch-window isolation."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-rom-source-spike"


def worker():
    spec = importlib.util.spec_from_file_location("builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    exe = builder.build(Path(__file__).with_name("driver.cpp"), OUTPUT,
        raw_fetch_access=True,physical_fetch_access=True)
    states = {}
    for mode in ("original","plain","traced","repeat"):
        subprocess.run([str(exe),"traced" if mode == "repeat" else mode,
            str(OUTPUT / f"{mode}.ndjson"),str(OUTPUT / f"{mode}.json")],check=True,timeout=10)
        states[mode] = json.loads((OUTPUT / f"{mode}.json").read_text())
    assert all(state == states["original"] for state in states.values())
    assert (OUTPUT / "traced.ndjson").read_bytes() == (OUTPUT / "repeat.ndjson").read_bytes()
    samples = [json.loads(row) for row in (OUTPUT / "traced.ndjson").read_text().splitlines()]
    assert [s["word"] for s in samples] == [0x24100001,0x24100001,0x20002000,0x24100001,0x24100001,0x24100002]
    assert [s["rom_offset"] for s in samples] == [4096,None,None,None,4096,4100]
    assert [s["rom_half_reads"] for s in samples] == [2,0,0,0,2,2]
    assert [s["physical"] for s in samples] == [0x10001000,0x10001000,0x10002000,0x10001000,0x10001000,0x10001004]
    assert all(not s["cached"] for s in samples)
    assert states["original"]["mapped_size"] == 8192
    results = {"samples":samples,"state":states["original"],"original_plain_traced_repeat_equal":True,
        "source_witnesses":3,"unknown_sources":3,"guest_completion_claimed":False}
    (OUTPUT / "results.json").write_text(json.dumps(results,indent=2)+"\n")
    print(json.dumps(results,indent=2))


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
