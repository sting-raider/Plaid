#!/usr/bin/env python3
"""Build and execute the composed exact-pin ares provenance experiment."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ARES = ROOT / ".refs/ares"
OUT = ROOT / "target/ares-rsp-dmem-spdma-rdram-fetch"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
sys.path.insert(0, str(HERE))
from verify import verify, reject_forgeries


def load_builder():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("ares_builder_rsp_dma_fetch", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_guard():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ARES, text=True).strip() == REV
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ARES, check=True)
    dma = ARES / "ares/n64/rsp/dma.cpp"
    io = ARES / "ares/n64/rsp/io.cpp"
    memory = ARES / "ares/n64/cpu/memory.cpp"
    d = dma.read_text(encoding="utf-8")
    i = io.read_text(encoding="utf-8")
    m = memory.read_text(encoding="utf-8")

    lo_read = "u32 dataLo = dmem.read<Word>(dma.current.pbusAddress + 0);"
    hi_read = "u32 dataHi = dmem.read<Word>(dma.current.pbusAddress + 4);"
    lo_write = "rdram.ram.write<Word>(dma.current.dramAddress + 0, dataLo, RBusDevice::SP_DMA);"
    hi_write = "rdram.ram.write<Word>(dma.current.dramAddress + 4, dataHi, RBusDevice::SP_DMA);"
    for marker in (lo_read, hi_read, lo_write, hi_write):
        assert d.count(marker) == 1, marker
    assert d.index(lo_read) < d.index(hi_read) < d.index(lo_write) < d.index(hi_write)
    assert "if(dma.busy.write)" in d
    assert "dma.current = dma.pending;" in d and "dma.busy    = dma.full;" in d
    assert "//SP_WRITE_LENGTH" in i and "dma.full.write = 1;" in i and "dmaTransferStart(thread);" in i
    assert "return bus.read<Size>(address, *this, RBusDevice::VR4300_UNCACHED);" in m
    assert "bus.write<Size>(address, data, *this, RBusDevice::VR4300_UNCACHED);" in m
    assert "if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);" in m
    assert "return busRead<Word>(paddr);" in m
    return {
        "revision": REV,
        "dma_cpp_sha256": sha(dma),
        "io_cpp_sha256": sha(io),
        "cpu_memory_cpp_sha256": sha(memory),
        "reverse_dmem_dma_local_value_chain": True,
        "uncached_cpu_read_write_requestor_explicit": True,
    }


def materialize_drivers():
    source = (HERE / "driver.cpp").read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = OUT / "baseline.cpp"
    sensor = OUT / "sensor.cpp"
    baseline.write_text("#define PLAID_COMPOSE_SENSOR 0\n" + source, encoding="utf-8", newline="\n")
    sensor.write_text("#define PLAID_COMPOSE_SENSOR 1\n" + source, encoding="utf-8", newline="\n")
    return baseline, sensor


def execute(exe, disabled=False):
    env = dict(os.environ)
    if disabled:
        env["PLAID_COMPOSE_DISABLE"] = "1"
    else:
        env.pop("PLAID_COMPOSE_DISABLE", None)
    raw = subprocess.check_output([str(exe)], text=True, env=env, timeout=45)
    rows = [json.loads(line) for line in raw.splitlines() if line.startswith("{")]
    assert len(rows) == 2, raw
    return raw, {"machine": rows[0], "history": rows[1]}


def worker():
    guard = source_guard()
    builder = load_builder()
    baseline_src, sensor_src = materialize_drivers()
    extras = (HERE / "driver.cpp", HERE / "observer.hpp", HERE / "verify.py", Path(__file__))
    baseline_exe = builder.build(baseline_src, OUT / "baseline-build", extra_sources=extras)
    sensor_exe = builder.build(
        sensor_src,
        OUT / "sensor-build",
        rdram_scalar_access=True,
        fetch_boundary_access=True,
        rsp_dmem_access=True,
        extra_sources=extras,
    )

    raw_baseline, baseline = execute(baseline_exe)
    raw_disabled, disabled = execute(sensor_exe, disabled=True)
    raw_sensor, sensor = execute(sensor_exe)
    raw_repeat, repeat = execute(sensor_exe)

    assert baseline["machine"] == disabled["machine"] == sensor["machine"] == repeat["machine"]
    assert baseline["history"] == disabled["history"]
    assert not baseline["history"]["rsp_sinks"] and not baseline["history"]["rdram"] and not baseline["history"]["fetch"]
    assert sensor == repeat
    assert raw_sensor == raw_repeat

    summary = verify(sensor["history"], sensor["machine"])
    forgeries = reject_forgeries(sensor["history"], sensor["machine"])
    assert len(forgeries) == 7

    result = {
        "plaid_base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "ares_revision": REV,
        "source_guard": guard,
        "neutrality": {
            "baseline_equals_generated_observer_disabled": baseline["machine"] == disabled["machine"],
            "baseline_equals_observer_enabled": baseline["machine"] == sensor["machine"],
            "enabled_repeat_byte_identical": raw_sensor == raw_repeat,
            "machine_sha256": sensor["machine"]["machine_sha256"],
        },
        "summary": summary,
        "forgeries_rejected": forgeries,
        "machine": sensor["machine"],
        "history": sensor["history"],
        "hashes": {
            "driver_sha256": sha(HERE / "driver.cpp"),
            "observer_sha256": sha(HERE / "observer.hpp"),
            "verify_sha256": sha(HERE / "verify.py"),
            "instrumented_stdout_sha256": hashlib.sha256(raw_sensor.encode()).hexdigest(),
        },
    }
    path = OUT / "results.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, sort_keys=True))
    print("RESULT_SHA256=" + sha(path))
    print("INSTRUMENTED_STDOUT_SHA256=" + result["hashes"]["instrumented_stdout_sha256"])
    print("PASS: actual decoded RSP DMEM stores compose through reverse SP DMA RDRAM effects into uncached CPU fetches; same-value writer generations, partial-byte roots, and same-value CPU overwrite boundaries remain distinct")


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
