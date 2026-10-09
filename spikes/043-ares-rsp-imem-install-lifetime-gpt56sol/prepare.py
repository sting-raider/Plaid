"""Generate exact-pin ares RSP shadows exposing completed IMEM lifecycle sinks."""
from pathlib import Path
import re


def generate(ref, out, sp_backing=False):
    assert not sp_backing, "this spike composes no SP backing shadow"
    ref, out = Path(ref), Path(out)

    header_src = ref / "ares/n64/rsp/rsp.hpp"
    header = header_src.read_text(encoding="utf-8")
    decl = '''// Project-owned completed RSP IMEM lifecycle callbacks; no object fields.\nusing PlaidRspImemInstallObserver = void (*)(u32,u32,u32,u32,u32,u32,u64);\ninline PlaidRspImemInstallObserver plaidRspImemInstallObserver = nullptr;\n'''
    dst_header = out / "include/n64/rsp/rsp.hpp"
    dst_header.parent.mkdir(parents=True, exist_ok=True)
    dst_header.write_text(decl + header, encoding="utf-8", newline="\n")

    dma = (ref / "ares/n64/rsp/dma.cpp").read_text(encoding="utf-8")
    promote = '''    dma.current = dma.pending;\n    dma.busy    = dma.full;\n    dma.full    = {0,0};'''
    assert dma.count(promote) == 1
    dma = dma.replace(promote, promote + '''\n    if(plaidRspImemInstallObserver) plaidRspImemInstallObserver(1, dma.current.pbusAddress, dma.current.dramAddress, dma.current.length, dma.current.count, dma.current.skip, 0);''')
    sink = '''        imem.write<Dual>(dma.current.pbusAddress, data);'''
    assert dma.count(sink) == 1
    dma = dma.replace(sink, sink + '''\n        if(plaidRspImemInstallObserver) plaidRspImemInstallObserver(2, dma.current.pbusAddress, dma.current.dramAddress, dma.current.length, dma.current.count, dma.current.skip, data);''')
    complete = '''  } else {\n    dma.busy = {0,0};\n    dma.current.length = 0xFF8;'''
    assert dma.count(complete) == 1
    dma = dma.replace(complete, '''  } else {\n    if(dma.busy.read && plaidRspImemInstallObserver) plaidRspImemInstallObserver(3, dma.current.pbusAddress, dma.current.dramAddress, dma.current.length, dma.current.count, dma.current.skip, 0);\n    dma.busy = {0,0};\n    dma.current.length = 0xFF8;''')
    dma_out = out / "rsp_install_dma.cpp"
    dma_out.write_text(dma, encoding="utf-8", newline="\n")

    io = (ref / "ares/n64/rsp/io.cpp").read_text(encoding="utf-8")
    cpu_sink = '''    if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);'''
    assert io.count(cpu_sink) == 1
    io = io.replace(cpu_sink, '''    if(address & 0x1000) {\n      recompiler.invalidate(address & 0xfff);\n      imem.write<Word>(address, data);\n      if(plaidRspImemInstallObserver) plaidRspImemInstallObserver(4, address & 0xfff, 0, 0, 0, 0, data);\n      return;\n    }''')
    io_out = out / "rsp_install_io.cpp"
    io_out.write_text(io, encoding="utf-8", newline="\n")

    rsp = (ref / "ares/n64/rsp/rsp.cpp").read_text(encoding="utf-8")
    replacements = {"dma.cpp": dma_out, "io.cpp": io_out}
    rsp = re.sub(r'#include "([^"]+)"', lambda m: f'#include "{replacements.get(m[1], ref / "ares/n64/rsp" / m[1])}"', rsp)
    rsp_out = out / "rsp_install.cpp"
    rsp_out.write_text(rsp, encoding="utf-8", newline="\n")

    unity_path = out / "n64.cpp"
    unity = unity_path.read_text(encoding="utf-8")
    marker = "#include <n64/rsp/rsp.cpp>"
    assert unity.count(marker) == 1
    unity_path.write_text(unity.replace(marker, f'#include "{rsp_out}"'), encoding="utf-8", newline="\n")
