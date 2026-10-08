"""Build pinned ares and test scalar-vs-cached CPU copy provenance."""
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
OUTPUT = ROOT / "target/ares-cpu-copy-transactions-spike"
HERE = Path(__file__).resolve().parent


def build_instrumented():
    output = OUTPUT / "instrumented"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REF / "LICENSE", output / "LICENSE")
    driver = HERE / "driver.cpp"
    observer = HERE / "observer.hpp"
    compiler = subprocess.check_output(["g++", "--version"], text=True).splitlines()[0]
    inputs = {
        "revision": REV,
        "compiler": compiler,
        "driver": hashlib.sha256(driver.read_bytes()).hexdigest(),
        "observer": hashlib.sha256(observer.read_bytes()).hexdigest(),
        "recipe": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    exe = output / "oracle"
    manifest = output / "build.json"
    if manifest.exists() and exe.exists() and json.loads(manifest.read_text()) == inputs:
        return exe

    ram = (REF / "ares/n64/rdram/rdram.hpp").read_text()
    scalar_read = "      return Memory::Writable::read<Size>(address);"
    assert ram.count(scalar_read) == 1
    ram = ram.replace(scalar_read, """      u64 plaidValue = Memory::Writable::read<Size>(address);
      if(plaidRdramScalarObserver) plaidRdramScalarObserver(false, address, Size, (u32)device, plaidValue);
      return plaidValue;""")
    scalar_write = "      self.hidden.update<Size>(address, value);"
    assert ram.count(scalar_write) == 1
    ram = ram.replace(scalar_write, scalar_write +
        "\n      if(self.mapIdentity && plaidRdramScalarObserver) plaidRdramScalarObserver(true, address, Size, (u32)device, value);")

    burst_write = "      self.hidden.updateBurst<Size>(address, value);"
    assert ram.count(burst_write) == 1
    ram = ram.replace(burst_write, burst_write +
        "\n      if(self.mapIdentity && plaidRdramBurstObserver) plaidRdramBurstObserver(true, address, Size, (u32)device, value);")
    begin = "    template<u32 Size>\n    auto readBurst(u32 address, u32 *value, RBusDevice device) -> void {"
    end = "  } ram{*this};"
    assert ram.count(begin) == ram.count(end) == 1
    start, stop = ram.index(begin), ram.index(end)
    block = ram[start:stop]
    assert block.endswith("    }\n\n")
    block = block[:-7] + "      if(plaidRdramBurstObserver) plaidRdramBurstObserver(false, address, Size, (u32)device, value);\n    }\n\n"
    ram = ram[:start] + block + ram[stop:]
    ram = """// Project-owned callbacks after completed identity-mapped RDRAM accesses.
using PlaidRdramScalarObserver = void (*)(bool, u32, u32, u32, u64);
inline PlaidRdramScalarObserver plaidRdramScalarObserver = nullptr;
using PlaidRdramBurstObserver = void (*)(bool, u32, u32, u32, const u32*);
inline PlaidRdramBurstObserver plaidRdramBurstObserver = nullptr;
""" + ram
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
        "ARES_NAME": "Plaid pinned ares CPU-copy oracle",
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
            print("\n".join((output / "build.log").read_text().splitlines()[-50:]))
            raise
    manifest.write_text(json.dumps(inputs, indent=2) + "\n")
    return exe


def build_baseline():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.build(HERE / "baseline.cpp", OUTPUT / "baseline", extra_sources=(HERE / "driver.cpp", HERE / "observer.hpp"))


def run():
    baseline_exe = build_baseline()
    instrumented_exe = build_instrumented()
    baseline_raw = subprocess.check_output([str(baseline_exe), "plain"], text=True, timeout=30)
    plain_raw = subprocess.check_output([str(instrumented_exe), "plain"], text=True, timeout=30)
    traced_raw = subprocess.check_output([str(instrumented_exe), "traced"], text=True, timeout=30)
    repeat_raw = subprocess.check_output([str(instrumented_exe), "traced"], text=True, timeout=30)
    assert traced_raw == repeat_raw
    baseline, plain, traced = map(json.loads, (baseline_raw, plain_raw, traced_raw))
    assert not baseline["scalar_events"] and not baseline["burst_events"]
    assert not plain["scalar_events"] and not plain["burst_events"]
    assert baseline["facts"] == plain["facts"] == traced["facts"]
    assert baseline["state"] == plain["state"] == traced["state"]

    original = 0x11223344
    old_destination = 0xaabbccdd
    alias_mutation = 0x55667788
    facts = traced["facts"]
    assert facts == {
        "uncached_destination": original,
        "cached_backing_before_writeback": old_destination,
        "mutated_source_backing": alias_mutation,
        "cached_source_resident": original,
        "cached_destination_resident": original,
        "cached_backing_after_writeback": original,
        "dirty_before_writeback": 15,
        "dirty_after_writeback": 0,
    }, facts

    scalar1 = [e for e in traced["scalar_events"] if e["phase"] == 1]
    assert [(e["write"], e["address"], e["bytes"], e["value"]) for e in scalar1] == [
        (False, 0x1000, 4, original),
        (True, 0x2000, 4, original),
    ], scalar1
    assert all(e["uncached_cpu"] for e in scalar1)

    scalar2 = [e for e in traced["scalar_events"] if e["phase"] == 2]
    assert [(e["write"], e["address"], e["bytes"], e["value"]) for e in scalar2] == [
        (True, 0x1000, 4, alias_mutation),
    ], scalar2
    assert scalar2[0]["uncached_cpu"]

    dcache2 = [e for e in traced["burst_events"] if e["phase"] == 2 and e["dcache"]]
    assert [(e["write"], e["address"], e["bytes"], e["words"][0]) for e in dcache2] == [
        (False, 0x1000, 16, original),
        (False, 0x2000, 16, old_destination),
        (True, 0x2000, 16, original),
    ], dcache2
    assert dcache2[0]["ordinal"] < scalar2[0]["ordinal"] < dcache2[1]["ordinal"] < dcache2[2]["ordinal"]
    assert not [e for e in traced["burst_events"] if e["phase"] == 1 and e["dcache"]]
    assert traced["state"]["exception"] == 0
    assert traced["state"]["dcache_misses"] == 2
    assert traced["state"]["dcache_writebacks"] == 1

    results = {"baseline": baseline, "plain": plain, "traced": traced}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    evidence = {
        "uncached_scalar_chain": scalar1,
        "cached_scalar_events": scalar2,
        "cached_dcache_bursts": dcache2,
        "facts": facts,
        "state": traced["state"],
    }
    print("EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    print("PASS: uncached LW/SW has exact scalar backing chain; cached copy remains D-cache-resident until writeback and survives an uncached stale-source alias mutation")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        run()


if __name__ == "__main__":
    main()
