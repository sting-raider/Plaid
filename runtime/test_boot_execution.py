"""ROM-only CPU-generated text: replay, native identity guard, pinned ares."""
from pathlib import Path
import json
import os
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/boot-execution-contract'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    if not cc:
        raise RuntimeError('boot execution contract requires a C compiler')
    rom = bytearray(0x3000)
    rom[:4] = bytes.fromhex('80371240')
    rom[8:12] = struct.pack('>I', 0x80000400)
    words = [0x3c088000, 0x35080500, 0xad000000,
             0x3c098000, 0x35291400, 0x3c0a8000, 0x354a1000, 0x240b000c,
             0x912c0000, 0x398c0055, 0xa14c0000, 0x25290001,
             0x254a0001, 0x256bffff, 0x1560fff9, 0,
             0x3c198000, 0x37391000, 0x3c028000, 0x34423000, 0x8c420000, 0x03200008, 0x24100007]
    rom[0x1000:0x105c] = struct.pack('>23I', *words)
    text = struct.pack('>3I', 0x2402002a, 0x03e00008, 0)
    rom[0x2000:0x200c] = bytes(b ^ 0x55 for b in text)
    source, loads, m, c = (OUT / n for n in ('input.z64', 'loads.json', 'map.json', 'native.c'))
    source.write_bytes(rom)

    def plaid(*args):
        return subprocess.check_output([str(exe), *map(str, args)], text=True)

    plaid('infer-loads', source, loads)
    doc = json.loads(loads.read_text())
    assert doc['loads'] == [{'destination': '0x80001000', 'size': '0xc', 'rom': '0x0', 'encoding': 'boot'}], doc
    assert 'consumed ROM ranges' in doc['source'] and 'output sha256' in doc['source']
    original = loads.read_bytes()
    plaid('infer-loads', source, loads)
    assert loads.read_bytes() == original
    plaid('discover', source, '0x1000', '0x80000400', '0x100', '0x80000400', m,
          '--loads', loads, '--address-taken')
    verdict = json.loads(plaid('solve', source, m, '--address-taken'))
    assert verdict['status'] == 'closed', verdict['blockers']
    plaid('lower-map', source, m, '0x80000400', '0x80003000', c)
    plaid('lower-map', source, m, '0x80001000', '0x80003000', OUT / 'tamper.c')
    # The oracle starts at RAM 0. Its initial jump enters the same boot stub;
    # both sides load original IPL3 bytes, never the recovered output image.
    raw = bytearray(0x400) + rom[0x1000:]
    raw[:8] = struct.pack('>2I', 0x08000100, 0)
    raw_path = OUT / 'raw.bin'
    raw_path.write_bytes(raw)
    harness = OUT / 'harness.c'
    harness.write_text(r'''
#include <stdio.h>
#ifdef BOOT_TAMPER
#include "tamper.c"
#else
#include "native.c"
#endif
static plaid_state s;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb");
  if (!f || fread(s.ram, 1, sizeof s.ram, f) == 0) return 2;
  fclose(f); s.r[31] = SX32(0x80003000u);
  if (argc > 2) {
    const u8 text[] = {0x24,2,0,42,3,0xe0,0,8,0,0,0,0};
    memcpy(s.ram + 0x1000, text, sizeof text);
    s.ram[0x1000] ^= 1;
    int r = plaid_run(&s);
    return !(r && s.fault == 8 && s.fault_pc == 0x80001000u);
  }
  if (plaid_run(&s) || s.fault) return 3;
  printf("{\"pc\":%u,\"regs\":[", s.pc);
  for (int i=0;i<32;i++) printf("%s%llu", i ? "," : "", (unsigned long long)s.r[i]);
  printf("],\"ram\":[");
  for (int i=0x1000;i<0x1100;i+=4)
    printf("%s%u", i == 0x1000 ? "" : ",", (u32)s.ram[i]<<24 | (u32)s.ram[i+1]<<16 | (u32)s.ram[i+2]<<8 | s.ram[i+3]);
  printf("]}\n"); return 0;
}
''')
    native = OUT / ('check.exe' if os.name == 'nt' else 'check')
    subprocess.run([cc, '-O2', '-std=c11', '-w', str(harness), '-lm', '-o', str(native)], check=True)
    state = json.loads(subprocess.check_output([str(native), str(raw_path)], text=True, timeout=30))
    assert state['pc'] == 0x80003000 and state['regs'][2] == 42 and state['regs'][16] == 7
    assert state['ram'][:3] == [0x2402002a, 0x03e00008, 0]
    tamper = OUT / ('tamper.exe' if os.name == 'nt' else 'tamper')
    subprocess.run([cc, '-O2', '-std=c11', '-w', '-DBOOT_TAMPER', str(harness), '-lm', '-o', str(tamper)], check=True)
    subprocess.run([str(tamper), str(raw_path), 'tamper'], check=True, timeout=30)
    oracle = ROOT / 'target/native-slice/oracle/oracle'
    if os.name == 'nt':
        def linux(path):
            return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(path)], text=True).strip()
        if not oracle.exists():
            subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', linux(ROOT / 'spikes/096-native-slice/run.py'), '--oracle'], check=True)
        command = ['wsl', '-d', 'Ubuntu', '--exec', linux(oracle), linux(raw_path), '0x80003000']
    else:
        if not oracle.exists():
            raise RuntimeError('build pinned oracle with spikes/096-native-slice/run.py --oracle')
        command = [str(oracle), str(raw_path), '0x80003000']
    assert json.loads((oracle.parent / 'build.json').read_text())['revision'] == '9408cb43d4948fc3ea6e152a307a34348df3fe04'
    reference = json.loads(subprocess.check_output(command, text=True, timeout=120))
    assert state == {k: reference[k] for k in state}, (state, reference)
    print('PASS boot-generated text: deterministic replay, CLOSED scope, native state/RAM match pinned ares; tampered text faults 8')


if __name__ == '__main__':
    main()
