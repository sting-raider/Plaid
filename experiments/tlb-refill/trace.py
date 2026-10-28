"""Observe a natural mapped fetch and guest refill on the pinned Windows ares.

No ROM/state is injected. The generated driver and byte-bearing output stay in target/.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import ares_oracle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('target', type=lambda v: int(v, 0))
    parser.add_argument('--out', type=Path, default=ROOT / 'target/refill-trace')
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    data = args.rom.read_bytes()
    crc = zlib.crc32(data[0x40:0x1000])
    cic = {0x6170a4a1: '6101', 0x90bb6cb5: '6102', 0x0b050ee0: '6103',
           0x98bc2c86: '6105', 0xacc8580a: '6106'}[crc]
    boot = int.from_bytes(data[8:12], 'big') - {'6103': 0x100000, '6106': 0x200000}.get(cic, 0)
    source = (ROOT / 'scripts/ares_boot.cpp').read_text()
    source = source.replace('../spikes/003-ares-oracle/driver.cpp',
                            (ROOT / 'spikes/003-ares-oracle/driver.cpp').as_posix())
    marker = '    if(cpu.instruction()) cpu.synchronize();'
    assert source.count(marker) == 1
    probe = r'''    static unsigned trace = 0;
    static u64 lastMapping = 0;
    u64 mapping = 0;
    for (auto& e : cpu.tlb.entry) mapping = (mapping * 31) ^ (u64)e.virtualAddress ^ (u64)e.physicalAddress[0] ^ (u64)e.physicalAddress[1] ^ (u64)e.valid[0] ^ ((u64)e.valid[1] << 1);
    if ((u32)cpu.ipu.pc == TARGET || trace) {
      trace++;
      if (trace <= 128 || (u32)cpu.ipu.pc == TARGET || mapping != lastMapping) {
      std::fprintf(result, "{\"tlb_trace\":%u,\"steps\":%llu,\"pc\":%u,\"delay\":%s,\"cp0\":[", trace,
        (unsigned long long)steps, (u32)cpu.ipu.pc, cpu.pipeline.inDelaySlot() ? "true" : "false");
      unsigned regs[] = {0,2,3,4,5,6,8,10,12,13,14,20};
      for (unsigned i=0;i<12;i++) std::fprintf(result,"%s%llu",i?",":"",(unsigned long long)cpu.getControlRegister(regs[i]));
      std::fprintf(result,"],\"gpr\":[");
      for(unsigned i=0;i<32;i++) std::fprintf(result,"%s%llu",i?",":"",(unsigned long long)cpu.ipu.r[i].u64);
      std::fprintf(result,"],\"tlb\":[");
      auto saved = cpu.scc.tlb;
      for(unsigned i=0;i<32;i++) {
        cpu.scc.tlb=cpu.tlb.entry[i];
        std::fprintf(result,"%s[",i?",":"");
        for(unsigned j: {5,10,2,3}) std::fprintf(result,"%s%llu",j==5?"":",",(unsigned long long)cpu.getControlRegister(j));
        std::fprintf(result,"]");
      }
      cpu.scc.tlb=saved;
      std::fprintf(result,"],\"vector\":[");
      for(unsigned i=0;i<0x200;i+=4) std::fprintf(result,"%s%u",i?",":"",(u32)rdram.ram.read<Word>(i,RBusDevice::ARES_DEBUGGER));
      std::fprintf(result,"]}\n"); std::fflush(result);
      }
    }
    lastMapping = mapping;
'''.replace('TARGET', hex(args.target) + 'u')
    source = source.replace(marker, probe + marker)
    driver = args.out / 'driver.cpp'
    driver.write_text(source)
    oracle = ares_oracle.build(driver, args.out / 'oracle', raw_fetch_access=True,
                              physical_fetch_access=True, rdram_burst_access=True,
                              rdram_scalar_access=True, pi_dma_access=True,
                              cpu_instruction_access=True)
    output = args.out / 'trace.jsonl'
    subprocess.run([str(oracle), str(args.rom.resolve()),
                    str(ROOT / '.refs/ares/ares/System/Nintendo 64/pif.ntsc.rom'),
                    hex(boot), hex(args.target), '100000000', 'CIC-NUS-' + cic,
                    str(output), 'exact-many'], check=True, timeout=300,
                   env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    for row in rows:
        if 'tlb_trace' in row:
            print(row['steps'], hex(row['pc']), 'delay', row['delay'],
                  'cp0', [hex(v) for v in row['cp0']])
    print('trace:', output)


if __name__ == '__main__':
    main()
