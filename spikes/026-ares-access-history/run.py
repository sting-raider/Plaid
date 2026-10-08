"""Check explicit access boundaries in the shared controlled callback ledger."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-access-history-spike"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(data):
    assert data["access_policy"] == "controlled_access_callbacks_v0"
    history = data["history"]
    payloads = {"fixture_write":data["fixture_writes"], "rdram_burst":data["rdram_bursts"],
                "fill":data["fills"], "fetch":data["events"], "cache_operation":data["cache_operations"],
                "scalar":data["scalars"], "fetch_boundary":data["boundaries"]}
    assert len(history) == 95 and len(data["boundaries"]) == 34 and len(data["scalars"]) == 18
    assert [e["seq"] for e in history] == list(range(1,len(history)+1))
    for kind, records in payloads.items():
        assert [e["index"] for e in history if e["kind"] == kind] == list(range(1,len(records)+1))
    assert all(set(e) == {"seq","kind","index"} and e["kind"] in payloads for e in history)
    active = None
    completed = []
    scalar_reads = []
    for e in history:
        record = payloads[e["kind"]][e["index"]-1]
        if e["kind"] == "fetch_boundary":
            if record["begin"]:
                assert active is None
                active = {"begin":record,"records":[]}
            else:
                assert active is not None
                begin = active["begin"]
                for field in ("pc","vaddr","translated","bus","cached"):
                    assert record[field] == begin[field]
                eligible = [r for kind,r in active["records"] if kind == "scalar"
                            and not r["write"] and r["bytes"] == 4 and r["device"] == 3]
                if not begin["cached"]:
                    assert len(eligible) == 1
                    read = eligible[0]
                    assert read["address"] == begin["bus"] and read["value"] == record["value"]
                    scalar_reads.append(read)
                else:
                    assert not eligible
                completed.append(record)
                active = None
        elif active is not None:
            assert e["kind"] in {"scalar","rdram_burst","fill"}
            active["records"].append((e["kind"],record))
        elif e["kind"] == "fetch":
            assert len(completed) == e["index"]
            last = completed[-1]
            assert (record["pc"],record["physical"],record["cached"],record["word"]) == (
                last["pc"],last["bus"],last["cached"],last["value"])
    assert active is None and len(completed) == 17 and len(scalar_reads) == 9
    assert [r for r in data["scalars"] if not r["write"]] == scalar_reads
    writes = [r for r in data["scalars"] if r["write"]]
    assert [(r["address"],r["value"],r["bytes"]) for r in writes] == [
        (r["address"],r["word"],r["bytes"]) for r in data["fixture_writes"]]
    assert all(r["device"] == 11 for r in writes)  # pinned ARES_DEBUGGER enum
    # Every fixture write has its own completed scalar transaction immediately before it.
    for i,e in enumerate(history):
        if e["kind"] == "fixture_write":
            previous = history[i-1]
            assert previous["kind"] == "scalar"
            assert payloads["scalar"][previous["index"]-1] == writes[e["index"]-1]
    prior = copy.deepcopy(data)
    for field in ("access_policy","scalars","boundaries"):
        prior.pop(field)
    prior["history"] = [e for e in prior["history"] if e["kind"] not in {"scalar","fetch_boundary"}]
    for i,e in enumerate(prior["history"],1):
        e["seq"] = i
    load("prior_history",ROOT/"spikes/018-ares-ordered-history/run.py").verify(prior)


def adversarial(data):
    variants = []
    for field in ("value","bus","vaddr"):
        changed = copy.deepcopy(data)
        changed["boundaries"][1][field] ^= 4
        variants.append(changed)
    changed = copy.deepcopy(data)
    first = next(e for e in changed["history"] if e["kind"] == "fetch_boundary")
    first["index"] = 2
    variants.append(changed)
    changed = copy.deepcopy(data)
    read = next(e for e in changed["scalars"] if not e["write"])
    read["address"] ^= 4
    variants.append(changed)
    changed = copy.deepcopy(data)
    changed["history"].pop(0)
    for i,e in enumerate(changed["history"],1): e["seq"] = i
    variants.append(changed)
    for changed in variants:
        try: verify(changed)
        except AssertionError: continue
        raise AssertionError("forged access history accepted")


def worker():
    builder = load("builder",ROOT/"spikes/003-ares-oracle/run.py")
    inputs = tuple(ROOT/f"spikes/{p}" for p in (
        "013-ares-cache-tag/driver.cpp","012-ares-cache-fill/observer.hpp",
        "014-ares-cache-operations/observer.hpp","014-ares-cache-operations/driver.cpp",
        "015-ares-cache-outcomes/driver.cpp","016-ares-rdram-bursts/observer.hpp",
        "016-ares-rdram-bursts/driver.cpp","018-ares-ordered-history/history.hpp"))
    baseline = builder.build(ROOT/"spikes/015-ares-cache-outcomes/baseline.cpp",OUTPUT/"baseline",
        raw_fetch_access=True,physical_fetch_access=True,extra_sources=inputs)
    original = json.loads(subprocess.check_output([str(baseline),"plain"],text=True,timeout=30))
    exe = builder.build(HERE/"driver.cpp",OUTPUT/"sensor",raw_fetch_access=True,
        physical_fetch_access=True,cache_fill_access=True,cache_operation_access=True,
        rdram_burst_access=True,rdram_scalar_access=True,fetch_boundary_access=True,
        extra_sources=(*inputs,HERE/"history.hpp"))
    runs = [subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ("plain","traced","traced")]
    plain,traced,repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2]
    assert original["state"] == plain["state"] == traced["state"] == repeat["state"]
    assert not any(plain[k] for k in ("history","fixture_writes","rdram_bursts","fills","events",
                                    "cache_operations","scalars","boundaries"))
    verify(traced)
    adversarial(traced)
    (OUTPUT/"results.json").write_text(json.dumps(traced,indent=2)+"\n")
    digest = hashlib.sha256(json.dumps(traced,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    print("RESULT_SHA256="+digest)
    print("PASS: 95 shared records with explicit fetch boundaries, 9 scalar fetch reads and 9 attributed fixture writes; prior 43-record projection and reported machine state unchanged; six forgeries rejected")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
