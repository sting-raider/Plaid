"""Build pinned ares and prove bounded D-cache store -> RDRAM writeback lineage."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
OUTPUT = ROOT / "target/ares-dcache-writeback-lineage-spike"
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_instrumented():
    output = OUTPUT / "instrumented"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    driver = HERE / "driver.cpp"
    observer = HERE / "observer.hpp"
    compiler = subprocess.check_output(["g++", "--version"], text=True).splitlines()[0]
    source_paths = {
        "dcache": REF / "ares/n64/cpu/dcache.cpp",
        "cpu_hpp": REF / "ares/n64/cpu/cpu.hpp",
        "rdram_hpp": REF / "ares/n64/rdram/rdram.hpp",
    }
    inputs = {
        "revision": REV,
        "compiler": compiler,
        "driver": sha(driver),
        "observer": sha(observer),
        "recipe": sha(Path(__file__)),
        **{f"source_{name}": sha(path) for name, path in source_paths.items()},
    }
    exe = output / "oracle"
    manifest = output / "build.json"
    if manifest.exists() and exe.exists() and json.loads(manifest.read_text()) == inputs:
        return exe, inputs

    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REF / "LICENSE", output / "LICENSE")

    # Shadow only the CPU source directory in the generated include tree. The
    # original cpu.cpp uses quoted sibling includes, so copying the directory
    # preserves all exact pinned relative include behavior while allowing two
    # tiny generated instrumentation edits in cpu.hpp and dcache.cpp.
    generated_cpu = output / "include/n64/cpu"
    shutil.copytree(REF / "ares/n64/cpu", generated_cpu)

    cpu_hpp_path = generated_cpu / "cpu.hpp"
    cpu_hpp = cpu_hpp_path.read_text()
    marker = "  //dcache.cpp\n  struct DataCache {"
    assert cpu_hpp.count(marker) == 1
    prefix, dcache_block = cpu_hpp.split(marker, 1)
    setvalid = """      auto setValid(bool on) -> void {\n        if(on) tagKey |= 1u;\n        else tagKey &= ~1u;\n      }"""
    assert dcache_block.count(setvalid) == 1
    setvalid_instrumented = """      auto setValid(bool on) -> void {\n        bool plaidWasValid = valid();\n        if(on) tagKey |= 1u;\n        else tagKey &= ~1u;\n        if(!on && plaidWasValid && plaidDcacheObserver)\n          plaidDcacheObserver(5, this, (tagKey & ~0x0000'0fffu) | index, 0, dirty, dirty, words);\n      }"""
    callbacks = """// Project-owned research callback. No N64 object layout changes.\nusing PlaidDcacheObserver = void (*)(u32, const void*, u32, u32, u16, u16, const u32*);\ninline PlaidDcacheObserver plaidDcacheObserver = nullptr;\n\n"""
    cpu_hpp_path.write_text(callbacks + prefix + marker + dcache_block.replace(setvalid, setvalid_instrumented))

    dcache_path = generated_cpu / "dcache.cpp"
    dcache = dcache_path.read_text()
    fill = "  setValid(cpu.busReadBurst<DCache>(tag | index, words));"
    assert dcache.count(fill) == 1
    dcache = dcache.replace(fill, """  bool plaidFilled = cpu.busReadBurst<DCache>(tag | index, words);\n  setValid(plaidFilled);\n  if(plaidFilled && plaidDcacheObserver)\n    plaidDcacheObserver(1, this, tag | index, DCache, 0, dirty, words);""")
    writeback = "  cpu.busWriteBurst<DCache>(tag | index, words);"
    assert dcache.count(writeback) == 1
    dcache = dcache.replace(writeback, """  if(plaidDcacheObserver) plaidDcacheObserver(3, this, tag | index, DCache, dirty, dirty, words);\n  cpu.busWriteBurst<DCache>(tag | index, words);\n  if(plaidDcacheObserver) plaidDcacheObserver(4, this, tag | index, DCache, dirty, dirty, words);""")
    write_sig = "auto CPU::DataCache::Line::write(u32 paddr, u64 data) -> void {"
    assert dcache.count(write_sig) == 1
    dcache = dcache.replace(write_sig, write_sig + "\n  u16 plaidDirtyBefore = dirty;")
    dirty_pc = "  dirtyPc = cpu.ipu.pc;"
    assert dcache.count(dirty_pc) == 1
    dcache = dcache.replace(dirty_pc, dirty_pc +
        "\n  if(plaidDcacheObserver) plaidDcacheObserver(2, this, paddr, Size, plaidDirtyBefore, dirty, words);")
    dcache_path.write_text(dcache)

    # Completed successful identity-RDRAM burst observation. Non-identity paths
    # return before the read hook, and the write hook is explicitly identity-only.
    ram = source_paths["rdram_hpp"].read_text()
    write_done = "      self.hidden.updateBurst<Size>(address, value);"
    assert ram.count(write_done) == 1
    ram = ram.replace(write_done, write_done +
        "\n      if(self.mapIdentity && plaidRdramBurstObserver) plaidRdramBurstObserver(true, address, Size, (u32)device, value);")
    begin = "    template<u32 Size>\n    auto readBurst(u32 address, u32 *value, RBusDevice device) -> void {"
    end = "  } ram{*this};"
    assert ram.count(begin) == ram.count(end) == 1
    start, stop = ram.index(begin), ram.index(end)
    block = ram[start:stop]
    assert block.endswith("    }\n\n")
    block = block[:-7] + "      if(plaidRdramBurstObserver) plaidRdramBurstObserver(false, address, Size, (u32)device, value);\n    }\n\n"
    ram = ram[:start] + block + ram[stop:]
    ram = """// Project-owned callback after completed eligible RDRAM burst accesses.\nusing PlaidRdramBurstObserver = void (*)(bool, u32, u32, u32, const u32*);\ninline PlaidRdramBurstObserver plaidRdramBurstObserver = nullptr;\n""" + ram
    destination = output / "include/n64/rdram/rdram.hpp"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(ram)

    includes = [output / "include"] + [REF / p for p in
        ("ares", "nall", ".", "thirdparty", "thirdparty/xxhash", "ares/n64/system")]
    include_flags = [part for path in includes for part in ("-I", str(path))]
    flags = ["-O1", "-std=c++20", "-msse4.1", "-DSLJIT_HAVE_CONFIG_PRE=1", "-DSLJIT_HAVE_CONFIG_POST=1"]

    core = (REF / "ares/ares/ares.cpp.in").read_text().replace(
        "#include <ares/resource/resource.cpp>", "// UI-only resources omitted in headless build.")
    for key, value in {
        "ARES_NAME": "Plaid pinned ares D-cache lineage oracle",
        "ARES_VERSION": REV,
        "ARES_LEGAL_COPYRIGHT_SHORT": "See upstream LICENSE",
        "ARES_WEBSITE": "ares-emu.net",
    }.items():
        core = core.replace(f"@{key}@", value)
    (output / "core.cpp").write_text(core)

    system = (REF / "ares/n64/system/system.cpp").read_text()
    assert system.count("    vulkan.load(node);") == 1
    system = system.replace("    vulkan.load(node);", "#if defined(VULKAN)\n    vulkan.load(node);\n#endif")
    (output / "system.cpp").write_text(system)
    unity = (REF / "ares/n64/n64.cpp").read_text()
    assert unity.count("#include <n64/system/system.cpp>") == 1
    unity = unity.replace("#include <n64/system/system.cpp>", f'#include "{output / "system.cpp"}"')
    (output / "n64.cpp").write_text(unity)

    objects = []
    with (output / "build.log").open("w") as log:
        for name, source in [
            ("sljit", REF / "thirdparty/sljit/sljit_src/sljitLir.c"),
            ("libco", REF / "libco/libco.c"),
        ]:
            obj = output / f"{name}.o"
            subprocess.run(["gcc", "-O1", *include_flags,
                "-DSLJIT_HAVE_CONFIG_PRE=1", "-DSLJIT_HAVE_CONFIG_POST=1",
                "-c", str(source), "-o", str(obj)], check=True, stdout=log, stderr=subprocess.STDOUT)
            objects.append(obj)
        sources = [driver, output / "core.cpp", output / "n64.cpp",
            REF / "ares/component/processor/sm5k/sm5k.cpp",
            REF / "ares/ares/memory/fixed-allocator.cpp", REF / "nall/nall/nall.cpp",
            REF / "thirdparty/sljitAllocator.cpp"]
        try:
            subprocess.run(["g++", *flags, *include_flags, *map(str, sources), *map(str, objects),
                "-pthread", "-ldl", "-o", str(exe)], check=True, stdout=log, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print("\n".join((output / "build.log").read_text().splitlines()[-80:]))
            raise
    manifest.write_text(json.dumps(inputs, indent=2) + "\n")
    return exe, inputs


def build_baseline():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.build(HERE / "baseline.cpp", OUTPUT / "baseline", extra_sources=(HERE / "driver.cpp", HERE / "observer.hpp"))


def verify_trace(trace):
    """Fail-closed causal verifier over the measured shared ordinal."""
    events = []
    for event in trace["dcache_events"]:
        events.append((event["ordinal"], "cache", event))
    for event in trace["burst_events"]:
        if event["dcache"]:
            events.append((event["ordinal"], "burst", event))
    events.sort(key=lambda row: row[0])

    generations = {}
    next_generation = 1
    resident = {}
    last_read = None
    pending = None
    certs = []
    rejected_writes = 0

    for _, family, e in events:
        if family == "burst":
            if not e["write"]:
                last_read = e
                continue
            if pending is None or e["address"] != pending["address"] or e["words"] != pending["words"]:
                rejected_writes += 1
                continue
            state = resident.get(pending["slot"])
            if state is None or state["generation"] != pending["generation"]:
                rejected_writes += 1
                pending = None
                continue
            certs.append({
                "phase": e["phase"], "address": e["address"], "slot": pending["slot"],
                "generation": pending["generation"], "write_ordinal": e["ordinal"],
                "origins": list(pending["origins"]),
            })
            continue

        kind = e["kind"]
        slot = e["slot"]
        if kind == "fill":
            if last_read is None or last_read["phase"] != e["phase"] or last_read["address"] != e["paddr"] or last_read["words"] != e["words"]:
                raise AssertionError(("unjoined fill", e, last_read))
            generation = next_generation; next_generation += 1
            generations[slot] = generation
            origins = [f"rdram-read:{last_read['ordinal']}:{i}" for i in range(16)]
            resident[slot] = {"generation": generation, "tag": e["tag"], "words": list(e["words"]),
                              "origins": origins, "dirty": set()}
            last_read = None
        elif kind == "store":
            state = resident.get(slot)
            if state is None or (e["tag"] != state["tag"]):
                raise AssertionError(("store without resident generation", e, state))
            off = e["paddr"] & 0xf
            for i in range(e["bytes"]):
                state["origins"][off+i] = f"store:{e['ordinal']}:{i}"
                state["dirty"].add(off+i)
            state["words"] = list(e["words"])
        elif kind == "writeback_begin":
            state = resident.get(slot)
            if state is None or not state["dirty"] or state["words"] != e["words"]:
                raise AssertionError(("writeback without dirty resident generation", e, state))
            if pending is not None:
                raise AssertionError("nested D-cache writeback context")
            pending = {"slot": slot, "generation": state["generation"], "address": e["paddr"],
                       "words": list(e["words"]), "origins": tuple(state["origins"])}
        elif kind == "writeback_end":
            if pending is None or pending["slot"] != slot:
                raise AssertionError(("writeback end without begin", e, pending))
            pending = None
        elif kind == "invalidate":
            resident.pop(slot, None)
            generations[slot] = next_generation; next_generation += 1
            if pending is not None and pending["slot"] == slot:
                pending = None
        else:
            raise AssertionError(kind)

    assert pending is None
    # Only explicit writeback and dirty eviction export the stored word.
    assert [c["phase"] for c in certs] == [1, 2], certs
    for cert in certs:
        assert all(origin.startswith("store:") for origin in cert["origins"][:4]), cert
        assert all(origin.startswith("rdram-read:") for origin in cert["origins"][4:]), cert
    assert not [c for c in certs if c["phase"] in (3, 4)]
    return {"certificates": certs, "rejected_writes": rejected_writes}


def verify_measured_sequences(traced):
    dcache = traced["dcache_events"]
    bursts = [e for e in traced["burst_events"] if e["dcache"]]
    by_phase = lambda rows, p: [e for e in rows if e["phase"] == p]

    expected_kinds = {
        1: ["fill", "store", "writeback_begin", "writeback_end"],
        2: ["fill", "store", "writeback_begin", "writeback_end", "fill"],
        3: ["fill", "fill"],
        4: ["fill", "store", "invalidate", "fill"],
    }
    for phase, expected in expected_kinds.items():
        actual = [e["kind"] for e in by_phase(dcache, phase)]
        assert actual == expected, (phase, actual)

    A, B, mutated = 0x1000, 0x3000, 0xA1B2C3D4
    phase1 = by_phase(bursts, 1)
    assert [(e["write"], e["address"]) for e in phase1] == [(False,A),(True,A)], phase1
    phase2 = by_phase(bursts, 2)
    assert [(e["write"], e["address"]) for e in phase2] == [(False,A),(True,A),(False,B)], phase2
    phase3 = by_phase(bursts, 3)
    assert [(e["write"], e["address"]) for e in phase3] == [(False,A),(False,B)], phase3
    phase4 = by_phase(bursts, 4)
    assert [(e["write"], e["address"]) for e in phase4] == [(False,A),(False,B)], phase4
    assert not [e for e in phase3 + phase4 if e["write"]]
    assert phase1[1]["words"][0] == phase2[1]["words"][0] == mutated

    # Shared ordinals must place each backing write strictly inside its cache
    # writeback boundary. The dirty eviction must write A before it reads B.
    for phase in (1, 2):
        ce = by_phase(dcache, phase)
        wb0 = next(e for e in ce if e["kind"] == "writeback_begin")
        wb1 = next(e for e in ce if e["kind"] == "writeback_end")
        wr = next(e for e in by_phase(bursts, phase) if e["write"])
        assert wb0["ordinal"] < wr["ordinal"] < wb1["ordinal"]
    p2_write = next(e for e in phase2 if e["write"])
    p2_bread = next(e for e in phase2 if not e["write"] and e["address"] == B)
    assert p2_write["ordinal"] < p2_bread["ordinal"]


def run():
    baseline_exe = build_baseline()
    instrumented_exe, source_inputs = build_instrumented()
    baseline_raw = subprocess.check_output([str(baseline_exe), "plain"], text=True, timeout=30)
    plain_raw = subprocess.check_output([str(instrumented_exe), "plain"], text=True, timeout=30)
    traced_raw = subprocess.check_output([str(instrumented_exe), "traced"], text=True, timeout=30)
    repeat_raw = subprocess.check_output([str(instrumented_exe), "traced"], text=True, timeout=30)
    assert traced_raw == repeat_raw
    baseline, plain, traced = map(json.loads, (baseline_raw, plain_raw, traced_raw))
    assert not baseline["dcache_events"] and not baseline["burst_events"]
    assert not plain["dcache_events"] and not plain["burst_events"]
    assert baseline["facts"] == plain["facts"] == traced["facts"]
    assert baseline["state"] == plain["state"] == traced["state"]

    facts = traced["facts"]
    assert facts == {
        "explicit_before": 0x11111111, "explicit_after": 0xA1B2C3D4,
        "explicit_dirty_before": 15, "explicit_dirty_after": 0,
        "eviction_before": 0x11111111, "eviction_after": 0xA1B2C3D4,
        "clean_a": 0x11111111, "clean_b": 0x11111111,
        "valid_after_invalidate": False, "dirty_after_invalidate": 15,
        "invalidate_backing_before_replacement": 0x11111111,
        "invalidate_backing_after_replacement": 0x11111111,
    }, facts
    assert traced["state"]["exception"] == 0

    verify_measured_sequences(traced)
    lineage = verify_trace(traced)
    results = {"baseline": baseline, "plain": plain, "traced": traced,
               "lineage": lineage, "sources": source_inputs}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "results.json"
    result_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    trace_hash = hashlib.sha256(traced_raw.encode()).hexdigest()
    result_hash = hashlib.sha256(result_path.read_bytes()).hexdigest()
    print("TRACE_SHA256=" + trace_hash)
    print("RESULT_SHA256=" + result_hash)
    for key in ("source_dcache", "source_cpu_hpp", "source_rdram_hpp"):
        print(key.upper() + "=" + source_inputs[key])
    print("PASS: explicit writeback and dirty eviction preserve versioned resident-byte lineage to the exact nested RDRAM burst; clean replacement and dirty invalidate/drop emit no backing certificate")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        run()


if __name__ == "__main__":
    main()
