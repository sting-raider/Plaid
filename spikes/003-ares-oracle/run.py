"""Build a separately licensed pinned core and check original CPU fixtures."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import shutil
import re
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
OUTPUT = ROOT / "target/ares-oracle-spike"


# MinGW names executables with .exe and links nall's Windows APIs; Linux needs libdl.
ORACLE = "oracle.exe" if os.name == "nt" else "oracle"

def build(driver, directory, raw_fetch_access=False, physical_fetch_access=False, extra_sources=(), cache_fill_access=False, cache_operation_access=False, rdram_burst_access=False, rdram_scalar_access=False, fetch_boundary_access=False, pi_dma_access=False, queue_access=False, sp_backing_access=False, pif_backing_access=False, rsp_dmem_access=False, cpu_instruction_access=False, rsp_word_read_access=False, rsp_dma_lifecycle_access=False, rsp_dma_pending_access=False, tlb_write_access=False, entryhi_write_access=False, entrylo_write_access=False, tlbr_load_access=False, dcache_access=False, memory_mutation_access=False, rsp_instruction_fetch_access=False,rsp_scalar_store_access=False,sp_dma_egress_access=False):
    if dcache_access: assert cpu_instruction_access and rdram_burst_access
    if cache_fill_access: assert raw_fetch_access and physical_fetch_access
    if cache_operation_access: assert raw_fetch_access and physical_fetch_access
    if rdram_burst_access: assert raw_fetch_access and physical_fetch_access
    if rdram_scalar_access: assert raw_fetch_access and physical_fetch_access
    if fetch_boundary_access: assert raw_fetch_access and physical_fetch_access
    if pi_dma_access: assert raw_fetch_access and physical_fetch_access
    if queue_access: assert raw_fetch_access and physical_fetch_access and pi_dma_access
    if sp_backing_access: assert raw_fetch_access and physical_fetch_access
    if sp_dma_egress_access: assert sp_backing_access and rdram_scalar_access
    if pif_backing_access: assert raw_fetch_access and physical_fetch_access
    if cpu_instruction_access: assert raw_fetch_access and physical_fetch_access
    if entryhi_write_access: assert tlb_write_access
    if entrylo_write_access: assert entryhi_write_access
    if tlbr_load_access: assert entrylo_write_access
    if tlb_write_access: assert cpu_instruction_access
    if rsp_word_read_access: assert rsp_dmem_access
    if rsp_instruction_fetch_access: assert rsp_dmem_access
    if rsp_scalar_store_access: assert rsp_dmem_access and rsp_instruction_fetch_access
    if rsp_dma_lifecycle_access: assert rsp_dmem_access
    if rsp_dma_pending_access: assert rsp_dma_lifecycle_access
    output = Path(directory)
    # Use the checkout's native stat implementation on DrvFS. Linux git can
    # rehash the entire reference tree because its index stats differ.
    git = shutil.which('git.exe') if str(REF).startswith('/mnt/') else None
    git = git or 'git'
    assert subprocess.check_output([git,"rev-parse","HEAD"],cwd=REF,text=True).strip() == REV
    subprocess.run([git,"-c","core.autocrlf=true","diff","--quiet","HEAD"],cwd=REF,check=True)
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
        "queue_access":queue_access,
        "queue_recipe":hashlib.sha256((ROOT/"spikes/032-ares-queue-identity/prepare.py").read_bytes()).hexdigest() if queue_access else None,
        "sp_backing_access":sp_backing_access,
        "sp_dma_egress_access":sp_dma_egress_access,
        "sp_recipe":hashlib.sha256((ROOT/"spikes/039-ares-cpu-sp-fetch/prepare.py").read_bytes()).hexdigest() if sp_backing_access else None,
        "pif_backing_access":pif_backing_access,
        "pif_recipe":hashlib.sha256((ROOT/"spikes/041-ares-boot-pif-history/prepare.py").read_bytes()).hexdigest() if pif_backing_access else None,
        "rsp_dmem_access":rsp_dmem_access,
        "rsp_dmem_recipe":hashlib.sha256((ROOT/"spikes/042-ares-rsp-dmem-history/prepare.py").read_bytes()).hexdigest() if rsp_dmem_access else None,
        "entryhi_write_access":entryhi_write_access,
        "entrylo_write_access":entrylo_write_access,
        "tlbr_load_access":tlbr_load_access,
        "tlb_write_access":tlb_write_access,
        "tlb_write_recipe":hashlib.sha256((ROOT/"spikes/075-tlb-mapped-cache-root-return/prepare.py").read_bytes()).hexdigest() if tlb_write_access else None,
        "cpu_instruction_access":cpu_instruction_access,
        "cpu_instruction_recipe":hashlib.sha256((ROOT/"spikes/044-ares-cpu-copy-dataflow/prepare.py").read_bytes()).hexdigest() if cpu_instruction_access else None,
        "extra_sources":{str(Path(p).relative_to(ROOT)):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in extra_sources},
        "fixture_driver":hashlib.sha256(Path(__file__).with_name("driver.cpp").read_bytes()).hexdigest(),
        "recipe":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if memory_mutation_access:
        inputs["memory_mutation_access"]=True
        inputs["memory_mutation_recipe"]=hashlib.sha256((ROOT/"spikes/086-storage-mutation-sensing/prepare.py").read_bytes()).hexdigest()
    if dcache_access:
        inputs["dcache_access"]=True
        inputs["dcache_recipe"]=hashlib.sha256((ROOT/"spikes/083-cached-ram-load-imem-consumption/prepare.py").read_bytes()).hexdigest()
    if rsp_word_read_access:
        inputs["rsp_word_read_access"]=True
    if rsp_instruction_fetch_access:
        inputs["rsp_instruction_fetch_access"]=True
    if rsp_dma_lifecycle_access:
        inputs["rsp_dma_lifecycle_access"]=True
    if rsp_dma_pending_access:
        inputs["rsp_dma_pending_access"]=True
    if rsp_scalar_store_access: inputs["rsp_scalar_store_access"]=True
    exe = output / ORACLE
    manifest = output / "build.json"
    # The inputs fully determine the oracle, so every checkout shares one copy.
    shared = Path(os.environ.get("PLAID_ORACLE_CACHE", Path.home() / ".cache/plaid/ares-oracle"))
    shared /= hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    built = lambda d: (d / "build.json").exists() and json.loads((d / "build.json").read_text()) == inputs and (d / ORACLE).exists()
    if not built(output) and built(shared):
        shutil.copy2(shared / ORACLE, exe)
        shutil.copyfile(shared / "build.json", manifest)
    if not built(output):
        # Required by the pinned core's cmake/common/compiler_common.cmake.
        # Vector union/lane accesses and signed shifts rely on these semantics.
        flags = ["-O2","-std=c++20","-msse4.1","-fwrapv","-fno-strict-aliasing","-DSLJIT_HAVE_CONFIG_PRE=1","-DSLJIT_HAVE_CONFIG_POST=1"]
        includes = [REF / p for p in ("ares","nall",".","thirdparty","thirdparty/xxhash","ares/n64/system")]
        queue_header = output/"include/nall/priority-queue.hpp"
        if queue_access:
            spec = importlib.util.spec_from_file_location("plaid_queue_generation", ROOT/"spikes/032-ares-queue-identity/prepare.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.generate(REF, queue_header)
        else:
            queue_header.unlink(missing_ok=True)
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
            if queue_access:
                header = """// Original optional request/CPU-dispatch scopes, no CPU object fields.
using PlaidPiIoDmaObserver = void (*)(bool, u32, u32, u32, u32);
inline PlaidPiIoDmaObserver plaidPiIoDmaObserver = nullptr;
using PlaidCpuQueueDispatchObserver = void (*)(bool, u32);
inline PlaidCpuQueueDispatchObserver plaidCpuQueueDispatchObserver = nullptr;
struct PlaidQueueDispatchScope {
  u32 event;
  explicit PlaidQueueDispatchScope(u32 event) : event(event) {
    if(plaidCpuQueueDispatchObserver) plaidCpuQueueDispatchObserver(true, event);
  }
  ~PlaidQueueDispatchScope() {
    if(plaidCpuQueueDispatchObserver) plaidCpuQueueDispatchObserver(false, event);
  }
};
""" + header
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
        elif rsp_dmem_access:
            # An RSP-only shadow also needs precedence over upstream headers.
            # Do not inherit stale CPU/RDRAM shadows from a prior option set.
            for name in ("cpu/cpu.hpp","rdram/rdram.hpp"):
                (output/"include/n64"/name).unlink(missing_ok=True)
            includes.insert(0, output / "include")
        mutation_header = output/"include/n64/memory/lsb/writable.hpp"
        if memory_mutation_access:
            spec = importlib.util.spec_from_file_location("plaid_storage_mutation_generation", ROOT/"spikes/086-storage-mutation-sensing/prepare.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.generate(REF, output)
            if output/"include" not in includes: includes.insert(0, output/"include")
        else:
            mutation_header.unlink(missing_ok=True)
            (output/"include/n64/memory/memory.hpp").unlink(missing_ok=True)
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
            pi_replacements = {"dma.cpp":output/"pi_dma.cpp"}
            if queue_access:
                pi_io = (REF/"ares/n64/pi/io.cpp").read_text()
                for direction in ("Read", "Write"):
                    name=direction.lower()
                    marker=f"    cpu.queueInsert(Queue::PI_DMA_{direction}, dmaDuration({str(direction == 'Read').lower()}));\n    dma{direction}();"
                    assert pi_io.count(marker)==1
                    before=f"    if(plaidPiIoDmaObserver) plaidPiIoDmaObserver(true, Queue::PI_DMA_{direction}, io.dramAddress, io.pbusAddress, io.{name}Length+1);\n"
                    after=f"\n    if(plaidPiIoDmaObserver) plaidPiIoDmaObserver(false, Queue::PI_DMA_{direction}, io.dramAddress, io.pbusAddress, io.{name}Length);"
                    pi_io=pi_io.replace(marker,before+marker+after)
                (output/"pi_io.cpp").write_text(pi_io)
                pi_replacements["io.cpp"]=output/"pi_io.cpp"
            pi_source = re.sub(r'#include "([^"]+)"',lambda m:f'#include "{pi_replacements.get(m[1], REF / "ares/n64/pi" / m[1])}"',pi_source)
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
            if queue_access:
                marker="  queue.step(clocks, [](u32 event) {"
                assert cpu.count(marker)==1
                cpu=cpu.replace(marker,marker+"\n    PlaidQueueDispatchScope plaidDispatchScope(event);")
            assert cpu.count('#include "memory.cpp"') == 1
            # Relocating this TU changes quoted-include lookup. Resolve every
            # CPU include explicitly; system/serialization.cpp shares a name.
            cpu = re.sub(r'#include "([^"]+)"', lambda match:
                f'#include "{replacements.get(match[1], REF / "ares/n64/cpu" / match[1])}"', cpu)
            (output / "cpu.cpp").write_text(cpu)
            assert unity.count("#include <n64/cpu/cpu.cpp>") == 1
            unity = unity.replace("#include <n64/cpu/cpu.cpp>", f'#include "{output / "cpu.cpp"}"')
        (output / "n64.cpp").write_text(unity)
        if sp_backing_access:
            spec = importlib.util.spec_from_file_location("plaid_sp_generation", ROOT/"spikes/039-ares-cpu-sp-fetch/prepare.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.generate(REF, output,egress=sp_dma_egress_access)
        else:
            (output / "include/n64/rsp/rsp.hpp").unlink(missing_ok=True)
        if pif_backing_access:
            spec = importlib.util.spec_from_file_location("plaid_pif_generation", ROOT/"spikes/041-ares-boot-pif-history/prepare.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.generate(REF, output)
        else:
            (output / "include/n64/pif/pif.hpp").unlink(missing_ok=True)
        if rsp_dmem_access:
            spec = importlib.util.spec_from_file_location("plaid_rsp_dmem_generation", ROOT/"spikes/042-ares-rsp-dmem-history/prepare.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.generate(REF, output,sp_backing=sp_backing_access,word_reads=rsp_word_read_access,dma_lifecycle=rsp_dma_lifecycle_access,dma_pending=rsp_dma_pending_access,instruction_fetches=rsp_instruction_fetch_access,scalar_stores=rsp_scalar_store_access)
        if cpu_instruction_access:
            spec = importlib.util.spec_from_file_location("plaid_cpu_instruction_generation", ROOT/"spikes/044-ares-cpu-copy-dataflow/prepare.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.generate(REF, output)
        if tlb_write_access:
            spec = importlib.util.spec_from_file_location("plaid_tlb_write_generation", ROOT/"spikes/075-tlb-mapped-cache-root-return/prepare.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.generate(REF, output,entryhi=entryhi_write_access,entrylo=entrylo_write_access,tlbr=tlbr_load_access)
        if dcache_access:
            spec = importlib.util.spec_from_file_location("plaid_operand_dcache_generation", ROOT/"spikes/083-cached-ram-load-imem-consumption/prepare.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.generate(REF, output)
        objects = []
        with (output / "build.log").open("w") as log:
            for name, source in [("sljit",REF / "thirdparty/sljit/sljit_src/sljitLir.c"),("libco",REF / "libco/libco.c")]:
                obj = output / f"{name}.o"
                subprocess.run(["gcc","-O1",*include_flags,"-DSLJIT_HAVE_CONFIG_PRE=1","-DSLJIT_HAVE_CONFIG_POST=1","-c",str(source),"-o",str(obj)],check=True,stdout=log,stderr=subprocess.STDOUT)
                objects.append(obj)
            compiled_driver = driver
            if os.name == "nt":
                compiled_driver = output / "native-driver.cpp"
                compiled_driver.write_text("#include <cstdio>\n#include <fcntl.h>\n#include <io.h>\n"
                    "namespace { struct PlaidBinaryOutput { PlaidBinaryOutput() {\n"
                    "  _setmode(_fileno(stdout), _O_BINARY); _setmode(_fileno(stderr), _O_BINARY);\n"
                    "} } plaidBinaryOutput; }\n" + '#include "' + driver.resolve().as_posix() + '"\n' +
                    "\n#include <nall/terminal.hpp>\nnamespace { const bool plaidAnsiOutput = [] {\n"
                    "  nall::terminal::setEscapable(true); return true; }(); }\n")
            sources = [compiled_driver,output / "core.cpp",output / "n64.cpp",REF / "ares/component/processor/sm5k/sm5k.cpp",
                REF / "ares/ares/memory/fixed-allocator.cpp",REF / "nall/nall/nall.cpp",REF / "thirdparty/sljitAllocator.cpp"]
            try:
                # Adapter edits must not rebuild the unchanged pinned core.
                # All reference/options/recipe inputs still invalidate its objects.
                recipe = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
                headers = b''.join(p.read_bytes() for p in sorted((output / 'include').rglob('*')) if p.is_file())
                for source in sources:
                    dependencies = dict(inputs)
                    if source != compiled_driver:
                        dependencies.pop('driver')
                    digest = hashlib.sha256(json.dumps([dependencies, flags, include_flags, recipe], sort_keys=True).encode()
                                            + headers + source.read_bytes()).hexdigest()
                    obj, stamp = output / (source.name + '.o'), output / (source.name + '.sha256')
                    if not obj.exists() or not stamp.exists() or stamp.read_text() != digest:
                        temporary = obj.with_suffix('.tmp.o')
                        stamp.unlink(missing_ok=True)
                        try:
                            subprocess.run(["g++",*flags,*include_flags,"-c",str(source),"-o",str(temporary)],check=True,stdout=log,stderr=subprocess.STDOUT)
                            temporary.replace(obj)
                            stamp.write_text(digest)
                        finally:
                            temporary.unlink(missing_ok=True)
                    objects.append(obj)
                subprocess.run(["g++",*map(str,objects),"-pthread",*(["-lws2_32","-lshlwapi","-lole32","-luuid"] if os.name == "nt" else ["-ldl"]),"-o",str(exe)],check=True,stdout=log,stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError:
                print("\n".join((output / "build.log").read_text().splitlines()[-30:]))
                raise
        manifest.write_text(json.dumps(inputs,indent=2)+"\n")
        shared.mkdir(parents=True,exist_ok=True)
        for name in (ORACLE,"build.json"):
            temporary = shared / f"{name}.{os.getpid()}.tmp"
            shutil.copy2(output / name, temporary)
            os.replace(temporary, shared / name)
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
    worker()


if __name__ == "__main__": main()
