"""Build a separately licensed pinned core and check original CPU fixtures."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import shutil
import re

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
OUTPUT = ROOT / "target/ares-oracle-spike"


def build(driver, directory, raw_fetch_access=False, physical_fetch_access=False, extra_sources=(), cache_fill_access=False, cache_operation_access=False, rdram_burst_access=False, rdram_scalar_access=False, fetch_boundary_access=False, pi_dma_access=False):
    if cache_fill_access: assert raw_fetch_access and physical_fetch_access
    if cache_operation_access: assert raw_fetch_access and physical_fetch_access
    if rdram_burst_access: assert raw_fetch_access and physical_fetch_access
    if rdram_scalar_access: assert raw_fetch_access and physical_fetch_access
    if fetch_boundary_access: assert raw_fetch_access and physical_fetch_access
    if pi_dma_access: assert raw_fetch_access and physical_fetch_access
    output = Path(directory)
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=REF,text=True).strip() == REV
    subprocess.run(["git","-c","core.autocrlf=true","diff","--quiet","HEAD"],cwd=REF,check=True)
    output.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(REF / "LICENSE", output / "LICENSE")
    driver = Path(driver)
    compiler = subprocess.check_output(["g++","--version"],text=True).splitlines()[0]
    inputs = {"revision":REV,"compiler":compiler,"driver":hashlib.sha256(driver.read_bytes()).hexdigest(),
        "raw_fetch_access":raw_fetch_access,
        "physical_fetch_access":physical_fetch_access,
        "cache_fill_access":cache_fill_access,
        "cache_operation_access":cache_operation_access,
        "rdram_burst_access":rdram_burst_access,
        "rdram_scalar_access":rdram_scalar_access,
        "fetch_boundary_access":fetch_boundary_access,
        "pi_dma_access":pi_dma_access,
        "extra_sources":{str(Path(p).relative_to(ROOT)):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in extra_sources},
        "fixture_driver":hashlib.sha256(Path(__file__).with_name("driver.cpp").read_bytes()).hexdigest(),
        "recipe":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    exe = output / "oracle"
    manifest = output / "build.json"
    if not manifest.exists() or json.loads(manifest.read_text()) != inputs or not exe.exists():
        flags = ["-O1","-std=c++20","-msse4.1","-DSLJIT_HAVE_CONFIG_PRE=1","-DSLJIT_HAVE_CONFIG_POST=1"]
        includes = [REF / p for p in ("ares","nall",".","thirdparty","thirdparty/xxhash","ares/n64/system")]
        if raw_fetch_access:
            # Expose existing debugger input through an accessor in a generated
            # header. No CPU fields, instruction code or object layout changes.
            header = (REF / "ares/n64/cpu/cpu.hpp").read_text()
            signature = "    auto disassemble(u32 address, u32 instruction) -> string;"
            assert header.count(signature) == 1
            header = header.replace(signature, signature + "\n    auto fetchedWord() const -> u32 { return instruction; }")
            if physical_fetch_access:
                header = "// Project-owned observer metadata; no CPU object-layout change.\nstruct PlaidFetchAccess { u32 physical; bool cached; };\ninline PlaidFetchAccess plaidFetchAccess;\n" + header
            if cache_fill_access:
                assert physical_fetch_access
                marker = "        cpu.busReadBurst<ICache>(tag | index, words);"
                assert header.count(marker) == 1
                header = header.replace(marker,marker + "\n        if(plaidCacheFillObserver) plaidCacheFillObserver(static_cast<u32>(this - cpu.icache.lines), paddr, index, words);")
                header = "// Project-owned callback after the existing completed cache fill.\nusing PlaidCacheFillObserver = void (*)(u32, u32, u32, const u32*);\ninline PlaidCacheFillObserver plaidCacheFillObserver = nullptr;\n" + header
            if cache_operation_access:
                header = "// Project-owned callback around completed guest instruction-cache operations.\nusing PlaidCacheOperationObserver = void (*)(u64, u32, u64, u32, u32, u32, const u32*, const u32*);\ninline PlaidCacheOperationObserver plaidCacheOperationObserver = nullptr;\n" + header
            if fetch_boundary_access:
                header = "// Project-owned callbacks bracketing a successful CPU fetch access.\nusing PlaidCpuFetchObserver = void (*)(bool, u64, u32, u32, bool, u32);\ninline PlaidCpuFetchObserver plaidCpuFetchObserver = nullptr;\n" + header
            if pi_dma_access:
                header = "// Project-owned PI DMA buffered-read/write boundaries.\nusing PlaidPiDmaObserver = void (*)(u32, u32, u32, u32, u32, u32);\ninline PlaidPiDmaObserver plaidPiDmaObserver = nullptr;\n" + header
            destination = output / "include/n64/cpu/cpu.hpp"
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(header)
            includes.insert(0, output / "include")
            if rdram_burst_access:
                ram = (REF / "ares/n64/rdram/rdram.hpp").read_text()
                marker = "      self.hidden.updateBurst<Size>(address, value);"
                assert ram.count(marker) == 1
                ram = ram.replace(marker,marker + "\n      if(self.mapIdentity && plaidRdramBurstObserver) plaidRdramBurstObserver(true, address, Size, (u32)device, value);")
                begin = "    template<u32 Size>\n    auto readBurst(u32 address, u32 *value, RBusDevice device) -> void {"
                end = "  } ram{*this};"
                assert ram.count(begin) == ram.count(end) == 1
                start, stop = ram.index(begin), ram.index(end)
                block = ram[start:stop]
                assert block.endswith("    }\n\n")
                block = block[:-7] + "      if(plaidRdramBurstObserver) plaidRdramBurstObserver(false, address, Size, (u32)device, value);\n    }\n\n"
                ram = ram[:start] + block + ram[stop:]
                ram = "// Project-owned identity-mapped successful RAM-burst callback.\nusing PlaidRdramBurstObserver = void (*)(bool, u32, u32, u32, const u32*);\ninline PlaidRdramBurstObserver plaidRdramBurstObserver = nullptr;\n" + ram
                destination = output / "include/n64/rdram/rdram.hpp"
                destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_text(ram)
            elif not rdram_scalar_access:
                # Do not shadow the original header when reusing a prior sensor build.
                (output / "include/n64/rdram/rdram.hpp").unlink(missing_ok=True)
            if rdram_scalar_access:
                destination = output / "include/n64/rdram/rdram.hpp"
                ram = destination.read_text() if rdram_burst_access else (REF / "ares/n64/rdram/rdram.hpp").read_text()
                marker = "      return Memory::Writable::read<Size>(address);"
                assert ram.count(marker) == 1
                ram = ram.replace(marker,"""      u64 plaidValue = Memory::Writable::read<Size>(address);
      if(plaidRdramScalarObserver) plaidRdramScalarObserver(false, address, Size, (u32)device, plaidValue);
      return plaidValue;""")
                marker = "      self.hidden.update<Size>(address, value);"
                assert ram.count(marker) == 1
                ram = ram.replace(marker,marker + "\n      if(self.mapIdentity && plaidRdramScalarObserver) plaidRdramScalarObserver(true, address, Size, (u32)device, value);")
                ram = "// Project-owned successful identity-mapped ordinary RAM callbacks.\nusing PlaidRdramScalarObserver = void (*)(bool, u32, u32, u32, u64);\ninline PlaidRdramScalarObserver plaidRdramScalarObserver = nullptr;\n" + ram
                destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_text(ram)
        include_flags = [part for path in includes for part in ("-I",str(path))]
        core = (REF / "ares/ares/ares.cpp.in").read_text().replace("#include <ares/resource/resource.cpp>", "// UI-only resources omitted in headless build.")
        for key, value in {"ARES_NAME":"Plaid pinned ares oracle", "ARES_VERSION":REV,
                "ARES_LEGAL_COPYRIGHT_SHORT":"See upstream LICENSE", "ARES_WEBSITE":"ares-emu.net"}.items():
            core = core.replace(f"@{key}@", value)
        (output / "core.cpp").write_text(core)
        # The pin leaves one Vulkan load call unguarded in System::run. Guard
        # only that renderer call in a generated TU; CPU/RSP sources stay exact.
        system = (REF / "ares/n64/system/system.cpp").read_text()
        assert system.count("    vulkan.load(node);") == 1
        system = system.replace("    vulkan.load(node);", "#if defined(VULKAN)\n    vulkan.load(node);\n#endif")
        (output / "system.cpp").write_text(system)
        unity = (REF / "ares/n64/n64.cpp").read_text()
        assert unity.count("#include <n64/system/system.cpp>") == 1
        unity = unity.replace("#include <n64/system/system.cpp>", f'#include "{output / "system.cpp"}"')
        if pi_dma_access:
            dma = (REF / "ares/n64/pi/dma.cpp").read_text()
            begin = "auto PI::dmaWrite() -> void {"
            end = "\nauto PI::dmaFinished() -> void {"
            assert dma.count(begin) == dma.count(end) == 1
            start,stop = dma.index(begin),dma.index(end)
            block = dma[start:stop]
            block = block.replace(begin,begin + "\n  if(plaidPiDmaObserver) plaidPiDmaObserver(1, io.dramAddress, io.pbusAddress, io.writeLength + 1, 0, 0);")
            marker = "    i32 curLen = min(length, blockLen);"
            assert block.count(marker) == 1
            block = block.replace(marker,marker + "\n    if(plaidPiDmaObserver) plaidPiDmaObserver(2, io.dramAddress, io.pbusAddress, curLen, misalign, firstBlock);")
            marker = "      u16 data = busReadHalf();"
            assert block.count(marker) == 1
            block = block.replace(marker,marker + "\n      if(plaidPiDmaObserver) plaidPiDmaObserver(3, io.dramAddress, io.pbusAddress, curLen, i, data);")
            for lane in ("i","i+0","i+1"):
                marker = f"        rdram.ram.write<Byte>(io.dramAddress++, mem[{lane}], RBusDevice::PI_DMA);"
                assert block.count(marker) == 1
                before = f"        if(plaidPiDmaObserver) plaidPiDmaObserver(4, io.dramAddress, io.pbusAddress, curLen, {lane}, mem[{lane}]);\n"
                after = f"\n        if(plaidPiDmaObserver) plaidPiDmaObserver(5, io.dramAddress-1, io.pbusAddress, curLen, {lane}, mem[{lane}]);"
                block = block.replace(marker,before + marker + after)
            marker = "    io.dramAddress = (io.dramAddress + 7) & ~7;"
            assert block.count(marker) == 1
            block = block.replace(marker,"    if(plaidPiDmaObserver) plaidPiDmaObserver(6, io.dramAddress, io.pbusAddress, curLen, misalign, firstBlock);\n"+marker)
            assert block.endswith("}\n")
            block = block[:-2]+"  if(plaidPiDmaObserver) plaidPiDmaObserver(7, io.dramAddress, io.pbusAddress, io.writeLength, 0, 0);\n}\n"
            dma = dma[:start]+block+dma[stop:]
            marker = "  mi.raise(MI::IRQ::PI);"
            assert dma.count(marker) == 1
            dma = dma.replace(marker,marker+"\n  if(plaidPiDmaObserver) plaidPiDmaObserver(8, io.dramAddress, io.pbusAddress, io.writeLength, io.dmaBusy, io.interrupt);")
            (output/"pi_dma.cpp").write_text(dma)
            pi_source = (REF/"ares/n64/pi/pi.cpp").read_text()
            assert pi_source.count('#include "dma.cpp"') == 1
            pi_source = re.sub(r'#include "([^"]+)"',lambda m:f'#include "{output / "pi_dma.cpp" if m[1] == "dma.cpp" else REF / "ares/n64/pi" / m[1]}"',pi_source)
            (output/"pi.cpp").write_text(pi_source)
            assert unity.count("#include <n64/pi/pi.cpp>") == 1
            unity = unity.replace("#include <n64/pi/pi.cpp>",f'#include "{output/"pi.cpp"}"')
        if physical_fetch_access:
            assert raw_fetch_access
            memory = (REF / "ares/n64/cpu/memory.cpp").read_text()
            marker = "  if(context.littleEndian()) paddr = reverseEndianPaddr<Word>(paddr);\n  if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);"
            assert memory.count(marker) == 1
            memory = memory.replace(marker, marker.split("\n")[0] + "\n  plaidFetchAccess = {paddr, access.cache};\n" + marker.split("\n")[1])
            if fetch_boundary_access:
                marker = "  if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);\n  return busRead<Word>(paddr);"
                assert memory.count(marker) == 1
                memory = memory.replace(marker,"""  if(plaidCpuFetchObserver) plaidCpuFetchObserver(true, access.vaddr, access.paddr, paddr, access.cache, 0);
  u32 value = access.cache ? icache.fetch(access.vaddr, paddr, cpu) : busRead<Word>(paddr);
  if(plaidCpuFetchObserver) plaidCpuFetchObserver(false, access.vaddr, access.paddr, paddr, access.cache, value);
  return value;""")
            (output / "cpu_memory.cpp").write_text(memory)
            replacements = {"memory.cpp":output / "cpu_memory.cpp"}
            if cache_operation_access:
                ipu = (REF / "ares/n64/cpu/interpreter-ipu.cpp").read_text()
                begin = "auto CPU::CACHE(u8 operation, cr64& rs, s16 imm) -> void {"
                end = "\nauto CPU::DADD(r64& rd, cr64& rs, cr64& rt) -> void {"
                assert ipu.count(begin) == ipu.count(end) == 1
                start, stop = ipu.index(begin), ipu.index(end)
                block = ipu[start:stop]
                marker = "  switch(operation) {"
                assert block.count(marker) == 1 and block.endswith("  }\n}\n")
                before = """  bool plaidObserveCache = plaidCacheOperationObserver &&
    (operation == 0x00 || operation == 0x08 || operation == 0x10 || operation == 0x14 || operation == 0x18);
  u32 plaidTagBefore = 0, plaidWordsBefore[8]{};
  if(plaidObserveCache) {
    const auto& line = icache.line(access.vaddr);
    plaidTagBefore = line.tagKey;
    for(u32 i=0;i<8;i++) plaidWordsBefore[i] = line.words[i];
  }
"""
                block = block.replace(marker,before + marker)
                after = """  if(plaidObserveCache) {
    const auto& line = icache.line(access.vaddr);
    plaidCacheOperationObserver(ipu.pc, operation, access.vaddr, access.paddr,
      plaidTagBefore, line.tagKey, plaidWordsBefore, line.words);
  }
"""
                block = block[:-2] + after + "}\n"
                (output / "cpu_interpreter_ipu.cpp").write_text(ipu[:start] + block + ipu[stop:])
                replacements["interpreter-ipu.cpp"] = output / "cpu_interpreter_ipu.cpp"
            cpu = (REF / "ares/n64/cpu/cpu.cpp").read_text()
            assert cpu.count('#include "memory.cpp"') == 1
            # Relocating this TU changes quoted-include lookup. Resolve every
            # CPU include explicitly; system/serialization.cpp shares a name.
            cpu = re.sub(r'#include "([^"]+)"', lambda match:
                f'#include "{replacements.get(match[1], REF / "ares/n64/cpu" / match[1])}"', cpu)
            (output / "cpu.cpp").write_text(cpu)
            assert unity.count("#include <n64/cpu/cpu.cpp>") == 1
            unity = unity.replace("#include <n64/cpu/cpu.cpp>", f'#include "{output / "cpu.cpp"}"')
        (output / "n64.cpp").write_text(unity)
        objects = []
        with (output / "build.log").open("w") as log:
            for name, source in [("sljit",REF / "thirdparty/sljit/sljit_src/sljitLir.c"),("libco",REF / "libco/libco.c")]:
                obj = output / f"{name}.o"
                subprocess.run(["gcc","-O1",*include_flags,"-DSLJIT_HAVE_CONFIG_PRE=1","-DSLJIT_HAVE_CONFIG_POST=1","-c",str(source),"-o",str(obj)],check=True,stdout=log,stderr=subprocess.STDOUT)
                objects.append(obj)
            sources = [driver,output / "core.cpp",output / "n64.cpp",REF / "ares/component/processor/sm5k/sm5k.cpp",
                REF / "ares/ares/memory/fixed-allocator.cpp",REF / "nall/nall/nall.cpp",REF / "thirdparty/sljitAllocator.cpp"]
            try:
                subprocess.run(["g++",*flags,*include_flags,*map(str,sources),*map(str,objects),"-pthread","-ldl","-o",str(exe)],check=True,stdout=log,stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError:
                print("\n".join((output / "build.log").read_text().splitlines()[-30:]))
                raise
        manifest.write_text(json.dumps(inputs,indent=2)+"\n")
    return exe


def worker():
    exe = build(Path(__file__).with_name("driver.cpp"), OUTPUT)
    results = {}
    for case in ("cartridge","linked","unaligned","slot_exception"):
        first = subprocess.check_output([str(exe),case],text=True,timeout=10)
        assert first == subprocess.check_output([str(exe),case],text=True,timeout=10)
        results[case] = json.loads(first)
    cartridge = results["cartridge"]
    assert cartridge["pc"] == 0xb0001014 and cartridge["exception"] == 0
    assert [cartridge["regs"][r] for r in (8,16,17,18,19,31)] == [-1342173152,5,3,7,2,-1342173168]
    linked = results["linked"]
    assert linked["pc"] == 0xa000000c and linked["regs"][4] == 1 and linked["exception"] == 0
    assert linked["memory"] == 0x123456789abcdef1 and linked["lladdr"] == 0x200
    for case, bd in (("unaligned",0),("slot_exception",1)):
        state = results[case]
        assert (state["exception"],state["bd"],state["epc"],state["badva"],state["pc"]) == (
            4, bd, 0xffffffffa0000000, 0xffffffffa0002001, 0xbfc00380), state
    for case, state in results.items():
        expected = [0] * 32
        if case == "cartridge":
            for register, value in zip((8,16,17,18,19,31),(-1342173152,5,3,7,2,-1342173168)):
                expected[register] = value
            assert state["memory"] == 0
        else:
            expected[3] = -1610604544
            if case == "linked": expected[4] = 1
            else: assert state["memory"] == 0x123456789abcdef0
        assert state["regs"] == expected and state["hi"] == state["lo"] == 0, (case,state)
    sys.path.insert(0, str(ROOT / "scripts"))
    import test_mupen_execution as mupen
    subprocess.run([sys.executable,str(ROOT / "scripts/prepare_mupen.py")],check=True)
    comparison = OUTPUT / "mupen"
    comparison.mkdir(exist_ok=True)
    for scenario in mupen.SCENARIOS:
        data = bytearray(8192)
        data[:4] = bytes.fromhex("80371240")
        for offset, word in mupen.program(scenario).items():
            data[64+offset:68+offset] = word.to_bytes(4, "big")
        (comparison / f"{scenario}.z64").write_bytes(data)
    mupen.worker(comparison)
    for scenario in mupen.SCENARIOS:
        raw = subprocess.check_output([str(exe),"fixture",str(comparison / f"{scenario}.z64")],text=True,timeout=10)
        assert raw == subprocess.check_output([str(exe),"fixture",str(comparison / f"{scenario}.z64")],text=True,timeout=10)
        state = json.loads(raw)
        shared = {key:state[key] for key in ("pc","regs","hi","lo")}
        for mode, other in json.loads((comparison / f"{scenario}-states.json").read_text()).items():
            assert shared == other, (scenario,mode,shared,other)
        assert state["exception"] == 0, (scenario,state)
        results[scenario] = state
    (OUTPUT / "results.json").write_text(json.dumps(results,indent=2)+"\n")
    print(f"PASS: four ares capability fixtures and {len(mupen.SCENARIOS)} independent CPU comparisons; repeated states match")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
