"""Reproduce actual PI buffer-lane/ROM-read/completed-byte-write joins."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT/"target/ares-pi-buffered-copy-spike"


def rom_bytes():
    data = bytearray(16384)
    data[:4] = bytes.fromhex("80371240")
    for i in range(256):
        data[0x1000+i] = data[0x2000+i] = (i*7+3)&255
        data[0x3000+i] = (i*3+128)&255
    return data


def reduce(events):
    source = rom_bytes()
    assert [e["ordinal"] for e in events] == list(range(1,len(events)+1))
    transfer = block = None
    buffer = {}
    attempt = committed = None
    previous = None
    writes = []
    attempts = failed = 0
    returned = False
    phases = []
    for e in events:
        kind = e["kind"]
        if kind == 1:
            assert transfer is None and attempt is None and e["transfer"] == len(phases)+1 and e["block"] == 0
            transfer = e["transfer"]
            phases.append(e["phase"])
            block = None
            returned = False
        else:
            assert transfer == e["transfer"] and e["phase"] == phases[-1]
        if kind == 2:
            assert block is None and not returned and attempt is None
            block = e["block"]
            assert 0 < e["length"] <= 128 and 0 <= e["lane"] <= 7
            buffer = {}
        elif kind in (3,4,5,6,9,10):
            assert block is not None and e["block"] == block and not returned
            if kind == 10:
                offset = e["pbus"]
                assert e["length"] == 2 and 0 <= offset <= len(source)-2
                assert e["value"] == int.from_bytes(source[offset:offset+2],"big")
            elif kind == 3:
                assert attempt is None and e["lane"] % 2 == 0 and e["lane"] < e["length"]
                assert e["lane"] not in buffer and e["value"] <= 65535
                witnessed = previous is not None and previous["kind"] == 10 and previous["ordinal"]+1 == e["ordinal"] \
                    and previous["transfer"] == transfer and previous["block"] == block \
                    and 0x10000000+previous["pbus"] == e["pbus"] and previous["value"] == e["value"]
                for i in range(2):
                    buffer[e["lane"]+i] = {"value":(e["value"]>>(8*(1-i)))&255,
                        "rom_offset":previous["pbus"]+i if witnessed else None,"read_ordinal":e["ordinal"]}
            elif kind == 4:
                assert attempt is None and e["lane"] in buffer and e["value"] == buffer[e["lane"]]["value"]
                attempt = e
                committed = None
                attempts += 1
            elif kind == 9:
                assert attempt is not None and committed is None
                assert e["length"] == 1 and e["lane"] == 5
                assert (e["dram"],e["value"]) == (attempt["dram"],attempt["value"])
                assert e["dram"] < 8388608
                committed = e
            elif kind == 5:
                assert attempt is not None
                for key in ("dram","pbus","length","lane","value"): assert e[key] == attempt[key]
                if committed:
                    origin = buffer[e["lane"]]
                    writes.append(dict(phase=e["phase"],transfer=transfer,block=block,dram=e["dram"],
                        value=e["value"],rom_offset=origin["rom_offset"],read_ordinal=origin["read_ordinal"],
                        write_ordinal=committed["ordinal"]))
                else: failed += 1
                attempt = committed = None
            else:
                assert kind == 6 and attempt is None
                block = None
        elif kind == 7:
            assert block is None and attempt is None and not returned
            returned = True
        elif kind == 8:
            assert returned and block is None and e["lane"] == 0 and e["value"] == 1
            transfer = None
        else:
            assert kind == 1
        previous = e
    assert transfer is None and attempt is None and phases == list(range(1,9))
    return {"writes":writes,"attempts":attempts,"failed_destination_witnesses":failed}


def verify(data):
    result = reduce(data["events"])
    writes = result["writes"]
    expected = {
        1:(0x1000,0x1000,16),2:(0x1000,0x2000,16),3:(0x1000,0x3000,16),
        4:(0x1102,0x1000,14),5:(0x1200,0x1000,15),6:(0x1800,0x1002,18),
        7:(8388608,None,0),8:(0x1300,None,8),
    }
    for phase,(destination,offset,count) in expected.items():
        actual = [w for w in writes if w["phase"] == phase]
        assert len(actual) == count
        assert [w["dram"] for w in actual] == list(range(destination,destination+count))
        assert [w["rom_offset"] for w in actual] == ([None]*count if offset is None else list(range(offset,offset+count)))
        assert all(w["transfer"] == phase and w["read_ordinal"] < w["write_ordinal"] for w in actual)
    assert len(writes) == 103 and result["attempts"] == 111 and result["failed_destination_witnesses"] == 8
    assert [w["value"] for w in writes if w["phase"] == 1] == [w["value"] for w in writes if w["phase"] == 2]
    latest = {}
    for w in writes: latest[w["dram"]] = w
    assert all(latest[0x1000+i]["transfer"] == 3 and latest[0x1000+i]["rom_offset"] == 0x3000+i for i in range(16))
    source = rom_bytes()
    assert data["state"]["rom_sha256"] == hashlib.sha256(source).hexdigest()
    assert data["state"]["count"] == data["state"]["exception"] == 0
    assert all(c["busy_before_finish"] == 1 and c["busy_after_finish"] == 0 and c["interrupt"] == 1 for c in data["checkpoints"])
    for phase in range(1,9):
        checkpoint = data["checkpoints"][phase-1]
        assert checkpoint["phase"] == phase
        if phase == 7:
            assert checkpoint["bytes"] == []
            continue
        destination,offset,count = expected[phase]
        start = destination & ~7
        predicted = [0xcc]*32
        for write in [w for w in writes if w["phase"] == phase]:
            predicted[write["dram"]-start] = write["value"]
            if offset is not None: assert write["value"] == source[write["rom_offset"]]
        if phase == 6: start = 0x17f8; predicted = [0xcc]*8+[source[0x1002+i] for i in range(18)]+[0xcc]*6
        assert checkpoint["bytes"] == predicted,(phase,checkpoint,predicted)
    return result


def negative(data):
    altered = copy.deepcopy(data["events"])
    rom_read = next(e for e in altered if e["kind"] == 10)
    rom_read["pbus"] += 0x1000  # equal ROM bytes at a different source cannot steal the witness
    writes = reduce(altered)["writes"]
    assert [w["rom_offset"] for w in writes[:2]] == [None,None]
    variants = []
    for key,value in (("dram",0x1001),("value",0)):
        changed = copy.deepcopy(data["events"])
        next(e for e in changed if e["kind"] == 9)[key] = value
        variants.append(changed)
    changed = copy.deepcopy(data["events"]); changed[-1]["kind"] = 7; variants.append(changed)
    changed = copy.deepcopy(data["events"]); changed[1]["ordinal"] = 1; variants.append(changed)
    for changed in variants:
        try: reduce(changed)
        except AssertionError: continue
        raise AssertionError("forged byte/finish/ordinal history accepted")


def worker():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    inputs = (HERE/"driver.cpp",HERE/"observer.hpp")
    baseline = builder.build(HERE/"baseline.cpp",OUTPUT/"baseline",extra_sources=inputs)
    exe = builder.build(HERE/"driver.cpp",OUTPUT/"sensor",raw_fetch_access=True,physical_fetch_access=True,
        rdram_scalar_access=True,pi_dma_access=True,extra_sources=(HERE/"observer.hpp",))
    original = json.loads(subprocess.check_output([str(baseline),"plain"],text=True,timeout=30))
    runs = [subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ("plain","traced","traced")]
    plain,traced,repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2]
    assert original["state"] == plain["state"] == traced["state"] == repeat["state"]
    assert original["checkpoints"] == plain["checkpoints"] == traced["checkpoints"]
    assert not original["events"] and not plain["events"]
    resolved = verify(traced); negative(traced)
    result = {"raw":traced,"resolved":resolved,"baseline_equal":True,"repeat_equal":True}
    path = OUTPUT/"results.json"
    path.write_text(json.dumps(result,indent=2)+"\n")
    print("RESULT_SHA256="+hashlib.sha256(path.read_bytes()).hexdigest())
    print("PASS: buffered ROM halves join through exact PI block/lane to 103 completed writes; 8 failed destinations remain unknown; distinct reload/source and completion boundaries preserve baseline/repeat state")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
