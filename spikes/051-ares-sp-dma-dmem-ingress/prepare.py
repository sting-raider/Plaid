"""Original finite-fixture observers, generated only beneath ignored output."""
import re
import subprocess


def build_traced(builder, driver, output):
    out = output / "traced-build"
    out.mkdir(parents=True, exist_ok=True)
    (out / "build.json").unlink(missing_ok=True)
    builder.build(driver, out)

    # Observe only successful ordinary RDRAM reads. This marker is after the
    # pinned bounds/translation checks; OOB reads return before it.
    include = out / "include/n64/rdram/rdram.hpp"
    include.parent.mkdir(parents=True, exist_ok=True)
    ram = (builder.REF / "ares/n64/rdram/rdram.hpp").read_text()
    marker = "      return Memory::Writable::read<Size>(address);"
    assert ram.count(marker) == 1
    ram = ram.replace(marker, """      u64 plaidValue = Memory::Writable::read<Size>(address);
      if(plaidRdramReadObserver) plaidRdramReadObserver(address, Size, (u32)device, plaidValue);
      return plaidValue;""")
    declarations = """// Project-owned research callbacks; no reference object-layout changes.
using PlaidRdramReadObserver = void (*)(u32, u32, u32, u64);
using PlaidRspDmemDmaWriteObserver = void (*)(u32, u32, u32);
using PlaidRspDmemDirectWriteObserver = void (*)(u32, u32, bool);
inline PlaidRdramReadObserver plaidRdramReadObserver = nullptr;
inline PlaidRspDmemDmaWriteObserver plaidRspDmemDmaWriteObserver = nullptr;
inline PlaidRspDmemDirectWriteObserver plaidRspDmemDirectWriteObserver = nullptr;
"""
    include.write_text(declarations + ram)

    dma = (builder.REF / "ares/n64/rsp/dma.cpp").read_text()
    marker = """        u32 dataLo = rdram.ram.read<Word>(dma.current.dramAddress + 0, RBusDevice::SP_DMA);
        u32 dataHi = rdram.ram.read<Word>(dma.current.dramAddress + 4, RBusDevice::SP_DMA);
        dmem.write<Word>(dma.current.pbusAddress + 0, dataLo);
        dmem.write<Word>(dma.current.pbusAddress + 4, dataHi);"""
    assert dma.count(marker) == 1
    replacement = """        u32 dataLo = rdram.ram.read<Word>(dma.current.dramAddress + 0, RBusDevice::SP_DMA);
        u32 dataHi = rdram.ram.read<Word>(dma.current.dramAddress + 4, RBusDevice::SP_DMA);
        dmem.write<Word>(dma.current.pbusAddress + 0, dataLo);
        if(plaidRspDmemDmaWriteObserver) plaidRspDmemDmaWriteObserver(dma.current.dramAddress + 0, dma.current.pbusAddress + 0, dataLo);
        dmem.write<Word>(dma.current.pbusAddress + 4, dataHi);
        if(plaidRspDmemDmaWriteObserver) plaidRspDmemDmaWriteObserver(dma.current.dramAddress + 4, dma.current.pbusAddress + 4, dataHi);"""
    dma_path = out / "rsp_dma.cpp"
    dma_path.write_text(dma.replace(marker, replacement))

    io = (builder.REF / "ares/n64/rsp/io.cpp").read_text()
    marker = "    else                 return dmem.write<Word>(address, data);"
    assert io.count(marker) == 1
    replacement = """    else {
      dmem.write<Word>(address, data);
      if(plaidRspDmemDirectWriteObserver) plaidRspDmemDirectWriteObserver(address & 0xfff, data, &thread != this);
      return;
    }"""
    io_path = out / "rsp_io.cpp"
    io_path.write_text(io.replace(marker, replacement))

    rsp_src = (builder.REF / "ares/n64/rsp/rsp.cpp").read_text()
    replacements = {"dma.cpp": dma_path, "io.cpp": io_path}
    rsp_src = re.sub(r'#include "([^"]+)"', lambda m:
        f'#include "{replacements.get(m[1], builder.REF / "ares/n64/rsp" / m[1])}"', rsp_src)
    rsp_path = out / "rsp.cpp"
    rsp_path.write_text(rsp_src)

    unity = (out / "n64.cpp").read_text()
    marker = "#include <n64/rsp/rsp.cpp>"
    assert unity.count(marker) == 1
    (out / "n64.cpp").write_text(unity.replace(marker, f'#include "{rsp_path}"'))

    flags = ["-O1", "-std=c++20", "-msse4.1", "-DSLJIT_HAVE_CONFIG_PRE=1", "-DSLJIT_HAVE_CONFIG_POST=1", "-DPLAID_DMEM_INGRESS_OBSERVER=1"]
    includes = [out / "include", *(builder.REF / p for p in ("ares", "nall", ".", "thirdparty", "thirdparty/xxhash", "ares/n64/system"))]
    include_flags = [part for path in includes for part in ("-I", str(path))]
    sources = [driver, out / "core.cpp", out / "n64.cpp", builder.REF / "ares/component/processor/sm5k/sm5k.cpp",
        builder.REF / "ares/ares/memory/fixed-allocator.cpp", builder.REF / "nall/nall/nall.cpp", builder.REF / "thirdparty/sljitAllocator.cpp"]
    exe = out / "oracle-traced"
    with (out / "traced-build.log").open("w", encoding="utf-8") as log:
        try:
            subprocess.run(["g++", *flags, *include_flags, *map(str, sources), str(out / "sljit.o"), str(out / "libco.o"),
                "-pthread", "-ldl", "-o", str(exe)], check=True, stdout=log, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print("\n".join((out / "traced-build.log").read_text(encoding="utf-8").splitlines()[-80:]), flush=True)
            raise
    return exe

