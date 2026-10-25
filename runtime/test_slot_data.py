"""Data before/between slot functions stays mutable; emitted code stays guarded."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess

from test_tlb_execution import _ares_run

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/slot-data-contract'
SLOT = 0x80004000


def main():
    spec = importlib.util.spec_from_file_location('slot_data_asm', ROOT / 'spikes/096-native-slice/run.py')
    a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a)
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    # The invalid data prefix forces the raw slot's full-file candidate extent.
    # Two separately called functions have a mutable gap between their bodies.
    payload = [0x7677696e, 0, 0, 0,
               a.lui(a.t0, 0x8000), a.ori(a.t0, a.t0, SLOT & 0xffff),
               a.addiu(a.v0, 0, 65), a.I(40, a.v0, a.t0, 1),
               a.I(40, a.v0, a.t0, 45), a.jr(a.ra), a.nop,
               0x7677696e,
               a.lui(a.t0, 0x8000), a.ori(a.t0, a.t0, SLOT & 0xffff),
               a.lw(a.t9, 76, a.t0), a.jr(a.t9), a.nop,
               0, 0, SLOT + 80, a.addiu(a.v0, 0, 99), a.jr(a.ra), a.nop, 0]
    items = [a.lui(a.s0, 0xa000), a.LO(a.s0, a.s0, 'payload'),
             a.lui(a.s1, 0xa000), a.ori(a.s1, a.s1, SLOT & 0xffff),
             a.addiu(a.s2, 0, len(payload)), 'copy',
             a.lw(a.t1, 0, a.s0), a.sw(a.t1, 0, a.s1),
             a.addiu(a.s0, a.s0, 4), a.addiu(a.s1, a.s1, 4),
             a.addiu(a.s2, a.s2, -1), a.bgtz(a.s2, 'copy'), a.nop,
             a.lui(a.a0, 0x8000), a.ori(a.a0, a.a0, SLOT & 0xffff),
             a.jal('icache'), a.nop,
             3 << 26 | ((SLOT + 16) >> 2 & 0x3ffffff), a.nop,
             a.addu(a.s3, a.v0, 0),
             3 << 26 | ((SLOT + 48) >> 2 & 0x3ffffff), a.nop,
             # Retire and reuse an idle overlay's proof bytes. Restoration is
             # required before the same tail transfer can bind again.
             a.lui(a.t0, 0x8000), a.ori(a.t0, a.t0, SLOT & 0xffff),
             a.addiu(a.t1, 0, 123), a.sw(a.t1, 76, a.t0), a.lw(a.s6, 76, a.t0),
             a.lui(a.t1, 0x8000), a.ori(a.t1, a.t1, (SLOT + 80) & 0xffff), a.sw(a.t1, 76, a.t0),
             3 << 26 | ((SLOT + 48) >> 2 & 0x3ffffff), a.nop,
             a.lui(a.t0, 0x8000), a.ori(a.t0, a.t0, SLOT & 0xffff),
             a.lw(a.s4, 0, a.t0), a.lw(a.s5, 44, a.t0), *a.DONE,
             'icache', a.jr(a.ra), a.nop, 'payload', *payload]
    raw = a.assemble(items)
    labels = a.label_pcs(items)
    rom = bytearray(0x1000)
    rom[:4] = bytes.fromhex('80371240')
    rom.extend(raw)
    source, loads, runtime, program_map, c = (OUT / ('data' + suffix) for suffix in
                                             ('.z64', '.loads.json', '.runtime.json', '.map.json', '.c'))
    source.write_bytes(rom)
    loads.write_text(json.dumps({'format': 'plaid-loads-v0', 'source': 'synthetic data-first slot',
                                'loads': [{'destination': hex(SLOT), 'size': hex(len(payload) * 4),
                                           'rom': hex(0x1000 + labels['payload'] - a.BASE),
                                           'encoding': 'raw', 'slot': True}]}))
    runtime.write_text(json.dumps({'format': 'plaid-runtime-functions-v0', 'source': 'synthetic cache boundary',
                                  'functions': [{'entry': hex(labels['icache']), 'name': 'icache', 'callbacks': []}]}))
    subprocess.run([str(exe), 'discover', str(source), '0x1000', hex(a.BASE), hex(len(raw)),
                    hex(a.BASE), str(program_map), str(runtime), '--loads', str(loads), '--address-taken'],
                   check=True, capture_output=True)
    subprocess.run([str(exe), 'lower-map', str(source), str(program_map), hex(a.BASE), hex(a.EXIT), str(c)],
                   check=True, capture_output=True)
    with c.open('a') as f:
        f.write('\nint plaid_rt_icache(plaid_state *s) { (void)s; return 0; }\n')
    harness = OUT / 'check.c'
    harness.write_text('#define main slice_main\n#include "' +
                       (ROOT / 'spikes/096-native-slice/harness.c').as_posix() +
                       '"\n#undef main\n#include <assert.h>\n' + r'''
int main(void) {
  u8 original; u32 mapped;
  assert(slice_main() == 0 && !s.native_frames);
  assert(s.r[19] == 65 && s.r[20] == 0x7641696eu && s.r[21] == 0x7641696eu);
  assert(s.ovl_ok[0] && !s.fault);
  /* Idle proof writes revoke; altered proof inputs must prevent reentry. */
  assert(s.r[22] == 123);
  mapped = plaid_link(&s, 0x80004030u);
  assert(plaid_runtime_write(&s, 0x404c, 1, 0) == 0 && !s.ovl_ok[0]);
  s.ram[0x404c] = 0;
  assert(plaid_link(&s, 0x80004030u) != mapped && !s.ovl_ok[0]);
  s.ram[0x404c] = 0x80;
  assert(plaid_link(&s, 0x80004030u) == mapped && s.ovl_ok[0]);
  /* Mutations before first entry and after a revocation must also bind. */
  assert(plaid_runtime_write(&s, 0x4001, 1, 0) == 0 && s.ovl_ok[0]);
  s.ram[0x4001] = 66;
  mapped = plaid_link(&s, 0x80004010u);
  original = s.ram[0x4010];
  assert(plaid_runtime_write(&s, 0x4010, 1, 0) == 0 && !s.ovl_ok[0]);
  s.ram[0x4010] ^= 1;
  assert(plaid_link(&s, 0x80004010u) != mapped && !s.ovl_ok[0]); /* changed instruction refuses */
  s.ram[0x4010] = original;
  assert(plaid_link(&s, 0x80004010u) != 1 && s.ovl_ok[0]);
  /* All bound code remains immutable while any overlay frame can resume. */
  { plaid_native_frame frame = {0,0,0,0,0,0,0};
    plaid_text_pin(&s, &frame);
    assert(plaid_store(&s, SX32(0x80004001u), 1, 67, 0) == 0);
    assert(plaid_runtime_write(&s, 0x4010, 1, 0) == 1 && s.fault == 2);
    assert(s.ram[0x4010] == original && s.ovl_ok[0]);
    s.fault = 0;
    assert(plaid_runtime_write(&s, 0x404c, 1, 0) == 1 && s.fault == 2);
    assert(s.ram[0x404c] == 0x80 && s.ovl_ok[0]);
    plaid_text_unpin(&s, &frame); s.fault = 0;
  }
  return 0;
}
''')
    binary = OUT / ('check.exe' if os.name == 'nt' else 'check')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                    '-DPLAID_LOWERED="data.c"', f'-DPLAID_EXIT={hex(a.EXIT)}u', '-I', str(OUT),
                    str(harness), '-lm', '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    state = json.loads(result.stdout)
    raw_path = OUT / 'data.bin'
    raw_path.write_bytes(raw)
    reference = _ares_run(raw_path)
    assert reference.returncode == 0 and state == json.loads(reference.stdout), (state, reference.stdout, reference.stderr)
    # Remove one active-frame guard in a private generated unit: the negative
    # must fail, so passing data writes cannot conceal weakened text protection.
    original = c.read_text()
    guard = 'if (s->ovl_active[k] || pc - plaid_ovls[k].link < plaid_ovls[k].text) return 1;'
    assert original.count(guard) == 1
    try:
        c.write_text(original.replace(guard, '/* mutation: omit active-frame guard */'))
        subprocess.run([cc, '-O2', '-std=c11', '-w', '-DPLAID_LOWERED="data.c"',
                        f'-DPLAID_EXIT={hex(a.EXIT)}u', '-I', str(OUT), str(harness), '-lm',
                        '-o', str(binary)], check=True)
        mutated = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        assert mutated.returncode != 0 and 'Assertion' in mutated.stderr, mutated
    finally:
        c.write_text(original)
    print('PASS slot data: prefix/inter-function byte writes and full CPU state match pinned ares; '
          'changed text/proof refuses, restored inputs rebind, active code/proof stay protected; '
          'active-frame guard mutation killed')


if __name__ == '__main__':
    main()

