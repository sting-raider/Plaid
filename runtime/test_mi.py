"""MI mask commands/readback against the pinned ares device implementation."""
import hashlib
import json
import os
import subprocess
import sys


def run(exe, cc, T):
    sys.path.insert(0, str(T.ROOT / 'scripts'))
    import ares_oracle
    A, out = T.A, T.OUT
    T.build(exe, cc, 'mi-fixture', list(A.DONE), [])
    # Every initial mask, all four per-bit actions, simultaneous commands,
    # unrelated high bits and mirrored addresses.
    commands = [0, 0x555, 0xaaa, 0xfff] + [3 << (2 * bit) for bit in range(6)] + [1 << (2 * bit) for bit in range(6)]
    cases = [(initial, command | (0xfffff000 if n & 1 else 0),
              0x0430000c if n & 2 else 0x043ffffc)
             for initial in range(64) for n, command in enumerate(commands)]
    (out / 'mi-cases.h').write_text('static const u32 cases[][3] = {\n' +
        ',\n'.join('{%du,%du,%du}' % case for case in cases) + '\n};\n')
    source = out / 'mi-contract.c'
    source.write_text('#define main runtime_main\n#include "' + (T.ROOT / 'runtime/plaid_rt.c').as_posix() + '"\n#undef main\n' + r'''
#include <assert.h>
#include "mi-cases.h"
static plaid_state state;
int main(int argc, char **argv) {
  unsigned i, batch = argc > 1 ? (unsigned)atoi(argv[1]) : 0;
  S = &state; S->io = rt_io; S->status_known = 1; S->cp0_status = 0xff03;
  pending[EV_PI] = 1;
  printf("[");
  for(i = batch * 16; i < batch * 16 + 16; i++) {
    u64 v = cases[i][1];
    S->mi_mask = cases[i][0]; mi_mask_known = 63u;
    assert(!plaid_store(S, SX32(cases[i][2] | 0xa0000000u), 4, v, 0x80000100u));
    v = 0xdeadbeefull;
    assert(!plaid_load(S, SX32((cases[i][2] ^ 0x100u) | 0xa0000000u), 4, 0x80000104u, &v));
    assert(S->mi_mask == v && S->cp0_status == 0xff03 && pending[EV_PI] == 1);
    printf("%s%u", i % 16 ? "," : "", (u32)v);
  }
  mi_mask_known = 0; S->mi_mask = 21;
  { u64 v = 19; assert(rt_io(S, 0x0430000c, 4, 0, &v)); assert(v == 19); }
  { u64 v = 3; assert(!rt_io(S, 0x0430000c, 4, 1, &v)); assert(S->mi_mask == 21 && mi_mask_known == 1); }
  { u64 v = 19; assert(rt_io(S, 0x0430000c, 4, 0, &v)); assert(v == 19); }
  { u64 v = 0x555; assert(!rt_io(S, 0x0430000c, 4, 1, &v)); assert(!S->mi_mask && mi_mask_known == 63); }
  S->status_known = 0;
  { u64 v = 19; assert(!rt_io(S, 0x0430000c, 4, 0, &v)); assert(!v); }
  { u64 v = 0xfff; assert(rt_io(S, 0x0430000c, 2, 1, &v)); assert(!S->mi_mask); }
  {
    rt_thread t = {0}; t.guest = 0x80004000; t.status_known = 1; t.status_global = 0x80005000;
    wr32(t.status_global, 0x003fff01); wr32(t.guest + 0x118, 0xff03); wr32(t.guest + 0x128, 63);
    mi_mask_known = 0; restore(&t);
    assert(mi_mask_known == 63 && S->mi_mask == 63);
  }
  printf("]\n"); return 0;
}
''')
    binary = out / ('mi-contract.exe' if os.name == 'nt' else 'mi-contract')
    flags = [cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-function',
             '-Wno-unused-label', '-DPLAID_SAFEPOINTS', '-DPLAID_LOWERED="mi-fixture.c"',
             '-I', str(out), str(source), '-pthread', '-o', str(binary)]
    subprocess.run(flags, check=True)
    oracle = ares_oracle.default()
    metadata = json.loads((oracle.parent / 'build.json').read_text())
    assert metadata['revision'] == A.builder().REV
    def command(mask):
        return sum((2 if mask >> bit & 1 else 1) << (2 * bit) for bit in range(6))
    receipts = []
    for batch in range(len(cases) // 16):
        program = [A.j('body'), A.nop] + [A.nop] * (0x2000 // 4 - 2) + ['body']
        program += T.li(A.gp, 0x80001000)
        for index, (initial, word, address) in enumerate(cases[batch * 16:batch * 16 + 16]):
            program += [*T.poke(0xa430000c, command(initial)), *T.poke(address | 0xa0000000, word),
                        *T.li(A.t0, (address ^ 0x100) | 0xa0000000), A.lw(A.t1, 0, A.t0),
                        A.sw(A.t1, index * 4, A.gp)]
        program += A.DONE
        labels = A.label_pcs(program); pc = A.BASE; words = []
        for item in program:
            if isinstance(item, str): continue
            words.append((item(pc, labels) if callable(item) else item) & 0xffffffff); pc += 4
        raw = out / 'mi-reference.bin'; raw.write_bytes(b''.join(word.to_bytes(4, 'big') for word in words))
        reference = subprocess.run([str(oracle), str(raw), hex(A.EXIT)], capture_output=True, text=True, timeout=60)
        assert not reference.returncode, reference.stderr
        expected = json.loads(reference.stdout)
        actual = subprocess.run([str(binary), str(batch)], capture_output=True, text=True, timeout=30)
        assert not actual.returncode, (actual.stdout, actual.stderr)
        words = json.loads(actual.stdout)
        assert expected['pc'] == A.EXIT and expected['ram'][:16] == words and not any(expected['ram'][16:]), (batch, expected, words)
        receipts.append(words)
    runtime_path = T.ROOT / 'runtime/plaid_rt.c'
    runtime = runtime_path.read_text()
    mutations = [
        ('set', 'if (word & (2u << (2 * i))) s->mi_mask |= 1u << i;', ''),
        ('set-dominates-clear', 'if (word & (2u << (2 * i)))', 'if ((word & (2u << (2 * i))) && !(word & (1u << (2 * i))))'),
        ('known-state', 'if (mi_mask_known != 63u) return 1;', 'if (0) return 1;'),
        ('mirror', 'p < 0x04400000u && (p & 15u) == 12u', 'p < 0x04300010u && (p & 15u) == 12u'),
    ]
    original = source.read_text()
    for name, before, after in mutations:
        assert runtime.count(before) == 1, before
        mutant = out / ('mi-mutant-' + name + '.c'); mutant.write_text(runtime.replace(before, after))
        source.write_text(original.replace(runtime_path.as_posix(), mutant.as_posix()))
        subprocess.run([*flags[:flags.index(str(source))], '-I', str(T.ROOT / 'runtime'), *flags[flags.index(str(source)):]], check=True)
        actual = subprocess.run([str(binary), '0'], capture_output=True, text=True, timeout=30)
        assert actual.returncode or json.loads(actual.stdout) != receipts[0], name
    source.write_text(original)
    (out / 'mi-differential.json').write_text(json.dumps(dict(reference=metadata, runtime_sha256=hashlib.sha256(runtime.encode()).hexdigest(), words=receipts, killed_mutations=[m[0] for m in mutations]), indent=2))
    print('PASS MI mask: 1024 pinned-ares cases, mirrors/high bits, unknown state and unsupported width refusals; four mutations killed')


if __name__ == '__main__':
    import shutil
    from pathlib import Path
    import test_runtime as T
    T.OUT.mkdir(parents=True, exist_ok=True)
    run(Path(os.environ.get('PLAID_TEST_EXE', T.ROOT / 'target/debug/plaid.exe')).resolve(), shutil.which('gcc'), T)
