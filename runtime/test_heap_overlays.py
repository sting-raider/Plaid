"""Inactive relocated copies may exchange one binding; active native frames pin it."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / 'spikes/096-native-slice'
OUT = ROOT / 'target/heap-overlay-contract'


def main():
    spec = importlib.util.spec_from_file_location('heap_asm', SLICE / 'run.py')
    a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a)
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    for mode in ('move', 'active', 'tamper'):
        extra = [(a.jalr(a.ra, a.a0),), (a.nop,)] if mode == 'active' else []
        words, relocs, text = a.overlay_file(extra)
        # Keep the full first-entry file identity when revisiting the first copy.
        words[5] = words[5] & 0x03ffffff | 35 << 26  # SW -> LW, same LO16 site

        def copy(label, base):
            return [a.lui(a.s6, 0xa000), a.LO(a.s6, a.s6, label),
                    a.lui(a.s7, base >> 16 | 0x2000), a.ori(a.s7, a.s7, base & 0xffff),
                    a.addiu(a.t8, 0, len(words)), label + '_copy',
                    a.lw(a.t1, 0, a.s6), a.sw(a.t1, 0, a.s7),
                    a.addiu(a.s6, a.s6, 4), a.addiu(a.s7, a.s7, 4),
                    a.addiu(a.t8, a.t8, -1), a.bgtz(a.t8, label + '_copy'), a.nop]

        def call(base):
            address = base + text + 4
            return [a.lui(a.t0, (address + 0x8000) >> 16), a.addu(a.t0, a.t0, a.s3),
                    a.lw(a.t9, address & 0xffff, a.t0),
                    a.lui(a.a0, 0x8000), a.LO(a.a0, a.a0, 'callback'), a.jalr(a.ra, a.t9), a.nop]

        items = [a.lui(a.sp, 0x8000), a.ori(a.sp, a.sp, 0x1100),
                 *copy('b1', a.OVL_B1), *copy('b2', a.OVL_B2)]
        if mode == 'tamper':
            items += [a.lui(a.t0, 0xa000), a.sw(0, a.OVL_B2 + 0x10, a.t0)]
        items += [*call(a.OVL_B1), a.addu(a.s0, a.v0, 0),
                  *call(a.OVL_B2), a.addu(a.s1, a.v0, 0),
                  *call(a.OVL_B1), a.addu(a.s2, a.v0, 0),
                  # Observable memory writes as well as relocated PC/register effects.
                  a.lui(a.t0, 0x8000), a.sw(a.s0, 0x1000, a.t0),
                  a.sw(a.s1, 0x1004, a.t0), a.sw(a.s2, 0x1008, a.t0),
                  *a.DONE, 'pad', a.jr(a.ra), a.nop, 'callback', a.addiu(a.sp, a.sp, -16), a.sw(a.ra, 12, a.sp),
                  *call(a.OVL_B2), a.lw(a.ra, 12, a.sp), a.jr(a.ra), a.addiu(a.sp, a.sp, 16),
                  'ovl_link', *words, 'b1', *a.relocate(words, relocs, text, a.OVL_B1),
                  'b2', *a.relocate(words, relocs, text, a.OVL_B2)]
        raw = a.assemble(items)
        labels = a.label_pcs(items)
        source, loads, c = (OUT / (mode + ext) for ext in ('.bin', '.loads.json', '.c'))
        source.write_bytes(raw)
        loads.write_text(json.dumps({'format': 'plaid-loads-v0', 'source': 'synthetic heap copies',
                                     'loads': [{'destination': hex(a.OVL_LINK), 'size': hex(len(words)*4),
                                                'rom': hex(labels['ovl_link']-a.BASE),
                                                'encoding': 'raw', 'relocatable': True}]}))
        subprocess.run([str(exe), 'lower-c', str(source), hex(a.BASE), hex(a.BASE), hex(a.EXIT),
                        str(c), '--loads', str(loads), '--address-taken'], check=True, capture_output=True)
        harness = OUT / (mode + '-harness.c')
        # Run the ordinary state/checkpoint harness, then inspect binding invariants.
        harness.write_text('#define main slice_main\n#include "' + (SLICE/'harness.c').as_posix() +
                           '"\n#undef main\n#include <assert.h>\nint main(void) { int r;\n' +
                           'r = slice_main(); assert(s.ovl_active[0] == 0);\n' +
                           ('assert(r == 0 && s.ovl_delta[0] == 0xffa03000u);\n'
                            'assert(s.prot[0x3000u >> 2] == 255 && s.prot[0x7fc0u >> 2] == 0);\n'
                            's.prot[0x7fc4u >> 2] = 1; assert(plaid_link(&s, 0x80007fc0u) == 1);\n'
                            'assert(s.ovl_ok[0] && s.ovl_delta[0] == 0xffa03000u && s.prot[0x3000u >> 2] == 255);\n'
                            's.prot[0x7fc4u >> 2] = 0;\n'
                            'assert(plaid_runtime_write(&s, 0x3000u, 4, 0) == 0 && !s.ovl_ok[0]);\n'
                            'assert(s.prot[0x3000u >> 2] == 0);\n' if mode == 'move' else
                            'assert(r == 6 && s.fault == 3);\n') + 'return r; }\n')
        native = OUT / (mode + ('.exe' if os.name == 'nt' else ''))
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                        f'-DPLAID_LOWERED="{c.name}"', f'-DPLAID_EXIT={hex(a.EXIT)}u', '-I', str(OUT),
                        str(harness), '-lm', '-o', str(native)], check=True)
        run = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
        assert run.stdout, (mode, run.returncode, run.stderr)
        state = json.loads(run.stdout)
        if mode == 'move':
            assert run.returncode == 0 and state['regs'][16:19] == [42]*3, (mode, run.returncode, state, run.stderr)
            oracle = ROOT / 'target/native-slice/oracle/oracle'
            if os.name == 'nt':
                def linux(path):
                    return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(path)], text=True).strip()
                reference = ['wsl', '-d', 'Ubuntu', '--exec', linux(oracle), linux(source), hex(a.EXIT)]
            else:
                reference = [str(oracle), str(source), hex(a.EXIT)]
            built = json.loads((oracle.parent/'build.json').read_text())
            assert built['revision'] == a.builder().REV
            ref = subprocess.run(reference, capture_output=True, text=True, timeout=120)
            assert ref.returncode == 0 and state == json.loads(ref.stdout), (state, ref.stdout, ref.stderr)
        else:
            assert run.returncode == 6 and state['fault'] == 3, (mode, run.returncode, state, run.stderr)
    print('PASS heap overlays: three inactive copy switches match pinned ares; active-frame, tampered and protected targets fault; pins unwind and runtime writes revoke')


if __name__ == '__main__':
    main()
