#!/usr/bin/env python3
"""Build and execute the exact pinned ares PI_DMA_Read lifecycle fixture."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT / ".refs/ares"
OUT = ROOT / "target/ares-pi-read-lifecycle"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build():
    builder = load("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    prepare = load("queue_prepare", ROOT / "spikes/032-ares-queue-identity/prepare.py")
    source = (HERE / "driver.cpp").read_text()
    marker = "#endif\n\nstruct Fact {"
    assert source.count(marker) == 1
    # Common oracle driver imports nall::queue and the N64 global queue through
    # using-directives. Pin unqualified fixture references to the N64 instance.
    source = source.replace(marker, "#endif\n\n#define queue ares::Nintendo64::queue\n\nstruct Fact {")
    OUT.mkdir(parents=True, exist_ok=True)
    generated = HERE / "_driver.generated.cpp"
    generated.write_text(source)
    baseline_source = OUT / "baseline.generated.cpp"
    baseline_source.write_text(f'#define PLAID_PI_READ_SENSOR 0\n#include "{generated}"\n')
    try:
        baseline = builder.build(baseline_source, OUT / "baseline", extra_sources=(generated,))
        observed_dir = OUT / "observed"
        prepare.generate(REF, observed_dir / "include/nall/priority-queue.hpp")
        observed = builder.build(
            generated,
            observed_dir,
            raw_fetch_access=True,
            physical_fetch_access=True,
            rdram_scalar_access=True,
            pi_dma_access=True,
            queue_access=True,
            extra_sources=(HERE / "observer.hpp", ROOT / "spikes/032-ares-queue-identity/prepare.py"),
        )
        return baseline, observed
    finally:
        generated.unlink(missing_ok=True)


def phase(data, number):
    return next(x for x in data["facts"] if x["phase"] == number)


def queue_phase(data, number):
    return [x for x in data["queue_trace"] if x["phase"] == number]


def pi_phase(data, number):
    return [x for x in data["pi_trace"] if x["phase"] == number]


def request_reads(data, number, request):
    return [
        x for x in data["rdram_trace"]
        if x["phase"] == number and x["request"] == request and not x["write"]
    ]


def verify(data):
    f1, f2, f3, f4, f5, f6 = (phase(data, n) for n in range(1, 7))
    assert (f1["busy_request"], f1["interrupt_request"], f1["latch_request"]) == (1, 0, 0x77887788)
    assert (f1["busy_end"], f1["interrupt_end"]) == (0, 1)
    assert (f2["busy_request"], f2["interrupt_request"], f2["latch_request"]) == (1, 0, 0xF012F012)
    assert (f2["busy_end"], f2["interrupt_end"]) == (0, 0)
    assert f3["aux"] == 512
    assert (f3["busy_request"], f3["interrupt_request"], f3["latch_request"]) == (1, 0, 0x48AD48AD)
    assert (f3["busy_end"], f3["interrupt_end"]) == (1, 0)
    assert (f4["busy_end"], f4["interrupt_end"], f4["aux"]) == (0, 1, 2)
    assert (f5["busy_request"], f5["interrupt_request"], f5["latch_request"]) == (1, 0, 0x1A1B1A1B)
    assert (f5["busy_end"], f5["interrupt_end"]) == (0, 1)
    assert (f6["busy_request"], f6["interrupt_request"], f6["latch_request"]) == (1, 0, 0x3A3B3A3B)
    assert (f6["busy_end"], f6["interrupt_end"]) == (0, 1)

    requests = data["requests"]
    normal = requests["normal"]
    cancel = requests["cancel"]
    reject = requests["reject"]
    save = requests["save"]
    restore = requests["restore"]
    assert all((normal, cancel, reject, save, restore))
    assert len({normal, cancel, reject, save, restore}) == 5

    expected_reads = {
        1: ([0x1000, 0x1002, 0x1004, 0x1006], [0x1122, 0x3344, 0x5566, 0x7788], normal),
        2: ([0x1100, 0x1102, 0x1104, 0x1106], [0x99AA, 0xBBCC, 0xDDEE, 0xF012], cancel),
        3: ([0x1200, 0x1202, 0x1204, 0x1206], [0x1357, 0x2468, 0x369C, 0x48AD], reject),
        5: ([0x1300, 0x1302, 0x1304, 0x1306], [0x0A0B, 0x0C0D, 0x0E0F, 0x1A1B], save),
        6: ([0x1400, 0x1402, 0x1404, 0x1406], [0x2A2B, 0x2C2D, 0x2E2F, 0x3A3B], restore),
    }
    read_receipts = {}
    for p, (addresses, values, request) in expected_reads.items():
        reads = request_reads(data, p, request)
        assert len(reads) == 4
        assert [x["address"] for x in reads] == addresses
        assert [x["value"] for x in reads] == values
        assert len({x["size"] for x in reads}) == 1
        assert len({x["device"] for x in reads}) == 1
        read_receipts[p] = dict(size=reads[0]["size"], device=reads[0]["device"])

    # 1: request -> successful read-event insertion -> immediate backing reads ->
    # later valid removal -> common dmaFinished under the inherited identity.
    q1 = queue_phase(data, 1)
    p1 = pi_phase(data, 1)
    insert1 = [x for x in q1 if x["kind"] == 4 and x["request"] == normal and x["event"] == 0]
    assert len(insert1) == 1 and insert1[0]["token"]
    token1 = insert1[0]["token"]
    removal1 = [x for x in q1 if x["kind"] == 5 and x["valid"] and x["token"] == token1]
    completion1 = [x for x in p1 if x["kind"] == 8]
    reads1 = request_reads(data, 1, normal)
    assert len(removal1) == len(completion1) == 1
    assert (completion1[0]["request"], completion1[0]["token"]) == (normal, token1)
    assert insert1[0]["o"] < reads1[0]["o"] < reads1[-1]["o"] < removal1[0]["o"] < completion1[0]["o"]

    # 2: status reset invalidates the exact token after the synchronous copy.
    q2 = queue_phase(data, 2)
    p2 = pi_phase(data, 2)
    token2 = next(x["token"] for x in q2 if x["kind"] == 4 and x["request"] == cancel and x["event"] == 0)
    reads2 = request_reads(data, 2, cancel)
    cancel_event = next(x for x in q2 if x["kind"] == 8 and x["event"] == 0 and x["token"] == token2)
    assert reads2[-1]["o"] < cancel_event["o"]
    assert any(x["kind"] == 5 and not x["valid"] and x["token"] == token2 for x in q2)
    assert not [x for x in p2 if x["kind"] == 8]

    # 3: full queue rejection precedes four real RDRAM reads, but no token or completion exists.
    q3 = queue_phase(data, 3)
    p3 = pi_phase(data, 3)
    reject_event = next(x for x in q3 if x["kind"] == 2 and x["event"] == 0)
    reads3 = request_reads(data, 3, reject)
    assert reject_event["o"] < reads3[0]["o"]
    assert not [x for x in q3 if x["kind"] == 4 and x["request"] == reject and x["event"] == 0]
    assert not [x for x in p3 if x["kind"] == 8]

    # 4: equal event/deadline rows remain distinct and unowned.
    q4 = queue_phase(data, 4)
    p4 = pi_phase(data, 4)
    inserts4 = [x for x in q4 if x["kind"] == 4 and x["event"] == 0]
    assert len(inserts4) == 2
    assert inserts4[0]["clock"] == inserts4[1]["clock"]
    assert inserts4[0]["token"] != inserts4[1]["token"]
    assert all(x["request"] == 0 for x in inserts4)
    comps4 = [x for x in p4 if x["kind"] == 8]
    assert len(comps4) == 2
    assert {x["token"] for x in comps4} == {x["token"] for x in inserts4}
    assert all(x["request"] == 0 for x in comps4)

    # 5: save-only kind-9 boundary is valid=false and preserves the live token.
    q5 = queue_phase(data, 5)
    p5 = pi_phase(data, 5)
    token5 = next(x["token"] for x in q5 if x["kind"] == 4 and x["request"] == save and x["event"] == 0)
    saves = [x for x in q5 if x["kind"] == 9]
    assert len(saves) == 1 and not saves[0]["valid"]
    comp5 = [x for x in p5 if x["kind"] == 8]
    assert len(comp5) == 1 and (comp5[0]["request"], comp5[0]["token"]) == (save, token5)

    # 6: writing preserves, reset/load cuts. Real restored completion is left unknown.
    q6 = queue_phase(data, 6)
    p6 = pi_phase(data, 6)
    token6 = next(x["token"] for x in q6 if x["kind"] == 4 and x["request"] == restore and x["event"] == 0)
    serial6 = [x for x in q6 if x["kind"] == 9]
    assert len(serial6) == 2 and [x["valid"] for x in serial6] == [False, True]
    comp6 = [x for x in p6 if x["kind"] == 8]
    assert len(comp6) == 1 and (comp6[0]["request"], comp6[0]["token"]) == (0, 0)

    return dict(
        normal_request=normal,
        normal_token=token1,
        canceled_token=token2,
        rejected_request=reject,
        duplicate_tokens=[x["token"] for x in inserts4],
        save_only_token=token5,
        pre_restore_token=token6,
        read_receipts=read_receipts,
        queue_records=len(data["queue_trace"]),
        pi_records=len(data["pi_trace"]),
        rdram_records=len(data["rdram_trace"]),
    )


def main():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    subprocess.run(["python3", str(HERE / "source_guard.py")], check=True)
    baseline, observed = build()

    def call(exe, mode):
        return subprocess.check_output([str(exe), mode], text=True, timeout=60)

    baseline_raw = call(baseline, "plain")
    disabled_raw = call(observed, "plain")
    traced_raw = call(observed, "traced")
    repeat_raw = call(observed, "traced")
    assert traced_raw == repeat_raw
    base, disabled, traced = map(json.loads, (baseline_raw, disabled_raw, traced_raw))
    assert base["queue_trace"] == base["pi_trace"] == base["rdram_trace"] == []
    assert disabled["queue_trace"] == disabled["pi_trace"] == disabled["rdram_trace"] == []
    assert base["facts"] == disabled["facts"] == traced["facts"]
    assert base["state"] == disabled["state"] == traced["state"]
    result = verify(traced)
    receipt = dict(
        revision=REV,
        result=result,
        baseline_disabled_enabled_state_equal=True,
        repeat_trace_byte_identical=True,
        actual_pi_iowrite_read_request_executed=True,
        actual_rdram_dma_reads_observed=True,
        actual_queue_container_executed=True,
        actual_cpu_synchronize_executed=True,
        dispatch_to_dmafinished_join_observed=True,
        save_only_identity_preserved=True,
        load_identity_certified=False,
        hardware_timing_claimed=False,
        dispatch_is_byte_transfer_completion=False,
        traced_sha256=hashlib.sha256(traced_raw.encode()).hexdigest(),
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "traced.json").write_text(traced_raw)
    path = OUT / "results.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("ACTUAL_TRACE_SHA256=" + receipt["traced_sha256"])
    print("ACTUAL_RESULT_SHA256=" + hashlib.sha256(path.read_bytes()).hexdigest())
    print(json.dumps(receipt, sort_keys=True))
    print("PASS: actual pinned PI_DMA_Read copies precede dispatch; token identity survives cancellation rules and save, but not load")


if __name__ == "__main__":
    import os
    if os.name == 'nt':
        script = subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script],check=True)
    else:
        main()
