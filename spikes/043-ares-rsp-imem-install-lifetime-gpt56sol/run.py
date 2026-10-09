#!/usr/bin/env python3
"""Build exact pinned ares and validate composed RSP IMEM installation lifetimes."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import types
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "target/ares-rsp-imem-install-lifetime"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
DMA_SHA = "b5d8a1c4b45c2d84c487d98725caa465ac4b5fbea4761beff51ca1a1ba93d7b6"
IO_SHA = "60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860"


def load_builder():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    source = path.read_text(encoding="utf-8")
    old = "spikes/042-ares-rsp-dmem-history/prepare.py"
    new = "spikes/043-ares-rsp-imem-install-lifetime-gpt56sol/prepare.py"
    assert source.count(old) == 2
    patched = source.replace(old, new)
    module = types.ModuleType("plaid_rsp_install_builder")
    module.__file__ = str(path)
    exec(compile(patched, str(path), "exec"), module.__dict__)
    return module, source, patched


def load_verifier():
    path = HERE / "verify.py"
    spec = importlib.util.spec_from_file_location("rsp_install_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def worker():
    builder, original_builder, patched_builder = load_builder()
    assert builder.REV == PIN
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=builder.REF,text=True).strip() == PIN
    subprocess.run(["git","-c","core.autocrlf=true","diff","--quiet","HEAD"],cwd=builder.REF,check=True)
    dma = builder.REF / "ares/n64/rsp/dma.cpp"
    io = builder.REF / "ares/n64/rsp/io.cpp"
    assert sha(dma) == DMA_SHA
    assert sha(io) == IO_SHA

    baseline = builder.build(HERE / "baseline.cpp", OUT / "baseline")
    sensor = builder.build(HERE / "driver.cpp", OUT / "sensor", rsp_dmem_access=True)

    base_raw = subprocess.check_output([str(baseline), "plain"], text=True, timeout=45)
    plain_raw = subprocess.check_output([str(sensor), "plain"], text=True, timeout=45)
    trace_raw1 = subprocess.check_output([str(sensor), "traced"], text=True, timeout=45)
    trace_raw2 = subprocess.check_output([str(sensor), "traced"], text=True, timeout=45)
    assert trace_raw1 == trace_raw2, "instrumented event trace is not byte-deterministic"
    base, plain, traced = map(json.loads, (base_raw, plain_raw, trace_raw1))
    assert base["state"] == plain["state"] == traced["state"], "observer changed architectural result"
    assert base["events"] == plain["events"] == []
    assert traced["state"]["reload1"] == traced["state"]["reload2"]

    verifier = load_verifier()
    replayed = verifier.assert_fixture_contract(traced)
    adversaries = verifier.adversarial_checks(traced)

    case1 = [e for e in traced["events"] if e["case"] == 1]
    assert [e["kind"] for e in case1] == ["promote","dma_sink","cpu_sink","dma_sink","complete"]
    assert case1[0]["request"] == case1[1]["request"] == case1[3]["request"] == case1[4]["request"] == 1
    assert case1[2]["request"] == 0 and case1[2]["pbus"] == 0x204
    assert case1[1]["value"] == 0x1111111111111111 and case1[2]["value"] == 0x11111111

    case2 = [e for e in traced["events"] if e["case"] == 2]
    promotes = [e for e in case2 if e["kind"] == "promote"]
    sinks = [e for e in case2 if e["kind"] == "dma_sink"]
    assert [e["request"] for e in promotes] == [2,3]
    assert [e["value"] for e in sinks[:2]] == [e["value"] for e in sinks[2:]]
    assert [e["pbus"] for e in sinks[:2]] == [e["pbus"] for e in sinks[2:]] == [0x300,0x308]

    case3 = [e for e in traced["events"] if e["case"] == 3 and e["kind"] == "dma_sink"]
    assert [(e["request"],e["pbus"]) for e in case3] == [(4,0xff8),(4,0x000)]

    case4 = [e for e in traced["events"] if e["case"] == 4]
    assert [e["kind"] for e in case4] == ["promote","dma_sink","complete","promote","dma_sink","complete"]
    assert [e["request"] for e in case4 if e["kind"] == "promote"] == [5,6]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "trace.json").write_text(json.dumps(traced, indent=2, sort_keys=True) + "\n")
    manifest = {
        "plaid_commit": subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        "ares_revision": PIN,
        "upstream_dma_sha256": DMA_SHA,
        "upstream_io_sha256": IO_SHA,
        "driver_sha256": sha(HERE / "driver.cpp"),
        "prepare_sha256": sha(HERE / "prepare.py"),
        "verify_sha256": sha(HERE / "verify.py"),
        "original_builder_sha256": hashlib.sha256(original_builder.encode()).hexdigest(),
        "patched_builder_sha256": hashlib.sha256(patched_builder.encode()).hexdigest(),
        "trace_sha256": hashlib.sha256(trace_raw1.encode()).hexdigest(),
        "baseline_state_equals_sensor_state": base["state"] == traced["state"],
        "repeat_trace_byte_identical": trace_raw1 == trace_raw2,
        "event_count": len(traced["events"]),
        "completed_requests": replayed["completed"],
        "rejected_adversaries": adversaries,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    print("TRACE_SHA256=" + manifest["trace_sha256"])
    print("MANIFEST_SHA256=" + sha(OUT / "manifest.json"))
    print("PASS: promoted request identity groups exact completed DMA sinks across count/skip and IMEM wrap; same-value CPU sinks retain independent byte generations; identical reloads remain distinct request generations; completion/promotion does not require a BUSY edge")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
