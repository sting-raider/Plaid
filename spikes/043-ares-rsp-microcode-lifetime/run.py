"""Execute and adversarially verify the bounded pinned-ares RSP microcode lifetime experiment."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
OUTPUT = ROOT / "target/ares-rsp-microcode-lifetime"
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
    builder.build(DRIVER, out)

    declarations = r'''// Plaid research-only callbacks. No RSP/RDRAM object layout changes.
using PlaidRspDmaPromoteObserver = void (*)(u64,u32,u32,u32,u32,u32,u32,bool,bool);
using PlaidRdramReadObserver = void (*)(u64,u32,u32,u32,u64);
using PlaidRspImemWriteObserver = void (*)(u64,u32,u32,u64);
using PlaidRspDmaCompleteObserver = void (*)(u64);
using PlaidRspImemDirectWriteObserver = void (*)(u32,u32,bool);
using PlaidRspFetchObserver = void (*)(u32,u32);
inline PlaidRspDmaPromoteObserver plaidRspDmaPromoteObserver = nullptr;
inline PlaidRdramReadObserver plaidRdramReadObserver = nullptr;
inline PlaidRspImemWriteObserver plaidRspImemWriteObserver = nullptr;
inline PlaidRspDmaCompleteObserver plaidRspDmaCompleteObserver = nullptr;
inline PlaidRspImemDirectWriteObserver plaidRspImemDirectWriteObserver = nullptr;
inline PlaidRspFetchObserver plaidRspFetchObserver = nullptr;
inline u64 plaidRspDmaTransferId = 0;
'''

    ram = (REF / "ares/n64/rdram/rdram.hpp").read_text()
    marker = "      return Memory::Writable::read<Size>(address);"
    assert ram.count(marker) == 1
    ram = ram.replace(marker, r'''      u64 plaidValue = Memory::Writable::read<Size>(address);
      if(plaidRdramReadObserver) plaidRdramReadObserver(plaidRspDmaTransferId, address, Size, (u32)device, plaidValue);
      return plaidValue;''')
    include = out / "include/n64/rdram/rdram.hpp"
    include.parent.mkdir(parents=True, exist_ok=True)
    include.write_text(declarations + ram)

    dma = (REF / "ares/n64/rsp/dma.cpp").read_text()
    promote = r'''    dma.current = dma.pending;
    dma.busy    = dma.full;
    dma.full    = {0,0};
    dmaQueue((dma.current.length+8) / 8 * 3, thread);'''
    assert dma.count(promote) == 1
    dma = dma.replace(promote, r'''    dma.current = dma.pending;
    dma.busy    = dma.full;
    dma.full    = {0,0};
    plaidRspDmaTransferId += 1;
    if(plaidRspDmaPromoteObserver) plaidRspDmaPromoteObserver(
      plaidRspDmaTransferId, dma.current.pbusRegion, dma.current.pbusAddress,
      dma.current.dramAddress, dma.current.length, dma.current.count, dma.current.skip,
      dma.busy.read, dma.busy.write);
    dmaQueue((dma.current.length+8) / 8 * 3, thread);''')
    write = r'''        u64 data = rdram.ram.read<Dual>(dma.current.dramAddress, RBusDevice::SP_DMA);
        imem.write<Dual>(dma.current.pbusAddress, data);'''
    assert dma.count(write) == 1
    dma = dma.replace(write, write + r'''
        if(plaidRspImemWriteObserver) plaidRspImemWriteObserver(
          plaidRspDmaTransferId, dma.current.dramAddress, dma.current.pbusAddress, data);''')
    complete = r'''  } else {
    dma.busy = {0,0};
    dma.current.length = 0xFF8;
    dmaTransferStart(*this);
  }'''
    assert dma.count(complete) == 1
    dma = dma.replace(complete, r'''  } else {
    if(plaidRspDmaCompleteObserver) plaidRspDmaCompleteObserver(plaidRspDmaTransferId);
    dma.busy = {0,0};
    dma.current.length = 0xFF8;
    dmaTransferStart(*this);
  }''')
    dma_path = out / "rsp_dma.cpp"
    dma_path.write_text(dma)

    io = (REF / "ares/n64/rsp/io.cpp").read_text()
    direct = "    if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);"
    assert io.count(direct) == 1
    io = io.replace(direct, r'''    if(address & 0x1000) {
      recompiler.invalidate(address & 0xfff);
      imem.write<Word>(address, data);
      if(plaidRspImemDirectWriteObserver) plaidRspImemDirectWriteObserver(address & 0xfff, data, &thread != this);
      return;
    }''')
    io_path = out / "rsp_io.cpp"
    io_path.write_text(io)

    rsp_src = (REF / "ares/n64/rsp/rsp.cpp").read_text()
    fetch = r'''  pipeline.address = ipu.pc;
  pipeline.instruction = instruction;
  debugger.instruction();'''
    assert rsp_src.count(fetch) == 1
    rsp_src = rsp_src.replace(fetch, r'''  pipeline.address = ipu.pc;
  pipeline.instruction = instruction;
  if(plaidRspFetchObserver) plaidRspFetchObserver(pipeline.address, instruction);
  debugger.instruction();''')
    replacements = {"dma.cpp": dma_path, "io.cpp": io_path}
    rsp_src = re.sub(r'#include "([^"]+)"', lambda m:
        f'#include "{replacements.get(m[1], REF / "ares/n64/rsp" / m[1])}"', rsp_src)
    rsp_path = out / "rsp.cpp"
    rsp_path.write_text(rsp_src)

    unity = (out / "n64.cpp").read_text()
    marker = "#include <n64/rsp/rsp.cpp>"
    assert unity.count(marker) == 1
    (out / "n64.cpp").write_text(unity.replace(marker, f'#include "{rsp_path}"'))

    flags = ["-O1", "-std=c++20", "-msse4.1", "-DSLJIT_HAVE_CONFIG_PRE=1", "-DSLJIT_HAVE_CONFIG_POST=1", "-DPLAID_RSP_LIFETIME_OBSERVER=1"]
    includes = [out / "include", *(REF / p for p in ("ares", "nall", ".", "thirdparty", "thirdparty/xxhash", "ares/n64/system"))]
    include_flags = [part for path in includes for part in ("-I", str(path))]
    sources = [DRIVER, out / "core.cpp", out / "n64.cpp", REF / "ares/component/processor/sm5k/sm5k.cpp",
        REF / "ares/ares/memory/fixed-allocator.cpp", REF / "nall/nall/nall.cpp", REF / "thirdparty/sljitAllocator.cpp"]
    exe = out / "oracle-traced"
    with (out / "traced-build.log").open("w") as log:
        try:
            subprocess.run(["g++", *flags, *include_flags, *map(str, sources), str(out / "sljit.o"), str(out / "libco.o"),
                "-pthread", "-ldl", "-o", str(exe)], check=True, stdout=log, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print("\n".join((out / "traced-build.log").read_text().splitlines()[-60:]))
            raise
    return exe


def expected_fragments(p):
    row_bytes = p["length"] + 8
    if row_bytes <= 0 or row_bytes % 8:
        raise AssertionError("invalid normalized DMA row length")
    dram = p["dram"]
    pbus = p["pbus"] & 0xFFF
    out = []
    for _row in range(p["count"] + 1):
        for offset in range(0, row_bytes, 8):
            out.append((dram + offset, (pbus + offset) & 0xFFF))
        dram += row_bytes + p["skip"]
        pbus = (pbus + row_bytes) & 0xFFF
    return out


def verify_trace(events):
    active = None
    installs = {}
    resident = [None] * 4096
    fetches = []
    last = None

    def end_overlapping(imem, size, seq, incoming):
        touched = {(imem + i) & 0xFFF for i in range(size)}
        for cert in installs.values():
            if cert["ended_seq"] is None and cert["transfer"] != incoming and touched.intersection(cert["bytes"]):
                cert["ended_seq"] = seq

    for event in events:
        seq = event["seq"]
        if last is not None and seq != last["seq"] + 1:
            raise AssertionError("non-contiguous observer sequence")
        kind = event["kind"]
        if kind == "promote":
            if active is not None:
                raise AssertionError("promotion while prior current transfer remains active")
            if event["transfer"] in installs or not event["read"] or event["write"] or event["region"] != 1:
                raise AssertionError("unsupported/non-IMEM promotion in bounded verifier")
            active = {"transfer":event["transfer"],"promote_seq":seq,"pbus":event["pbus"] & 0xFFF,"dram":event["dram"],
                "length":event["length"],"count":event["count"],"skip":event["skip"],"fragments":[],"payloads":[]}
        elif kind == "rdram_read":
            if active is None or event["transfer"] != active["transfer"] or event["bytes"] != 8:
                raise AssertionError("backing read not owned by current IMEM transfer")
        elif kind == "imem_write":
            if active is None or event["transfer"] != active["transfer"]:
                raise AssertionError("IMEM fragment not owned by current transfer")
            if last is None or last["kind"] != "rdram_read" or last["seq"] + 1 != seq:
                raise AssertionError("IMEM write lacks immediately paired successful backing read")
            if last["transfer"] != event["transfer"] or last["dram"] != event["dram"] or last["bytes"] != 8 or last["value"] != event["value"]:
                raise AssertionError("backing/write pair mismatch")
            expected = expected_fragments(active); index = len(active["fragments"])
            if index >= len(expected) or expected[index] != (event["dram"], event["imem"] & 0xFFF):
                raise AssertionError("fragment does not match promoted descriptor chronology")
            end_overlapping(event["imem"],8,seq,event["transfer"])
            payload = event["value"].to_bytes(8,"big")
            for i,value in enumerate(payload): resident[(event["imem"]+i)&0xFFF]=(event["transfer"],value,seq)
            active["fragments"].append((event["dram"],event["imem"]&0xFFF)); active["payloads"].append(payload)
        elif kind == "complete":
            if active is None or event["transfer"] != active["transfer"]:
                raise AssertionError("completion does not match current transfer")
            expected = expected_fragments(active)
            if active["fragments"] != expected:
                raise AssertionError("completion before exact promoted descriptor effects are complete")
            byte_set=set()
            for _dram,imem in expected: byte_set.update((imem+i)&0xFFF for i in range(8))
            if any(resident[i] is None or resident[i][0] != active["transfer"] for i in byte_set):
                raise AssertionError("transfer completed but its full installed image is not resident")
            content=b"".join(active["payloads"])
            installs[active["transfer"]]={"transfer":active["transfer"],"promote_seq":active["promote_seq"],"complete_seq":seq,
                "fragments":[{"dram":d,"imem":i} for d,i in expected],"bytes":byte_set,
                "content_sha256":hashlib.sha256(content).hexdigest(),"ended_seq":None}
            active=None
        elif kind == "direct_write":
            end_overlapping(event["imem"],event["bytes"],seq,f"direct:{seq}")
            payload=event["value"].to_bytes(event["bytes"],"big")
            for i,value in enumerate(payload): resident[(event["imem"]+i)&0xFFF]=(f"direct:{seq}",value,seq)
        elif kind == "fetch":
            cells=[resident[(event["pc"]+i)&0xFFF] for i in range(4)]; word=event["word"].to_bytes(4,"big")
            if all(cell is not None for cell in cells):
                if bytes(cell[1] for cell in cells) != word: raise AssertionError("fetch disagrees with replayed resident bytes")
                owners={cell[0] for cell in cells}
            else: owners=set()
            certified=False; owner=None
            if len(owners)==1:
                owner=next(iter(owners))
                if isinstance(owner,int) and owner in installs:
                    cert=installs[owner]; certified=cert["complete_seq"]<seq and (cert["ended_seq"] is None or seq<cert["ended_seq"])
            fetches.append({"seq":seq,"pc":event["pc"],"word":event["word"],"owner":owner,"certified_installation":certified})
        else:
            raise AssertionError(f"unknown event kind {kind}")
        last=event
    if active is not None: raise AssertionError("trace ended with an incomplete current transfer")
    serial=[]
    for transfer in sorted(installs):
        c=installs[transfer]; serial.append({k:(sorted(v) if k=="bytes" else v) for k,v in c.items()})
    return {"installations":serial,"fetches":fetches}


def expect_reject(events):
    try: verify_trace(events)
    except AssertionError: return
    raise AssertionError("forged history was accepted")


def run_forgery_tests(events):
    count=0
    forged=[copy.deepcopy(e) for e in events]; idx=next(i for i,e in enumerate(forged) if e["kind"]=="imem_write"); del forged[idx]
    for i,e in enumerate(forged,1): e["seq"]=i
    expect_reject(forged); count+=1
    forged=copy.deepcopy(events); next(e for e in forged if e["kind"]=="imem_write")["transfer"]+=1000
    expect_reject(forged); count+=1
    forged=copy.deepcopy(events); c4=next(i for i,e in enumerate(forged) if e["kind"]=="complete" and e["transfer"]==4); p5=next(i for i,e in enumerate(forged) if e["kind"]=="promote" and e["transfer"]==5)
    assert p5==c4+1; forged[c4],forged[p5]=forged[p5],forged[c4]; forged[c4]["seq"],forged[p5]["seq"]=c4+1,p5+1
    expect_reject(forged); count+=1
    forged=[copy.deepcopy(e) for e in events]; idx=next(i for i,e in enumerate(forged) if e["kind"]=="direct_write" and e["imem"]==0x200); del forged[idx]
    for i,e in enumerate(forged,1): e["seq"]=i
    expect_reject(forged); count+=1
    forged=copy.deepcopy(events); p7=next(e for e in forged if e["kind"]=="promote" and e["transfer"]==7); p7["dram"],p7["pbus"]=0x7000,0x380
    expect_reject(forged); count+=1
    return count


def self_test():
    value=0x2401000100000000
    events=[
        {"seq":1,"kind":"promote","transfer":1,"region":1,"pbus":0,"dram":0x1000,"length":0,"count":0,"skip":0,"read":True,"write":False},
        {"seq":2,"kind":"rdram_read","transfer":1,"dram":0x1000,"bytes":8,"value":value},
        {"seq":3,"kind":"imem_write","transfer":1,"dram":0x1000,"imem":0,"bytes":8,"value":value},
        {"seq":4,"kind":"complete","transfer":1}, {"seq":5,"kind":"fetch","pc":0,"word":0x24010001}]
    result=verify_trace(events); assert len(result["installations"])==1 and result["fetches"][0]["certified_installation"]
    forged=copy.deepcopy(events); forged.pop(2)
    for i,e in enumerate(forged,1): e["seq"]=i
    expect_reject(forged)
    print("PASS self-test: exact completion accepted; missing fragment rejected")


def worker():
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=REF,text=True).strip()==REV
    subprocess.run(["git","-c","core.autocrlf=true","diff","--quiet","HEAD"],cwd=REF,check=True)
    builder=load_builder(); baseline=builder.build(DRIVER,OUTPUT/"baseline-build"); traced=build_traced(builder)
    plain_raw=subprocess.check_output([str(baseline),"plain"],text=True,timeout=30)
    traced_raw=subprocess.check_output([str(traced),"traced"],text=True,timeout=30)
    repeat_raw=subprocess.check_output([str(traced),"traced"],text=True,timeout=30)
    plain,observed,repeat=map(json.loads,(plain_raw,traced_raw,repeat_raw))
    assert traced_raw==repeat_raw
    assert plain["events"]==[] and observed["events"] and plain["state"]==observed["state"]==repeat["state"]
    assert observed["state"]["handoff"]==[1,1,1,0]
    replay=verify_trace(observed["events"]); certs={c["transfer"]:c for c in replay["installations"]}
    assert sorted(certs)==[1,2,3,4,5,6,7]
    assert [(f["dram"],f["imem"]) for f in certs[1]["fragments"]]==[(0x1000,0x000),(0x1008,0x008)]
    assert [(f["dram"],f["imem"]) for f in certs[2]["fragments"]]==[(0x2000,0x100),(0x2010,0x108)]
    assert [(f["dram"],f["imem"]) for f in certs[3]["fragments"]]==[(0x3000,0xff8),(0x3008,0x000)]
    assert certs[4]["content_sha256"]==certs[5]["content_sha256"] and certs[4]["transfer"]!=certs[5]["transfer"]
    assert certs[4]["ended_seq"] is not None and certs[5]["ended_seq"] is not None
    assert certs[7]["fragments"]==[{"dram":0x7100,"imem":0x3c0}]
    partial=next(f for f in replay["fetches"] if f["pc"]==0x100); assert partial["owner"]==2 and not partial["certified_installation"]
    post=[f for f in replay["fetches"] if f["pc"]==0x108][-1]; assert post["owner"]==2 and post["certified_installation"]
    hf=[f for f in replay["fetches"] if f["pc"]==0x200]
    assert hf[0]["owner"]==4 and hf[0]["certified_installation"]
    assert hf[1]["owner"]==5 and hf[1]["certified_installation"]
    assert hf[2]["owner"]==5 and hf[2]["certified_installation"]
    assert not hf[3]["certified_installation"] and str(hf[3]["owner"]).startswith("direct:")
    forged=run_forgery_tests(observed["events"])
    result={"revision":REV,"driver_sha256":hashlib.sha256(DRIVER.read_bytes()).hexdigest(),"state":observed["state"],
        "events":observed["events"],"replay":replay,"neutrality":plain["state"]==observed["state"],
        "repeat_deterministic":traced_raw==repeat_raw,"forgeries_rejected":forged}
    OUTPUT.mkdir(parents=True,exist_ok=True); path=OUTPUT/"results.json"; path.write_text(json.dumps(result,indent=2)+"\n")
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"PASS: 7 promoted transfers produced exact completed installation certificates; 5 forgeries rejected; results_sha256={digest}")


def main():
    if "--self-test" in sys.argv: self_test(); return
    if os.name=="nt":
        script=subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__=="__main__": main()
