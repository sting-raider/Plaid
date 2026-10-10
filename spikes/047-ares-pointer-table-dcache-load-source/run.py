"""Build exact pinned ares and execute cacheable pointer-table load-source cases."""
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
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-pointer-table-dcache-load-source"
SCENARIOS = ("stale", "same", "refill", "same_refill", "resident")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_baseline():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.build(HERE / "baseline.cpp", OUTPUT / "baseline")


def patch_rdram(output):
    observer = HERE / "observer.hpp"
    ram = (REF / "ares/n64/rdram/rdram.hpp").read_text()
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
    ram = f'#include "{observer.as_posix()}"\n' + ram
    destination = output / "include/n64/rdram/rdram.hpp"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(ram)


def patch_dcache(output):
    observer = HERE / "observer.hpp"
    source = (REF / "ares/n64/cpu/dcache.cpp").read_text()
    old_read = """template<u32 Size>
auto CPU::DataCache::read(u64 vaddr, u32 paddr) -> u64 {
  auto& line = this->line(vaddr);
  if(!line.hit(paddr)) {
    if(line.valid() && line.dirty) {
      line.writeBack();
      self.profile.dcacheWritebacks++;
    }
    line.fill(paddr);
    self.profile.dcacheMisses++;
  } else {
    cpu.step(1 * 2);
    self.profile.dcacheHits++;
  }
  return line.read<Size>(paddr);
}
"""
    new_read = """template<u32 Size>
auto CPU::DataCache::read(u64 vaddr, u32 paddr) -> u64 {
  auto& line = this->line(vaddr);
  bool plaidHitBefore = line.hit(paddr);
  if(!plaidHitBefore) {
    if(line.valid() && line.dirty) {
      line.writeBack();
      self.profile.dcacheWritebacks++;
    }
    line.fill(paddr);
    self.profile.dcacheMisses++;
  } else {
    cpu.step(1 * 2);
    self.profile.dcacheHits++;
  }
  u64 plaidValue = line.read<Size>(paddr);
  if(plaidDcacheReadObserver) plaidDcacheReadObserver(cpu.ipu.pc, vaddr, paddr, Size,
    plaidValue, line.tagKey, line.index, line.dirty, line.fillPc, line.dirtyPc, plaidHitBefore);
  return plaidValue;
}
"""
    old_write = """template<u32 Size>
auto CPU::DataCache::write(u64 vaddr, u32 paddr, u64 data) -> void {
  auto& line = this->line(vaddr);
  if(!line.hit(paddr)) {
    if(line.valid() && line.dirty) {
      line.writeBack();
      self.profile.dcacheWritebacks++;
    }
    line.fill(paddr);
    self.profile.dcacheMisses++;
  } else {
    cpu.step(1 * 2);
    self.profile.dcacheHits++;
  }
  line.write<Size>(paddr, data);
}
"""
    new_write = """template<u32 Size>
auto CPU::DataCache::write(u64 vaddr, u32 paddr, u64 data) -> void {
  auto& line = this->line(vaddr);
  bool plaidHitBefore = line.hit(paddr);
  if(!plaidHitBefore) {
    if(line.valid() && line.dirty) {
      line.writeBack();
      self.profile.dcacheWritebacks++;
    }
    line.fill(paddr);
    self.profile.dcacheMisses++;
  } else {
    cpu.step(1 * 2);
    self.profile.dcacheHits++;
  }
  line.write<Size>(paddr, data);
  if(plaidDcacheWriteObserver) plaidDcacheWriteObserver(cpu.ipu.pc, vaddr, paddr, Size,
    data, line.tagKey, line.index, line.dirty, line.fillPc, line.dirtyPc, plaidHitBefore);
}
"""
    assert source.count(old_read) == 1
    assert source.count(old_write) == 1
    source = source.replace(old_read, new_read).replace(old_write, new_write)
    source = f'#include "{observer.as_posix()}"\n' + source
    destination = output / "include/n64/cpu/dcache.cpp"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source)


def build_instrumented():
    output = OUTPUT / "instrumented"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REF / "LICENSE", output / "LICENSE")
    driver = HERE / "driver.cpp"
    observer = HERE / "observer.hpp"
    upstream_dcache = REF / "ares/n64/cpu/dcache.cpp"
    upstream_rdram = REF / "ares/n64/rdram/rdram.hpp"
    compiler = subprocess.check_output(["g++", "--version"], text=True).splitlines()[0]
    inputs = {
        "revision": REV,
        "compiler": compiler,
        "driver": sha(driver),
        "observer": sha(observer),
        "recipe": sha(__file__),
        "upstream_dcache": sha(upstream_dcache),
        "upstream_rdram": sha(upstream_rdram),
    }
    exe = output / "oracle"
    manifest = output / "build.json"
    if manifest.exists() and exe.exists() and json.loads(manifest.read_text()) == inputs:
        return exe, inputs

    patch_rdram(output)
    patch_dcache(output)
    includes = [output / "include"] + [REF / p for p in
        ("ares", "nall", ".", "thirdparty", "thirdparty/xxhash", "ares/n64/system")]
    include_flags = [part for path in includes for part in ("-I", str(path))]
    flags = ["-O1", "-std=c++20", "-msse4.1", "-DSLJIT_HAVE_CONFIG_PRE=1", "-DSLJIT_HAVE_CONFIG_POST=1"]

    core = (REF / "ares/ares/ares.cpp.in").read_text().replace(
        "#include <ares/resource/resource.cpp>", "// UI-only resources omitted in headless build.")
    for key, value in {
        "ARES_NAME": "Plaid pinned ares pointer-table D-cache oracle",
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
                "-c", str(source), "-o", str(obj)], check=True,
                stdout=log, stderr=subprocess.STDOUT)
            objects.append(obj)
        sources = [driver, output / "core.cpp", output / "n64.cpp",
            REF / "ares/component/processor/sm5k/sm5k.cpp",
            REF / "ares/ares/memory/fixed-allocator.cpp", REF / "nall/nall/nall.cpp",
            REF / "thirdparty/sljitAllocator.cpp"]
        try:
            subprocess.run(["g++", *flags, *include_flags, *map(str, sources), *map(str, objects),
                "-pthread", "-ldl", "-o", str(exe)], check=True,
                stdout=log, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print("\n".join((output / "build.log").read_text().splitlines()[-80:]))
            raise
    manifest.write_text(json.dumps(inputs, indent=2, sort_keys=True) + "\n")
    return exe, inputs


def run_case(exe, mode, scenario):
    raw = subprocess.check_output([str(exe), mode, scenario], text=True, timeout=30)
    return raw, json.loads(raw)


def run():
    baseline = build_baseline()
    instrumented, source_inputs = build_instrumented()
    evidence = {"schema": "plaid.pointer_table_dcache_load_source.v0", "ares_rev": REV,
                "source_inputs": source_inputs, "cases": {}}

    for scenario in SCENARIOS:
        baseline_raw, baseline_doc = run_case(baseline, "plain", scenario)
        plain_raw, plain_doc = run_case(instrumented, "plain", scenario)
        traced_raw, traced_doc = run_case(instrumented, "traced", scenario)
        repeat_raw, repeat_doc = run_case(instrumented, "traced", scenario)
        assert traced_raw == repeat_raw
        assert traced_doc == repeat_doc
        assert all(not baseline_doc["events"][k] for k in baseline_doc["events"])
        assert all(not plain_doc["events"][k] for k in plain_doc["events"])
        assert baseline_doc["facts"] == plain_doc["facts"] == traced_doc["facts"]
        assert baseline_doc["state"] == plain_doc["state"] == traced_doc["state"]
        assert baseline_doc["scenario"] == plain_doc["scenario"] == traced_doc["scenario"] == scenario

        facts = traced_doc["facts"]
        dispatch = [e for e in traced_doc["events"]["dreads"]
                    if e["pc"] & 0xffffffff == facts["dispatch_pc"] and e["paddr"] == 0x2000 and e["bytes"] == 4]
        assert len(dispatch) == 1, (scenario, dispatch)
        dispatch = dispatch[0]
        assert dispatch["value"] == facts["expected_pointer"] == facts["dispatch_register"]
        if scenario in ("stale", "same", "resident"):
            assert dispatch["hit_before"] is True
        else:
            assert dispatch["hit_before"] is False

        scalar_table_writes = [e for e in traced_doc["events"]["scalars"]
                               if e["write"] and e["address"] == 0x2000 and e["bytes"] == 4]
        if scenario == "resident":
            assert not scalar_table_writes
            writes = [e for e in traced_doc["events"]["dwrites"] if e["paddr"] == 0x2000]
            assert len(writes) == 1 and writes[0]["value"] == 0x80007200
            assert writes[0]["ordinal"] < dispatch["ordinal"]
            assert facts["final_backing"] == 0x80007100
        else:
            assert len(scalar_table_writes) == 1
            assert scalar_table_writes[0]["uncached_cpu"] is True
            assert scalar_table_writes[0]["ordinal"] < dispatch["ordinal"]
            assert scalar_table_writes[0]["value"] == facts["rewrite_value"]

        table_fills = [e for e in traced_doc["events"]["bursts"]
                       if (not e["write"]) and e["dcache"] and e["address"] == 0x2000 and e["bytes"] == 16]
        if scenario in ("refill", "same_refill"):
            assert len(table_fills) == 2 and table_fills[0]["ordinal"] < table_fills[1]["ordinal"] < dispatch["ordinal"]
        else:
            assert len(table_fills) == 1 and table_fills[0]["ordinal"] < dispatch["ordinal"]
        if scenario == "same_refill":
            assert table_fills[0]["words"][0] == table_fills[1]["words"][0] == 0x80007000
        if scenario == "same":
            assert facts["initial_table"] == facts["rewrite_value"] == facts["final_backing"] == dispatch["value"]

        evidence["cases"][scenario] = traced_doc

    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "evidence.json"
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print("EVIDENCE_SHA256=" + hashlib.sha256(canonical.encode()).hexdigest())
    print("EVIDENCE_PATH=" + str(path))
    print("SOURCE_DCACHE_SHA256=" + source_inputs["upstream_dcache"])
    print("SOURCE_RDRAM_SHA256=" + source_inputs["upstream_rdram"])
    for scenario in SCENARIOS:
        doc = evidence["cases"][scenario]
        dispatch = [e for e in doc["events"]["dreads"]
                    if e["paddr"] == 0x2000 and (e["pc"] & 0xffffffff) == doc["facts"]["dispatch_pc"]][0]
        print(f"CASE {scenario}: dispatch=0x{dispatch['value']:08x} hit_before={dispatch['hit_before']} backing=0x{doc['facts']['final_backing']:08x} marker=0x{doc['facts']['marker']:x}")
    print("PASS: exact interpreted table dispatches preserve resident-vs-backing distinctions with neutral instrumentation")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        run()


if __name__ == "__main__":
    main()
