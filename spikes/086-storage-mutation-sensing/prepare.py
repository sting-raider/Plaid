"""Passive completed storage writes and conservative bulk/lifecycle cuts."""
from pathlib import Path
import hashlib
import re

AUDITS = {
    'ares/n64/memory/lsb/writable.hpp': '52565f0359450110af0836d37540a7fb8f77cb10a6e444286a5b09c14c8fd2f0',
    'ares/n64/memory/memory.hpp': '673de0205f34c3da47095bce162e5706924cb24cddaac3080a2a40e0d444b6eb',
    'ares/n64/rdram/rdram.hpp': '6a77c2fa0bbb320ff6b2855ea6379541a67096bed6b91cc6cd2697584112b1cf',
}


def generate(ref, output):
    ref, output = Path(ref), Path(output)
    for name, expected in AUDITS.items():
        assert hashlib.sha256((ref/name).read_text(encoding="utf-8").encode("utf-8")).hexdigest() == expected, name
    source = (ref/'ares/n64/memory/lsb/writable.hpp').read_text()

    def replace(before, after):
        nonlocal source
        assert source.count(before) == 1, before
        source = source.replace(before, after)

    def append_to_method(start, next_method, callback):
        nonlocal source
        assert source.count(start) == source.count(next_method) == 1
        begin, end = source.index(start), source.index(next_method)
        body = source[begin:end]
        assert body.endswith('  }\n\n')
        source = source[:begin] + body[:-5] + callback + '  }\n\n' + source[end:]

    replace('    memory::free<u8, 64_KiB>(data);',
        '    if(data && plaidMemoryMutationObserver) plaidMemoryMutationObserver(this,4,0,size,0);\n'
        '    memory::free<u8, 64_KiB>(data);')
    append_to_method('  auto fill(', '  auto load(',
        '    if(plaidMemoryMutationObserver) plaidMemoryMutationObserver(this,1,0,size,0);\n')
    append_to_method('  auto load(', '  auto save(',
        '    if(plaidMemoryMutationObserver) plaidMemoryMutationObserver(this,2,0,size,0);\n')
    append_to_method('  auto write(u32 address, u64 value)', '  template<u32 Size>\n  auto readUnaligned(',
        '    if constexpr(Size == Byte || Size == Half || Size == Word) {\n'
        '      const u32 mask = Size == Byte ? maskByte : Size == Half ? maskHalf : maskWord;\n'
        '      const u64 payload = value & (Size == Byte ? 0xffull : Size == Half ? 0xffffull : 0xffffffffull);\n'
        '      if(plaidMemoryMutationObserver) plaidMemoryMutationObserver(this,0,address & mask,Size,payload);\n'
        '    }\n')
    replace('    s(std::span<u8>{data, size});',
        '    s(std::span<u8>{data, size});\n'
        '    if(s.reading() && plaidMemoryMutationObserver) plaidMemoryMutationObserver(this,3,0,size,0);')
    declarations = ('// Original passive storage sensor; kind0 completed scalar,1 fill,2 file load,3 restore,4 retirement.\n'
        'using PlaidMemoryMutationObserver = void (*)(const void*,u32,u32,u32,u64);\n'
        'inline PlaidMemoryMutationObserver plaidMemoryMutationObserver = nullptr;\n')
    destination = output/'include/n64/memory/lsb/writable.hpp'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(declarations+source, encoding='utf-8', newline='\n')
    memory = (ref/'ares/n64/memory/memory.hpp').read_text()
    assert memory.count('#include "lsb/writable.hpp"') == 1
    memory = re.sub(r'#include "([^"]+)"', lambda m:
        f'#include "{destination if m[1] == "lsb/writable.hpp" else ref/"ares/n64/memory"/m[1]}"', memory)
    (output/'include/n64/memory/memory.hpp').write_text(memory, encoding='utf-8', newline='\n')
