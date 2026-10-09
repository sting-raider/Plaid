"""Run exact pinned-ares SP DMEM -> RDRAM DMA egress provenance experiment."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
PLAID_BASE = "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256"
OUTPUT = ROOT / "target/ares-sp-dma-dmem-egress"
DRIVER = Path(__file__).with_name("driver.cpp")


def load_builder():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_hash(path):
    return hashlib.sha256((REF / path).read_bytes()).hexdigest()


def build_traced(builder):
    out = OUTPUT / "traced-build"
    if out.exists():
        shutil.rmtree(out)
    builder.build(DRIVER, out)

    # Observe only completed successful ordinary RDRAM storage effects. The callback
    # is after translation/bounds checks and after both normal and hidden-RAM updates.
    include = out / "include/n64/rdram/rdram.hpp"
    include.parent.mkdir(parents=True, exist_ok=True)
    ram = (REF / "ares/n64/rdram/rdram.hpp").read_text()
    marker = """      Memory::Writable::write<Size>(address, value);
      self.hidden.update<Size>(address, value);"""
    assert ram.count(marker) == 1
    ram = ram.replace(marker, marker + """
      if(plaidRdramWriteObserver) plaidRdramWriteObserver(address, Size, (u32)device, value);""")
    declarations = """// Project-owned research callbacks; no reference object-layout changes.
using PlaidRdramWriteObserver = void (*)(u32, u32, u32, u64);
using PlaidRspDmemDmaReadObserver = void (*)(u32, u32, u32);
using PlaidRspDmemDirectWriteObserver = void (*)(u32, u32, bool);
inline PlaidRdramWriteObserver plaidRdramWriteObserver = nullptr;
inline PlaidRspDmemDmaReadObserver plaidRspDmemDmaReadObserver = nullptr;
inline PlaidRspDmemDirectWriteObserver plaidRspDmemDirectWriteObserver = nullptr;
"""
    include.write_text(declarations + ram)

    dma = (REF / "ares/n64/rsp/dma.cpp").read_text()
    marker = """        u32 dataLo = dmem.read<Word>(dma.current.pbusAddress + 0);
        u32 dataHi = dmem.read<Word>(dma.current.pbusAddress + 4);
        rdram.ram.write<Word>(dma.current.dramAddress + 0, dataLo, RBusDevice::SP_DMA);
        rdram.ram.write<Word>(dma.current.dramAddress + 4, dataHi, RBusDevice::SP_DMA);"""
    assert dma.count(marker) == 1
    replacement = """        u32 dataLo = dmem.read<Word>(dma.current.pbusAddress + 0);
        if(plaidRspDmemDmaReadObserver) plaidRspDmemDmaReadObserver(dma.current.pbusAddress + 0, dma.current.dramAddress + 0, dataLo);
        u32 dataHi = dmem.read<Word>(dma.current.pbusAddress + 4);
        if(plaidRspDmemDmaReadObserver) plaidRspDmemDmaReadObserver(dma.current.pbusAddress + 4, dma.current.dramAddress + 4, dataHi);
        rdram.ram.write<Word>(dma.current.dramAddress + 0, dataLo, RBusDevice::SP_DMA);
        rdram.ram.write<Word>(dma.current.dramAddress + 4, dataHi, RBusDevice::SP_DMA);"""
    dma_path = out / "rsp_dma.cpp"
    dma_path.write_text(dma.replace(marker, replacement))

    io = (REF / "ares/n64/rsp/io.cpp").read_text()
    marker = "    else                 return dmem.write<Word>(address, data);"
    assert io.count(marker) == 1
    replacement = """    else {
      dmem.write<Word>(address, data);
      if(plaidRspDmemDirectWriteObserver) plaidRspDmemDirectWriteObserver(address & 0xfff, data, &thread != this);
      return;
    }"""
    io_path = out / "rsp_io.cpp"
    io_path.write_text(io.replace(marker, replacement))

    rsp_src = (REF / "ares/n64/rsp/rsp.cpp").read_text()
    replacements = {"dma.cpp": dma_path, "io.cpp": io_path}
    rsp_src = re.sub(r'#include "([^"]+)"', lambda m:
        f'#include "{replacements.get(m[1], REF / "ares/n64/rsp" / m[1])}"', rsp_src)
    rsp_path = out / "rsp.cpp"
    rsp_path.write_text(rsp_src)

    unity = (out / "n64.cpp").read_text()
    marker = "#include <n64/rsp/rsp.cpp>"
    assert unity.count(marker) == 1
    (out / "n64.cpp").write_text(unity.replace(marker, f'#include "{rsp_path}"'))

    flags = ["-O1", "-std=c++20", "-msse4.1", "-DSLJIT_HAVE_CONFIG_PRE=1", "-DSLJIT_HAVE_CONFIG_POST=1", "-DPLAID_DMEM_EGRESS_OBSERVER=1"]
    includes = [out / "include", *(REF / p for p in ("ares", "nall", ".", "thirdparty", "thirdparty/xxhash", "ares/n64/system"))]
    include_flags = [part for path in includes for part in ("-I", str(path))]
    sources = [DRIVER, out / "core.cpp", out / "n64.cpp", REF / "ares/component/processor/sm5k/sm5k.cpp",
        REF / "ares/ares/memory/fixed-allocator.cpp", REF / "nall/nall/nall.cpp", REF / "thirdparty/sljitAllocator.cpp"]
    exe = out / "oracle-traced"
    with (out / "traced-build.log").open("w", encoding="utf-8") as log:
        try:
            subprocess.run(["g++", *flags, *include_flags, *map(str, sources), str(out / "sljit.o"), str(out / "libco.o"),
                "-pthread", "-ldl", "-o", str(exe)], check=True, stdout=log, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print("\n".join((out / "traced-build.log").read_text(encoding="utf-8").splitlines()[-80:]), flush=True)
            raise
    return exe


def payload_bytes(value):
    return int(value).to_bytes(4, "big")


def replay(events):
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    dmem = [None] * 4096
    reads = []
    sinks = []

    for event in events:
        kind = event["kind"]
        if kind in ("dmem_direct_write", "dmem_foreign_write"):
            assert event["bytes"] == 4
            origin = ("cpu", event["seq"]) if kind == "dmem_direct_write" and event["origin_cpu"] else ("unknown", event["seq"])
            for i, byte in enumerate(payload_bytes(event["value"])):
                dmem[(event["dmem"] + i) & 0xfff] = {"origin": origin, "value": byte, "writer_seq": event["seq"]}
            continue

        if kind == "dmem_dma_read":
            assert event["bytes"] == 4
            snapshot = []
            for i, byte in enumerate(payload_bytes(event["value"])):
                cell = dmem[(event["dmem"] + i) & 0xfff]
                if cell is not None and cell["value"] == byte:
                    snapshot.append(cell["origin"])
                else:
                    snapshot.append(("unknown", None))
            reads.append({**event, "used": False, "snapshot": snapshot})
            continue

        if kind == "rdram_write":
            assert event["bytes"] == 4
            matches = [r for r in reads if not r["used"] and r["seq"] < event["seq"]
                       and r["dram"] == event["dram"] and r["value"] == event["value"]]
            if len(matches) != 1:
                raise AssertionError(f"expected one concrete DMEM read for sink {event}: {matches}")
            read = matches[0]
            read["used"] = True
            sinks.append({**event, "read_seq": read["seq"], "dmem": read["dmem"], "source": read["snapshot"]})
            continue

        raise AssertionError("unknown event kind: " + kind)
    return reads, sinks


def source_writer(sink):
    ids = {origin for origin in sink["source"]}
    if len(ids) == 1:
        return next(iter(ids))
    return ("mixed", tuple(sorted(ids, key=str)))


def validate(events):
    reads, sinks = replay(events)
    by_dram = {s["dram"]: s for s in sinks}
    expected = {
        0x1000:0x000,0x1004:0x004,0x2000:0x000,0x2004:0x004,
        0x3000:0x020,0x3004:0x024,0x3010:0x028,0x3014:0x02c,
        0x4000:0xff8,0x4004:0xffc,0x4008:0x000,0x400c:0x004,
        0x5000:0x020,0x5004:0x024,0x6000:0x070,0x6004:0x074,
    }
    assert {k: by_dram[k]["dmem"] for k in expected} == expected
    assert 0x3008 not in by_dram and 0x300c not in by_dram

    # OOB destination consumed the two source reads but no successful backing write callback fired.
    oob = [r for r in reads if r["dram"] >= 8 * 1024 * 1024]
    assert len(oob) == 2
    assert not any(s["dram"] >= 8 * 1024 * 1024 for s in sinks)

    # First equal-valued fragment reads both source Words before the first RDRAM sink.
    r0 = next(r for r in reads if r["dram"] == 0x1000)
    r1 = next(r for r in reads if r["dram"] == 0x1004)
    w0 = by_dram[0x1000]
    assert r0["value"] == r1["value"] == w0["value"] == 0x11223344
    assert r0["seq"] < r1["seq"] < w0["seq"]

    # Byte-identical reload uses fresh CPU writer identities.
    assert source_writer(by_dram[0x1000])[0] == "cpu"
    assert source_writer(by_dram[0x2000])[0] == "cpu"
    assert source_writer(by_dram[0x1000]) != source_writer(by_dram[0x2000])

    # Same-value overwrite at 0x020 must replace the writer generation used by 0x5000.
    assert by_dram[0x3000]["value"] == by_dram[0x5000]["value"]
    assert source_writer(by_dram[0x3000])[0] == "cpu"
    assert source_writer(by_dram[0x5000])[0] == "cpu"
    assert source_writer(by_dram[0x3000]) != source_writer(by_dram[0x5000])

    # Measured foreign same-value write cuts only the first Word to UNKNOWN.
    assert source_writer(by_dram[0x6000])[0] == "unknown"
    assert source_writer(by_dram[0x6004])[0] == "cpu"

    # Demonstrate the real trace breaks a latest-equal-payload heuristic.
    reads_seen = []
    mismatches = []
    for event in events:
        if event["kind"] == "dmem_dma_read":
            reads_seen.append(event)
        elif event["kind"] == "rdram_write" and event["dram"] in (0x1000, 0x1004):
            candidates = [r for r in reads_seen if r["value"] == event["value"]]
            guessed = candidates[-1]
            actual = by_dram[event["dram"]]
            if guessed["dmem"] != actual["dmem"]:
                mismatches.append({"sink_seq": event["seq"], "expected_dmem": actual["dmem"], "payload_guess_dmem": guessed["dmem"]})
    assert mismatches

    return {"sinks": sinks, "payload_only_mismatches": mismatches}


def renumber(events):
    for i, event in enumerate(events, 1):
        event["seq"] = i


def reject_forged(events):
    cases = []

    x = copy.deepcopy(events)
    next(e for e in x if e["kind"] == "dmem_dma_read" and e["dram"] == 0x1000)["dram"] = 0x1004
    cases.append(("equal_payload_wrong_lane", x))

    x = copy.deepcopy(events)
    del x[next(i for i,e in enumerate(x) if e["kind"] == "dmem_dma_read" and e["dram"] == 0x3000)]
    renumber(x)
    cases.append(("missing_source_read", x))

    x = copy.deepcopy(events)
    next(e for e in x if e["kind"] == "rdram_write" and e["dram"] == 0x3010)["dram"] = 0x3008
    cases.append(("skip_poison_sink", x))

    x = copy.deepcopy(events)
    del x[next(i for i,e in enumerate(x) if e["kind"] == "dmem_direct_write" and e["dmem"] == 0x020 and
          i > next(j for j,q in enumerate(x) if q["kind"] == "rdram_write" and q["dram"] == 0x3014))]
    renumber(x)
    cases.append(("same_value_overwrite_removed", x))

    x = copy.deepcopy(events)
    del x[next(i for i,e in enumerate(x) if e["kind"] == "dmem_foreign_write")]
    renumber(x)
    cases.append(("foreign_same_value_mutation_removed", x))

    x = copy.deepcopy(events)
    x[1]["seq"] = x[0]["seq"]
    cases.append(("duplicate_ordinal", x))

    rejected = []
    for name, forged in cases:
        try:
            validate(forged)
        except (AssertionError, StopIteration, KeyError):
            rejected.append(name)
        else:
            raise AssertionError("forged history accepted: " + name)
    return rejected


def parse(raw):
    rows = [line for line in raw.splitlines() if line.startswith("{")]
    assert len(rows) == 1, raw
    return json.loads(rows[0])


def worker():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    builder = load_builder()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    baseline = builder.build(DRIVER, OUTPUT / "baseline-build")
    traced = build_traced(builder)

    baseline_raw = subprocess.check_output([str(baseline), "plain"], text=True, timeout=30)
    disabled_raw = subprocess.check_output([str(traced), "plain"], text=True, timeout=30)
    traced_raw = subprocess.check_output([str(traced), "traced"], text=True, timeout=30)
    repeat_raw = subprocess.check_output([str(traced), "traced"], text=True, timeout=30)
    baseline_json, disabled, observed, repeat = map(parse, (baseline_raw, disabled_raw, traced_raw, repeat_raw))
    assert traced_raw == repeat_raw and observed == repeat
    assert baseline_json["events"] == [] and disabled["events"] == [] and observed["events"]
    assert baseline_json["state"] == disabled["state"] == observed["state"] == repeat["state"]

    audit = validate(observed["events"])
    forged = reject_forged(observed["events"])
    expected_forged = ["equal_payload_wrong_lane","missing_source_read","skip_poison_sink",
                       "same_value_overwrite_removed","foreign_same_value_mutation_removed","duplicate_ordinal"]
    assert forged == expected_forged

    result = {
        "revision": REV,
        "plaid_base": PLAID_BASE,
        "driver_sha256": hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
        "source_sha256": {
            "ares/n64/rdram/rdram.hpp": source_hash("ares/n64/rdram/rdram.hpp"),
            "ares/n64/rsp/dma.cpp": source_hash("ares/n64/rsp/dma.cpp"),
            "ares/n64/rsp/io.cpp": source_hash("ares/n64/rsp/io.cpp"),
        },
        "neutrality": baseline_json["state"] == disabled["state"] == observed["state"],
        "repeat_deterministic": traced_raw == repeat_raw,
        "state": observed["state"],
        "event_count": len(observed["events"]),
        "events": observed["events"],
        "audit": audit,
        "forged_histories_rejected": forged,
    }
    path = OUTPUT / "results.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "event_count": result["event_count"],
        "neutrality": result["neutrality"],
        "repeat_deterministic": result["repeat_deterministic"],
        "payload_only_mismatches": audit["payload_only_mismatches"],
        "forged_histories_rejected": forged,
    }, sort_keys=True), flush=True)
    print("RESULT_SHA256=" + hashlib.sha256(path.read_bytes()).hexdigest(), flush=True)
    print("PASS: DMEM egress requires exact measured source-read/sink lanes; equal payloads, skip/wrap/OOB and same-value mutations remain distinct", flush=True)


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
