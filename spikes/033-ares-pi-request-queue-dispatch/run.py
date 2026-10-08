"""Compose PI request context with the exact pinned nall queue token and dispatch boundary."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT / ".refs/ares"
OUTPUT = ROOT / "target/ares-pi-request-queue-dispatch"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

sys.path.insert(0, str(ROOT / "spikes/032-ares-queue-identity"))
from prepare import generate  # noqa: E402


def ordered(text: str, *needles: str) -> None:
    pos = -1
    for needle in needles:
        found = text.find(needle, pos + 1)
        assert found >= 0, needle
        pos = found


def guard_sources() -> dict:
    pi_io = (REF / "ares/n64/pi/io.cpp").read_text()
    cpu = (REF / "ares/n64/cpu/cpu.cpp").read_text()
    dma = (REF / "ares/n64/pi/dma.cpp").read_text()
    queue = (REF / "nall/nall/priority-queue.hpp").read_text()

    ordered(pi_io,
        "if(address != 4 && (io.dmaBusy || io.ioBusy)) {",
        "io.error = 1;",
        "return;")
    ordered(pi_io,
        "io.writeLength = n24(data);",
        "io.dmaBusy = 1;",
        "io.originPc = cpu.ipu.pc;",
        "cpu.queueInsert(Queue::PI_DMA_Write, dmaDuration(false));",
        "dmaWrite();")
    ordered(pi_io,
        "io.readLength = n24(data);",
        "io.dmaBusy = 1;",
        "io.originPc = cpu.ipu.pc;",
        "cpu.queueInsert(Queue::PI_DMA_Read, dmaDuration(true));",
        "dmaRead();")
    ordered(pi_io,
        "if(data.bit(0)) {",
        "io.dmaBusy = 0;",
        "io.error = 0;",
        "queue.remove(Queue::PI_DMA_Read);",
        "queue.remove(Queue::PI_DMA_Write);")
    ordered(cpu,
        "auto CPU::queueInsert(u32 event, u32 clocks) -> void {",
        "if(!queue.insert(event, clocks)) return;")
    ordered(cpu,
        "queue.step(clocks, [](u32 event) {",
        "case Queue::PI_DMA_Read:   return pi.dmaFinished();",
        "case Queue::PI_DMA_Write:  return pi.dmaFinished();")
    ordered(dma,
        "auto PI::dmaFinished() -> void {",
        "io.dmaBusy = 0;",
        "io.interrupt = 1;",
        "mi.raise(MI::IRQ::PI);")
    ordered(queue,
        "while(size && ge(clock, heap[0].clock)) {",
        "if(auto event = remove()) callback(*event);")
    assert queue.count("if(auto event = remove()) callback(*event);") == 1

    return {
        "pi_io_sha256": hashlib.sha256(pi_io.encode()).hexdigest(),
        "cpu_sha256": hashlib.sha256(cpu.encode()).hexdigest(),
        "pi_dma_sha256": hashlib.sha256(dma.encode()).hexdigest(),
        "queue_sha256": hashlib.sha256(queue.encode()).hexdigest(),
    }


def worker() -> None:
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    source_hashes = guard_sources()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REF / "LICENSE", OUTPUT / "LICENSE")
    generated = OUTPUT / "include/nall/priority-queue.hpp"
    generate(REF, generated)

    baseline = OUTPUT / "baseline"
    observed = OUTPUT / "observed"
    common = ["g++", "-O1", "-std=c++20", "-I", str(REF / "nall"), str(HERE / "probe.cpp")]
    subprocess.run(common + ["-DPLAID_QUEUE_SENSOR=0", "-o", str(baseline)], check=True)
    subprocess.run(common[:3] + ["-I", str(OUTPUT / "include")] + common[3:] +
                   ["-DPLAID_QUEUE_SENSOR=1", "-o", str(observed)], check=True)

    def execute(exe: Path, mode: str) -> str:
        return subprocess.check_output([str(exe), mode], text=True, timeout=10)

    base = json.loads(execute(baseline, "plain"))
    disabled = json.loads(execute(observed, "plain"))
    raw = execute(observed, "traced")
    assert raw == execute(observed, "traced")
    traced = json.loads(raw)

    semantic = ("copy_effects", "requests", "rejected_inserted", "rejected_dispatched", "busy", "interrupt")
    assert {k: base[k] for k in semantic} == {k: disabled[k] for k in semantic} == {k: traced[k] for k in semantic}
    assert len(base["dispatches"]) == len(disabled["dispatches"]) == len(traced["dispatches"]) == 3
    assert traced["requests"] == 5 and traced["copy_effects"] == 5
    assert traced["token_a"] and traced["token_b"] and traced["token_a"] != traced["token_b"]
    assert traced["dispatches"][0:2] == [1, 2]
    assert traced["dispatches"][-1] == 0 and traced["unknown_dispatches"] == 1
    assert traced["rejected_inserted"] is False and traced["rejected_dispatched"] is False
    assert traced["serialized_request_joined"] is False

    receipt = {
        "revision": REV,
        "source_hashes": source_hashes,
        "reported_semantics_baseline_disabled_repeat_equal": True,
        "actual_pinned_queue_executed": True,
        "full_pi_cpu_component_executed": False,
        "guest_busy_gate_blocks_second_live_pi_request": True,
        "equal_event_deadline_tokens_distinct_container_stress_only": True,
        "canceled_event_no_cpu_callback": True,
        "rejected_request_copy_effect_observed_in_guarded_model": True,
        "post_serialization_dispatch_identity_unknown": True,
        "queue_dispatch_proves_byte_copy_completion": False,
        "traced": traced,
    }
    out = OUTPUT / "results.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("RESULT_SHA256=" + hashlib.sha256(out.read_bytes()).hexdigest())
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print("PASS: queue token composes with request/dispatch/status boundary; copy completion remains independent")


if __name__ == "__main__":
    if os.name == "nt":
        path = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", path], check=True)
    else:
        worker()
