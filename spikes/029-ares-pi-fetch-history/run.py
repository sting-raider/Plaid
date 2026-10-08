"""Reproduce actual PI writers versus resident cache and partial-word fetches."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
from model import check, rom_bytes

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-pi-fetch-history-spike"


def verify(data):
    result = check(data["events"])
    samples = {s["stage"]: s for s in result["samples"]}
    assert len(samples) == len(result["samples"]) == 16
    expected = {2: (0x1111, 1), 3: (0x1111, 1), 5: (0x1111, 1), 6: (0x1111, 2),
                8: (0x1111, 1), 9: (0x3333, 3), 11: (0x1111, 1)}
    for stage, (low, transfer) in expected.items():
        sample = samples[stage]
        assert sample["word"] == 0x34080000 | low
        assert sample["transfers"] == [transfer]*4 and sample["contiguous_rom_word"]
        offset = {1: 0x1000, 2: 0x2000, 3: 0x3000}[transfer]
        assert sample["rom_offsets"] == list(range(offset, offset+4))
    assert samples[2]["fill"] == samples[5]["fill"] == samples[8]["fill"] == samples[11]["fill"]
    assert samples[2]["writers"] == samples[5]["writers"] == samples[8]["writers"] == samples[11]["writers"]
    for stage in (12, 14):
        assert samples[stage]["word"] == 0x34084444 and samples[stage]["rom_offsets"] == [None]*4
        assert samples[stage]["transfers"] == [None]*4 and len(set(samples[stage]["writers"])) == 1
    for stage in (15, 20):
        assert samples[stage]["word"] == 0 and samples[stage]["transfers"] == [3]*4
        assert samples[stage]["rom_offsets"] == list(range(0x3004, 0x3008))
    for stage in (18, 19):
        assert samples[stage]["word"] == 0x34081144 and samples[stage]["transfers"] == [4, 4, 4, None]
        assert samples[stage]["rom_offsets"] == [0x1000, 0x1001, 0x1002, None]
        assert not samples[stage]["contiguous_rom_word"]
    assert samples[18]["writers"] == samples[19]["writers"]
    assert samples[14]["fill"] != samples[18]["fill"] != samples[2]["fill"]
    assert len(result["pi_writes"]) == 99
    assert data["state"]["rom_sha256"] == hashlib.sha256(rom_bytes()).hexdigest()
    assert data["state"]["exception"] == 0 and data["state"]["regs"][8] == 0x1144
    assert data["state"]["count"] == 970
    assert data["state"]["ram_sha256"] == "244f6213e481b6380a6173976a5a68084a92a4fdc9e97d0e42ab424110642221"
    assert data["state"]["hidden_sha256"] == "bb9f8df61474d25e71fa00722318cd387396ca1736605e1248821cc0de3d3af8"
    assert data["state"]["cache_sha256"] == "624c32899483563cffde7b68e4f24041652c6b175b0ca4eccf6dbc27fa026607"
    assert [c["stage"] for c in data["checkpoints"]] == sorted(samples)
    assert all(c["busy"] == 0 and c["interrupt"] == 1 for c in data["checkpoints"])
    return result


def negative(data):
    events = data["events"]
    # Same canonical bytes, changed delegated offset: origin must disappear.
    changed = copy.deepcopy(events)
    next(e for e in changed if e["kind"] == "rom")["offset"] += 0x1000
    samples = {s["stage"]: s for s in check(changed)["samples"]}
    assert samples[2]["rom_offsets"][:2] == [None, None]
    assert samples[5]["rom_offsets"][:2] == [None, None]
    assert samples[6]["rom_offsets"] == list(range(0x2000, 0x2004))
    # An extra same-valued read in the interval makes attribution ambiguous.
    changed = copy.deepcopy(events)
    index = next(i for i, e in enumerate(changed) if e["kind"] == "scalar" and e["stage"] == 3)
    changed.insert(index, copy.deepcopy(changed[index]))
    for ordinal, event in enumerate(changed, 1):
        event["ordinal"] = ordinal
        if event.get("context"):
            # Contexts are begin ordinals; the inserted read is after its begin.
            event["context"] += int(event["context"] > events[index]["ordinal"])
    samples = {s["stage"]: s for s in check(changed)["samples"]}
    assert samples[3]["rom_offsets"] == [None]*4
    variants = []
    for kind, field, replacement in (("scalar", "value", 0), ("fill", "slot", 1),
                                      ("cache", "after_tag", 0x4001), ("fetch", "word", 0)):
        changed = copy.deepcopy(events)
        next(e for e in changed if e["kind"] == kind)[field] = replacement
        variants.append(changed)
    changed = copy.deepcopy(events)
    next(e for e in changed if e["kind"] == "fetch" and e["stage"] == 8)["words"][0] = 0x34083333
    variants.append(changed)
    variants.append(copy.deepcopy(events[:-1]))
    changed = copy.deepcopy(events); changed[1]["ordinal"] = 1; variants.append(changed)
    for changed in variants:
        try:
            check(changed)
        except AssertionError:
            continue
        raise AssertionError("forged chronology accepted")


def worker():
    spec = importlib.util.spec_from_file_location("builder", ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    inputs = (HERE/"driver.cpp", HERE/"observer.hpp")
    baseline = builder.build(HERE/"baseline.cpp", OUTPUT/"baseline", extra_sources=inputs)
    exe = builder.build(HERE/"driver.cpp", OUTPUT/"sensor", raw_fetch_access=True, physical_fetch_access=True,
                        rdram_scalar_access=True, rdram_burst_access=True, cache_fill_access=True,
                        cache_operation_access=True, fetch_boundary_access=True, pi_dma_access=True,
                        extra_sources=(HERE/"observer.hpp",))
    original = json.loads(subprocess.check_output([str(baseline), "plain"], text=True, timeout=30))
    runs = [subprocess.check_output([str(exe), mode], text=True, timeout=30) for mode in ("plain", "traced", "traced")]
    plain, traced, repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2]
    assert original["state"] == plain["state"] == traced["state"] == repeat["state"]
    assert original["checkpoints"] == plain["checkpoints"] == traced["checkpoints"] == repeat["checkpoints"]
    assert not original["events"] and not plain["events"]
    resolved = verify(traced); negative(traced)
    path = OUTPUT/"results.json"
    path.write_text(json.dumps(dict(raw=traced, resolved=resolved, baseline_equal=True, repeat_equal=True), indent=2)+"\n")
    print("RESULT_SHA256="+hashlib.sha256(path.read_bytes()).hexdigest())
    print("PASS: 99 PI byte writers join actual fetch/fill contexts; cached reloads retain earlier origins, CPU patches and partial words preserve mixed/unknown byte history")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
