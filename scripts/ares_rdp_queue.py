"""Oracle build recipe: the pinned ares RDP without its software rasterizer (ADR-0329).

Headless ares has no Vulkan renderer, so `RDP::render` falls back to the
software rasterizer, which reads a command split across two DPC_END writes
past `end`; some microcode then waits forever for DPC_CURRENT to equal END.
This recipe gives `render` the Vulkan path's command accounting instead
(ares n64/vulkan/vulkan.cpp, same pinned revision): consume words up to END,
keep a partial command for the next write, and raise the DP interrupt on
SYNC_FULL. No pixels are drawn, so the RDP writes no framebuffer bytes to
RDRAM; traces that use it compare inputs, not images.
"""
from pathlib import Path


def generate(ref, output):
    """Write output/rdp.cpp (including a patched render.cpp); return its path."""
    rdp = Path(ref) / 'ares/n64/rdp'
    vulkan = (Path(ref) / 'ares/n64/vulkan/vulkan.cpp').read_text()
    start = vulkan.index('  static constexpr u32 commandLength[64] = {')
    lengths = vulkan[start:vulkan.index('};', start) + 2]
    render = (rdp / 'render.cpp').read_text()
    begin = 'auto RDP::render() -> void {\n'
    assert render.count(begin) == 1 and lengths.count(',') == 64
    # The observer sees each frame's command words, hashed as PLAID_TRACE_RDP does natively.
    render = render.replace(begin, '''void (*plaidRdpFrameObserver)(u64 hash, u32 commands, const u32* ops) = nullptr;
void (*plaidRdpCommandObserver)(const u64* words, u32 count) = nullptr;
''' + begin + '{' + lengths + '''
  static u64 hash = 0xcbf29ce484222325ull;
  static u32 count = 0, ops[64] = {};
  static std::vector<u64> pending;
  auto& memory = !command.source ? (Memory::Writable&)rdram.ram : (Memory::Writable&)rsp.dmem;
  while(command.current < command.end) {
    pending.push_back(memory.readUnaligned<Dual>(command.current));
    command.current += 8;
  }
  u32 at = 0;
  while(at < pending.size()) {
    u32 code = pending[at] >> 56 & 63;
    if(at + commandLength[code] > pending.size()) break;  // completed by the next DPC_END
    for(u32 i = 0; i < commandLength[code]; i++) hash = (hash ^ pending[at + i]) * 0x100000001b3ull;
    count++; ops[code]++;
    if(plaidRdpCommandObserver) plaidRdpCommandObserver(&pending[at], commandLength[code]);
    if(code == 0x29) {
      if(plaidRdpFrameObserver) plaidRdpFrameObserver(hash, count, ops);
      hash = 0xcbf29ce484222325ull; count = 0; for(auto& o : ops) o = 0;
      syncFull();
    }
    at += commandLength[code];
  }
  pending.erase(pending.begin(), pending.begin() + at);
  return;
  }
''')
    (Path(output) / 'rdp_render.cpp').write_text(render)
    source = (rdp / 'rdp.cpp').read_text()
    for name in ('render.cpp', 'io.cpp', 'debugger.cpp', 'serialization.cpp'):
        include = f'#include "{name}"'
        assert source.count(include) == 1
        target = Path(output) / 'rdp_render.cpp' if name == 'render.cpp' else rdp / name
        source = source.replace(include, f'#include "{target.as_posix()}"')
    path = Path(output) / 'rdp.cpp'
    path.write_text(source)
    return path
