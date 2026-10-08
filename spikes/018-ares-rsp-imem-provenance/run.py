"""Run a bounded pinned-ares RSP IMEM provenance experiment."""
from pathlib import Path
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
OUTPUT = ROOT / "target/ares-rsp-imem-provenance-spike"
DRIVER = Path(__file__).with_name("driver.cpp")


def load_builder():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_traced(builder):
    out = OUTPUT / "traced-build"
    if out.exists():
        shutil.rmtree(out)
    # First generate/link the known-good headless recipe unmodified. We then
    # rebuild only with generated observer shadows; upstream checkout stays clean.
    builder.build(DRIVER, out)
    include = out / "include/n64/rdram/rdram.hpp"
    include.parent.mkdir(parents=True, exist_ok=True)
    ram = (REF / "ares/n64/rdram/rdram.hpp").read_text()
    marker = "      return Memory::Writable::read<Size>(address);"
    assert ram.count(marker) == 1
    replacement = """      u64 plaidValue = Memory::Writable::read<Size>(address);
      if(plaidRdramReadObserver) plaidRdramReadObserver(address, Size, (u32)device, plaidValue);
      return plaidValue;"""
    declarations = """// Project-owned research callbacks; no RDRAM/RSP object-layout changes.
using PlaidRdramReadObserver = void (*)(u32, u32, u32, u64);
using PlaidRspImemDmaWriteObserver = void (*)(u32, u32, u64);
using PlaidRspImemDirectWriteObserver = void (*)(u32, u32, bool);
using PlaidRspFetchObserver = void (*)(u32, u32);
inline PlaidRdramReadObserver plaidRdramReadObserver = nullptr;
inline PlaidRspImemDmaWriteObserver plaidRspImemDmaWriteObserver = nullptr;
inline PlaidRspImemDirectWriteObserver plaidRspImemDirectWriteObserver = nullptr;
inline PlaidRspFetchObserver plaidRspFetchObserver = nullptr;
"""
    include.write_text(declarations + ram.replace(marker, replacement))

    dma = (REF / "ares/n64/rsp/dma.cpp").read_text()
    marker = """        u64 data = rdram.ram.read<Dual>(dma.current.dramAddress, RBusDevice::SP_DMA);
        imem.write<Dual>(dma.current.pbusAddress, data);"""
    assert dma.count(marker) == 1
    dma = dma.replace(marker, marker + "\n        if(plaidRspImemDmaWriteObserver) plaidRspImemDmaWriteObserver(dma.current.dramAddress, dma.current.pbusAddress, data);")
    dma_path = out / "rsp_dma.cpp"; dma_path.write_text(dma)

    io = (REF / "ares/n64/rsp/io.cpp").read_text()
    marker = "    if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);"
    assert io.count(marker) == 1
    io = io.replace(marker, """    if(address & 0x1000) {
      recompiler.invalidate(address & 0xfff);
      imem.write<Word>(address, data);
      if(plaidRspImemDirectWriteObserver) plaidRspImemDirectWriteObserver(address & 0xfff, data, &thread != this);
      return;
    }""")
    io_path = out / "rsp_io.cpp"; io_path.write_text(io)

    rsp_src = (REF / "ares/n64/rsp/rsp.cpp").read_text()
    fetch_marker = """  pipeline.address = ipu.pc;
  pipeline.instruction = instruction;
  debugger.instruction();"""
    assert rsp_src.count(fetch_marker) == 1
    rsp_src = rsp_src.replace(fetch_marker, """  pipeline.address = ipu.pc;
  pipeline.instruction = instruction;
  if(plaidRspFetchObserver) plaidRspFetchObserver(pipeline.address, instruction);
  debugger.instruction();""")
    replacements = {"dma.cpp": dma_path, "io.cpp": io_path}
    rsp_src = re.sub(r'#include "([^"]+)"', lambda m:
        f'#include "{replacements.get(m[1], REF / "ares/n64/rsp" / m[1])}"', rsp_src)
    rsp_path = out / "rsp.cpp"; rsp_path.write_text(rsp_src)

    unity = (out / "n64.cpp").read_text()
    marker = "#include <n64/rsp/rsp.cpp>"
    assert unity.count(marker) == 1
    (out / "n64.cpp").write_text(unity.replace(marker, f'#include "{rsp_path}"'))

    flags = ["-O1","-std=c++20","-msse4.1","-DSLJIT_HAVE_CONFIG_PRE=1","-DSLJIT_HAVE_CONFIG_POST=1","-DPLAID_RSP_OBSERVER=1"]
    includes = [out / "include", *(REF / p for p in ("ares","nall",".","thirdparty","thirdparty/xxhash","ares/n64/system"))]
    include_flags = [part for path in includes for part in ("-I", str(path))]
    sources = [DRIVER,out / "core.cpp",out / "n64.cpp",REF / "ares/component/processor/sm5k/sm5k.cpp",
        REF / "ares/ares/memory/fixed-allocator.cpp",REF / "nall/nall/nall.cpp",REF / "thirdparty/sljitAllocator.cpp"]
    exe = out / "oracle-traced"
    with (out / "traced-build.log").open("w") as log:
        try:
            subprocess.run(["g++",*flags,*include_flags,*map(str,sources),str(out / "sljit.o"),str(out / "libco.o"),
                "-pthread","-ldl","-o",str(exe)],check=True,stdout=log,stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print("\n".join((out / "traced-build.log").read_text().splitlines()[-40:]))
            raise
    return exe


def lineage(events):
    bytes_ = [None] * 4096
    generation = 0
    resolved_fetches = []
    last = None
    for event in events:
        kind = event["kind"]
        if kind == "rdram_read":
            last = event
            continue
        if kind == "imem_dma_write":
            generation += 1
            matched = (last is not None and last["kind"] == "rdram_read"
                and last["seq"] + 1 == event["seq"]
                and last["dram"] == event["dram"] and last["bytes"] == event["bytes"]
                and last["value"] == event["value"])
            payload = event["value"].to_bytes(event["bytes"], "big")
            for i, value in enumerate(payload):
                source = ("rdram", event["dram"] + i) if matched else ("unknown", None)
                bytes_[(event["imem"] + i) & 0xfff] = (generation, source, value, event["seq"])
            last = event
            continue
        if kind == "imem_direct_write":
            generation += 1
            payload = event["value"].to_bytes(4, "big")
            for i, value in enumerate(payload):
                bytes_[(event["imem"] + i) & 0xfff] = (generation, ("direct_cpu" if event["origin_cpu"] else "direct_rsp", None), value, event["seq"])
            last = event
            continue
        if kind == "fetch":
            cells = [bytes_[(event["pc"] + i) & 0xfff] for i in range(4)]
            word = event["word"].to_bytes(4, "big")
            if any(cell is None for cell in cells) or bytes(cell[2] for cell in cells) != word:
                resolution = {"kind":"unknown"}
            elif len({cell[0] for cell in cells}) != 1:
                resolution = {"kind":"mixed_generation"}
            elif all(cell[1][0] == "rdram" for cell in cells) and [cell[1][1] for cell in cells] == list(range(cells[0][1][1], cells[0][1][1] + 4)):
                resolution = {"kind":"rdram","dram":cells[0][1][1],"generation":cells[0][0],"write_seq":cells[0][3]}
            elif len({cell[1][0] for cell in cells}) == 1 and cells[0][1][0].startswith("direct_"):
                resolution = {"kind":cells[0][1][0],"generation":cells[0][0],"write_seq":cells[0][3]}
            else:
                resolution = {"kind":"unknown","generation":cells[0][0],"write_seq":cells[0][3]}
            resolved_fetches.append({"seq":event["seq"],"pc":event["pc"],"word":event["word"],**resolution})
            last = event
    return resolved_fetches


def worker():
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=REF,text=True).strip() == REV
    subprocess.run(["git","diff","--quiet","HEAD"],cwd=REF,check=True)
    builder = load_builder()
    baseline = builder.build(DRIVER, OUTPUT / "baseline-build")
    traced = build_traced(builder)
    plain_raw = subprocess.check_output([str(baseline),"plain"],text=True,timeout=30)
    traced_raw = subprocess.check_output([str(traced),"traced"],text=True,timeout=30)
    repeat_raw = subprocess.check_output([str(traced),"traced"],text=True,timeout=30)
    plain, observed, repeat = map(json.loads, (plain_raw,traced_raw,repeat_raw))
    assert traced_raw == repeat_raw
    assert plain["events"] == [] and observed["events"] and plain["state"] == observed["state"] == repeat["state"]
    fetches = lineage(observed["events"])
    expected = [
        (0x000,"rdram",0x1000),(0x004,"rdram",0x1004),
        (0x000,"rdram",0x2000),(0x000,"rdram",0x3000),
        (0x020,"rdram",0x4000),(0x028,"rdram",0x4010),
        (0x000,"direct_cpu",None),(0x060,"unknown",None),
    ]
    got = [(f["pc"],f["kind"],f.get("dram")) for f in fetches]
    assert got == expected, (got, fetches)
    # Identical bytes at the same IMEM PC nevertheless come from a distinct reload generation.
    assert fetches[0]["word"] == fetches[2]["word"] and fetches[0]["generation"] != fetches[2]["generation"]
    # Changed reload and direct write must also supersede the prior resident generation.
    assert fetches[3]["generation"] > fetches[2]["generation"]
    assert fetches[6]["generation"] > fetches[3]["generation"]
    # DMEM reads are visible at the backing boundary but can never create an IMEM write witness.
    assert [e["dram"] for e in observed["events"] if e["kind"] == "rdram_read" and 0x5000 <= e["dram"] < 0x5008] == [0x5000,0x5004]
    assert not any(e["kind"] == "imem_dma_write" and 0x5000 <= e["dram"] < 0x5008 for e in observed["events"])
    # OOB SP DMA writes zero into IMEM but has no successful RDRAM read witness.
    oob = next(e for e in observed["events"] if e["kind"] == "imem_dma_write" and e["imem"] == 0x60)
    assert oob["value"] == 0 and not any(e["kind"] == "rdram_read" and e["dram"] == 8 * 1024 * 1024 for e in observed["events"])
    result = {"revision":REV,"driver_sha256":hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
        "state":observed["state"],"events":observed["events"],"resolved_fetches":fetches,
        "neutrality":plain["state"] == observed["state"],"repeat_deterministic":traced_raw == repeat_raw}
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT / "results.json").write_text(json.dumps(result,indent=2)+"\n")
    print("PASS: exact SP_DMA backing reads join to IMEM generations/fetches; reload/direct-write replace lineage; DMEM stays separate; OOB source remains unknown")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
