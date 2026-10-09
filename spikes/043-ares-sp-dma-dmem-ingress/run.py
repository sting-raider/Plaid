"""Run exact pinned-ares RDRAM -> SP DMEM ingress provenance experiment."""
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
OUTPUT = ROOT / "target/ares-sp-dma-dmem-ingress"
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

    # Observe only successful ordinary RDRAM reads. This marker is after the
    # pinned bounds/translation checks; OOB reads return before it.
    include = out / "include/n64/rdram/rdram.hpp"
    include.parent.mkdir(parents=True, exist_ok=True)
    ram = (REF / "ares/n64/rdram/rdram.hpp").read_text()
    marker = "      return Memory::Writable::read<Size>(address);"
    assert ram.count(marker) == 1
    ram = ram.replace(marker, """      u64 plaidValue = Memory::Writable::read<Size>(address);
      if(plaidRdramReadObserver) plaidRdramReadObserver(address, Size, (u32)device, plaidValue);
      return plaidValue;""")
    declarations = """// Project-owned research callbacks; no reference object-layout changes.
using PlaidRdramReadObserver = void (*)(u32, u32, u32, u64);
using PlaidRspDmemDmaWriteObserver = void (*)(u32, u32, u32);
using PlaidRspDmemDirectWriteObserver = void (*)(u32, u32, bool);
inline PlaidRdramReadObserver plaidRdramReadObserver = nullptr;
inline PlaidRspDmemDmaWriteObserver plaidRspDmemDmaWriteObserver = nullptr;
inline PlaidRspDmemDirectWriteObserver plaidRspDmemDirectWriteObserver = nullptr;
"""
    include.write_text(declarations + ram)

    dma = (REF / "ares/n64/rsp/dma.cpp").read_text()
    marker = """        u32 dataLo = rdram.ram.read<Word>(dma.current.dramAddress + 0, RBusDevice::SP_DMA);
        u32 dataHi = rdram.ram.read<Word>(dma.current.dramAddress + 4, RBusDevice::SP_DMA);
        dmem.write<Word>(dma.current.pbusAddress + 0, dataLo);
        dmem.write<Word>(dma.current.pbusAddress + 4, dataHi);"""
    assert dma.count(marker) == 1
    replacement = """        u32 dataLo = rdram.ram.read<Word>(dma.current.dramAddress + 0, RBusDevice::SP_DMA);
        u32 dataHi = rdram.ram.read<Word>(dma.current.dramAddress + 4, RBusDevice::SP_DMA);
        dmem.write<Word>(dma.current.pbusAddress + 0, dataLo);
        if(plaidRspDmemDmaWriteObserver) plaidRspDmemDmaWriteObserver(dma.current.dramAddress + 0, dma.current.pbusAddress + 0, dataLo);
        dmem.write<Word>(dma.current.pbusAddress + 4, dataHi);
        if(plaidRspDmemDmaWriteObserver) plaidRspDmemDmaWriteObserver(dma.current.dramAddress + 4, dma.current.pbusAddress + 4, dataHi);"""
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

    flags = ["-O1", "-std=c++20", "-msse4.1", "-DSLJIT_HAVE_CONFIG_PRE=1", "-DSLJIT_HAVE_CONFIG_POST=1", "-DPLAID_DMEM_INGRESS_OBSERVER=1"]
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


def replay(events):
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    cells = [None] * 4096
    outstanding = []
    writes = []
    generation = 0
    for event in events:
        kind = event["kind"]
        if kind == "rdram_read":
            assert event["bytes"] == 4
            outstanding.append({**event, "used": False})
            continue
        if kind == "dmem_dma_write":
            assert event["bytes"] == 4
            generation += 1
            matches = [r for r in outstanding if not r["used"] and r["seq"] < event["seq"]
                and r["dram"] == event["dram"] and r["bytes"] == 4 and r["value"] == event["value"]]
            if len(matches) == 1:
                matches[0]["used"] = True
                origin = ("rdram", event["dram"])
                read_seq = matches[0]["seq"]
            elif len(matches) == 0:
                origin = ("unknown", None)
                read_seq = None
            else:
                raise AssertionError("ambiguous backing read")
            payload = event["value"].to_bytes(4, "big")
            for i, value in enumerate(payload):
                cells[(event["dmem"] + i) & 0xfff] = (generation, origin, value, event["seq"], read_seq)
            writes.append({**event, "generation": generation, "origin_kind": origin[0], "origin": origin[1], "read_seq": read_seq})
            continue
        if kind == "dmem_direct_write":
            assert event["bytes"] == 4
            generation += 1
            origin = ("direct_cpu" if event["origin_cpu"] else "direct_other", None)
            payload = event["value"].to_bytes(4, "big")
            for i, value in enumerate(payload):
                cells[(event["dmem"] + i) & 0xfff] = (generation, origin, value, event["seq"], None)
            writes.append({**event, "generation": generation, "origin_kind": origin[0], "origin": None, "read_seq": None})
            continue
        raise AssertionError("unknown event kind")
    return cells, writes


def validate(events):
    cells, writes = replay(events)
    dma = [w for w in writes if w["kind"] == "dmem_dma_write"]
    direct = [w for w in writes if w["kind"] == "dmem_direct_write"]

    # First 8-byte fragment: both successful reads happen before either sink.
    prefix = events[:4]
    assert [e["kind"] for e in prefix] == ["rdram_read", "rdram_read", "dmem_dma_write", "dmem_dma_write"]
    assert [e.get("dram") for e in prefix] == [0x1000, 0x1004, 0x1000, 0x1004]
    assert prefix[0]["value"] == prefix[1]["value"] == prefix[2]["value"] == prefix[3]["value"] == 0x11223344
    # The first sink is not adjacent to its producer read; nearest-payload would choose the wrong address.
    assert prefix[2]["seq"] - next(w for w in dma if w["dram"] == 0x1000)["read_seq"] == 2

    known = [(w["dmem"], w["origin"]) for w in dma if w["origin_kind"] == "rdram"]
    expected_known = [
        (0x000,0x1000),(0x004,0x1004),
        (0x000,0x2000),(0x004,0x2004),
        (0x020,0x3000),(0x024,0x3004),(0x028,0x3010),(0x02c,0x3014),
        (0xff8,0x4000),(0xffc,0x4004),(0x000,0x4008),(0x004,0x400c),
    ]
    assert known == expected_known, known
    assert not any(w["origin"] in (0x3008,0x300c) for w in dma)

    unknown = [(w["dmem"], w["value"]) for w in dma if w["origin_kind"] == "unknown"]
    assert unknown == [(0x060,0),(0x064,0)], unknown

    # Equal-byte reload at the same DMEM destinations still minted fresh writer generations.
    first0 = next(w for w in dma if w["dram"] == 0x1000)
    reload0 = next(w for w in dma if w["dram"] == 0x2000)
    assert first0["value"] == reload0["value"] and first0["generation"] != reload0["generation"]

    # Wrap leaves the later 0x4008/0x400c generations resident at 0x000/0x004.
    for dmem, dram in ((0x000,0x4008),(0x004,0x400c),(0xff8,0x4000),(0xffc,0x4004)):
        cell = cells[dmem]
        assert cell is not None and cell[1] == ("rdram", dram)

    # Same-value CPU overwrite at 0x020 cuts only that Word's DMA lineage.
    assert len(direct) == 1 and direct[0]["origin_cpu"] and direct[0]["dmem"] == 0x020
    prior = next(w for w in dma if w["dram"] == 0x3000)
    assert direct[0]["value"] == prior["value"] and direct[0]["generation"] > prior["generation"]
    assert all(cells[0x020+i][1][0] == "direct_cpu" for i in range(4))
    assert all(cells[0x024+i][1] == ("rdram",0x3004) for i in range(4))

    # Demonstrate the tempting payload-only rule is already wrong on the real trace.
    mismatches = []
    reads_seen = []
    for event in events:
        if event["kind"] == "rdram_read":
            reads_seen.append(event)
        elif event["kind"] == "dmem_dma_write" and event["dram"] < 0x2000:
            candidates = [r for r in reads_seen if r["value"] == event["value"]]
            if candidates:
                guessed = candidates[-1]["dram"]
                if guessed != event["dram"]:
                    mismatches.append({"sink_seq":event["seq"],"expected_dram":event["dram"],"payload_guess":guessed})
    assert mismatches, "equal payload adversary did not break latest-value rule"
    return {"writes": writes, "payload_only_mismatches": mismatches}


def reject_forged(events):
    rejected = []
    cases = []

    x = copy.deepcopy(events)
    first = next(e for e in x if e["kind"] == "dmem_dma_write" and e["dram"] == 0x1000)
    first["dram"] = 0x1004  # equal payload decoy
    cases.append(("equal_payload_wrong_source", x))

    x = copy.deepcopy(events)
    del x[next(i for i,e in enumerate(x) if e["kind"] == "rdram_read" and e["dram"] == 0x3000)]
    for i,e in enumerate(x,1): e["seq"] = i
    cases.append(("missing_successful_read", x))

    x = copy.deepcopy(events)
    poison = next(e for e in x if e["kind"] == "dmem_dma_write" and e["dram"] == 0x3010)
    poison["dram"] = 0x3008
    cases.append(("skip_poison_join", x))

    x = copy.deepcopy(events)
    direct = next(e for e in x if e["kind"] == "dmem_direct_write")
    direct["origin_cpu"] = False
    cases.append(("forged_cpu_overwrite_identity", x))

    x = copy.deepcopy(events)
    x[1]["seq"] = x[0]["seq"]
    cases.append(("duplicate_ordinal", x))

    for name, forged in cases:
        try:
            validate(forged)
        except (AssertionError, StopIteration):
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
    assert forged == ["equal_payload_wrong_source","missing_successful_read","skip_poison_join","forged_cpu_overwrite_identity","duplicate_ordinal"]

    result = {
        "revision": REV,
        "plaid_base": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
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
    print("PASS: DMEM ingress uses paired Word reads/sinks; exact source-address chronology survives equal payloads, wrap/skip/OOB and CPU overwrite", flush=True)


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
