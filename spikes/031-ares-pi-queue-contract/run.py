"""Check exact pin/source routes and execute the container, not the N64 CPU."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT/".refs/ares"
OUTPUT = ROOT/"target/ares-pi-queue-contract"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def worker():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    cpu = (REF/"ares/n64/cpu/cpu.cpp").read_text()
    pi = (REF/"ares/n64/pi/io.cpp").read_text()
    queue = (REF/"nall/nall/priority-queue.hpp").read_text()
    assert "if(!queue.insert(event, clocks)) return;" in cpu
    assert "case Queue::PI_DMA_Read:   return pi.dmaFinished();" in cpu
    assert "case Queue::PI_DMA_Write:  return pi.dmaFinished();" in cpu
    for direction in ("Read", "Write"):
        assert f"cpu.queueInsert(Queue::PI_DMA_{direction}, dmaDuration({str(direction == 'Read').lower()}));" in pi
        assert f"queue.remove(Queue::PI_DMA_{direction});" in pi
    assert "struct Queue : priority_queue<u32[512]>" in (REF/"ares/n64/n64.hpp").read_text()
    assert "if(size >= Size) return false;" in queue and "heap[i].valid = false;" in queue
    OUTPUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REF/"LICENSE", OUTPUT/"LICENSE")
    exe = OUTPUT/"queue-probe"
    subprocess.run(["g++", "-O1", "-std=c++20", "-I", str(REF/"nall"), str(HERE/"probe.cpp"), "-o", str(exe)], check=True)
    raw = subprocess.check_output([str(exe)], text=True, timeout=10)
    assert raw == subprocess.check_output([str(exe)], text=True, timeout=10)
    result = json.loads(raw)
    assert result == dict(duplicate_write_dispatches=[1,1], canceled_write_then_read=[0], capacity=512,
                          canceled_slots_reject_insert_until_drained=True, clock_wrap_dispatch=[1])
    receipt = dict(revision=REV, container_result=result, source_routes_checked=True,
                   cpu_or_pi_execution_claimed=False, hardware_timing_claimed=False)
    path = OUTPUT/"results.json"
    path.write_text(json.dumps(receipt, indent=2)+"\n")
    print("RESULT_SHA256="+hashlib.sha256(path.read_bytes()).hexdigest())
    print("PASS: actual pinned queue retains duplicate IDs, cancels all matching IDs, rejects inserts while invalid slots occupy capacity, and dispatches across wrap; CPU/PI claims remain source-only")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
