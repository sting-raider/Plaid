"Project-owned callback shadows around the exact completed SP Word read/write effects."
from pathlib import Path
import re

RSP_HEADER_SHA256 = None  # Filled by run.py from the exact pin for the receipt.
RSP_IO_SHA256 = None

def generate(ref, out):
    ref, out = Path(ref), Path(out)
    header_path = ref / "ares/n64/rsp/rsp.hpp"
    io_source_path = ref / "ares/n64/rsp/io.cpp"

    header = header_path.read_text(encoding="utf-8")
    declarations = """// Project-owned research callback; no reference object fields.
using PlaidCopySpWordObserver = void (*)(bool,u32,u32,u32,u32,bool);
inline PlaidCopySpWordObserver plaidCopySpWordObserver = nullptr;
"""
    destination = out / "include/n64/rsp/rsp.hpp"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(declarations + header, encoding="utf-8", newline="\n")

    io = io_source_path.read_text(encoding="utf-8")
    before = """    if(address & 0x1000) return imem.read<Word>(address);
    else                 return dmem.read<Word>(address);"""
    after = """    u32 plaidCopyValue = address & 0x1000 ? imem.read<Word>(address) : dmem.read<Word>(address);
    if(plaidCopySpWordObserver) plaidCopySpWordObserver(false,address,(address>>12)&1,address&0xffc,plaidCopyValue,&thread==&cpu);
    return plaidCopyValue;"""
    assert io.count(before) == 1
    io = io.replace(before, after)

    before = """    if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);
    else                 return dmem.write<Word>(address, data);"""
    after = """    if(address & 0x1000) { recompiler.invalidate(address & 0xfff); imem.write<Word>(address,data); }
    else dmem.write<Word>(address,data);
    if(plaidCopySpWordObserver) plaidCopySpWordObserver(true,address,(address>>12)&1,address&0xffc,data,&thread==&cpu);
    return;"""
    assert io.count(before) == 1
    io = io.replace(before, after)

    io_path = out / "rsp_io.cpp"
    io_path.write_text(io, encoding="utf-8", newline="\n")

    rsp = (ref / "ares/n64/rsp/rsp.cpp").read_text(encoding="utf-8")
    rsp = re.sub(
        r'#include "([^"]+)"',
        lambda m: f'#include "{io_path if m[1] == "io.cpp" else ref / "ares/n64/rsp" / m[1]}"',
        rsp,
    )
    rsp_path = out / "rsp.cpp"
    rsp_path.write_text(rsp, encoding="utf-8", newline="\n")

    unity_path = out / "n64.cpp"
    unity = unity_path.read_text(encoding="utf-8")
    marker = "#include <n64/rsp/rsp.cpp>"
    assert unity.count(marker) == 1
    unity_path.write_text(unity.replace(marker, f'#include "{rsp_path}"'), encoding="utf-8", newline="\n")
