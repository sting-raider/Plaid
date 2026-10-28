"""Fixed and mapped native code share bytes without losing either owner."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import test_tlb_execution as T

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/mapped-alias-contract'


def ownership_units(cc, prefix, source, one):
    """Isolate the runtime protocol with explicit synthetic protection metadata.

    The CPU/oracle program below uses the compiler-produced raw-load metadata.
    These variants supply base-text, immutable-data and mixed owners directly;
    they do not claim that the oracle program derived those proof classes.
    """
    row = f'{{{T.P0}, {T.P0 + 12}, 0}}'
    tags = f'{{{T.P0}u,{T.P0 + 12}u,2u}}'
    assert source.count(row) == source.count(tags) == 1
    for owner in ('text', 'proof', 'mixed'):
        changed = source.replace(row, f'{{{T.P0}, {T.P0 + 12}, {-1 if owner == "text" else -2}}}')
        changed = changed.replace(tags, f'{{{T.P0}u,{T.P0 + 12}u,{1 if owner == "text" else 253}u}}')
        if owner == 'mixed':
            changed = source.replace(row, f'{{{T.P0}, {T.P0 + 4}, 0}}, {{{T.P0 + 4}, {T.P0 + 12}, -2}}')
            changed = changed.replace(tags, f'{{{T.P0}u,{T.P0 + 4}u,2u}},{{{T.P0 + 4}u,{T.P0 + 12}u,253u}}')
            changed, count = re.subn(r'(u8 plaid_base_prot\(u32 p\) \{\n  u32 lo = 0, hi = )(\d+)u;',
                                    lambda m: m[1] + str(int(m[2]) + 1) + 'u;', changed)
            assert count == 1
        filename = f'native-{owner}.c'
        (OUT / filename).write_text(changed)
        body = f'''int main(void) {{
  static plaid_state s, before; plaid_load_images(&s); plaid_build_prot(&s);
  memcpy(s.ram + 0x{T.P0:x}u, raw0, sizeof raw0);
  for(u32 w=0;w<PLAID_RAM_SIZE/4;w++) assert(plaid_base_prot(w<<2)==s.prot[w]);
  plaid_tlb_entry entry = {{0,0x{T.E0:x}u,{{{T.P0 >> 6 | 31}u,{(T.P0 + 0x1000) >> 6 | 31}u}}}};
  assert(!plaid_tlb_write(&s,0,entry,0x{T.PC:x}u));
  s.prot[0x{T.P0:x}u>>2]=252; before=s;
  assert(plaid_link(&s,0x{T.E0:x}u)==1 && !memcmp(&before,&s,sizeof s));
  s.prot[0x{T.P0:x}u>>2]=plaid_base_prot(0x{T.P0:x}u);
  assert(plaid_link(&s,0x{T.E0:x}u)!=1);
  int k=find_tlb(&s,0); assert(k>=0 && s.prot[0x{T.P0:x}u>>2]==255);
  #define REFUSE(expr) do {{ before=s; assert(expr); assert(s.fault==2); s.fault=before.fault; s.fault_pc=before.fault_pc; assert(!memcmp(&before,&s,sizeof s)); }} while(0)
'''
        if owner == 'text':
            body += f'''  const u32 words[]={{{','.join(hex(w) + 'u' for w in one)}}};
  u32 different[3]; memcpy(different,words,sizeof different); different[2]^=1;
  before=s; assert(plaid_text_enter(&s,0x{T.P0:x}u,different,3,0x{T.PC:x}u) && s.fault==8);
  s.fault=before.fault;s.fault_pc=before.fault_pc;assert(!memcmp(&before,&s,sizeof s));
  assert(!plaid_text_enter(&s,0x{T.P0:x}u,words,3,0x{T.PC:x}u) && s.prot[0x{T.P0:x}u>>2]==255);
  const plaid_text_range ranges[]={{{{0x{T.P0:x}u,0x{T.P0 + 12:x}u}}}};
  plaid_native_frame frame={{0}};frame.overlay=-1;frame.ranges=ranges;frame.count=1;
  plaid_text_pin(&s,&frame);
  REFUSE(plaid_runtime_write(&s,0x{T.P0:x}u,4,0x{T.PC:x}u));plaid_text_unpin(&s,&frame);
  assert(!plaid_runtime_write(&s,0x{T.P0:x}u,4,0x{T.PC:x}u));
  assert(!s.ovl_ok[k] && s.prot[0x{T.P0:x}u>>2]==254 && s.text_dirty);
  s.ram[0x{T.P0:x}u]^=1;assert(plaid_link(&s,0x{T.E0:x}u)==1);
  before=s;assert(plaid_text_enter(&s,0x{T.P0:x}u,words,3,0x{T.PC:x}u) && s.fault==8);
  s.fault=before.fault;s.fault_pc=before.fault_pc;assert(!memcmp(&before,&s,sizeof s));
'''
        else:
            width = 8 if owner == 'mixed' else 4
            body += f'''  s.load_ok[0]=1;
  REFUSE(plaid_runtime_write(&s,0x{T.P0:x}u,{width},0x{T.PC:x}u));
  assert(!plaid_tlb_write(&s,0,entry,0x{T.PC:x}u) && !s.ovl_ok[k]);
  assert(s.prot[0x{T.P0:x}u>>2]=={2 if owner == 'mixed' else 253});
  assert(s.prot[0x{T.P0 + 4:x}u>>2]==253);
  REFUSE(plaid_runtime_write(&s,0x{T.P0:x}u,{width},0x{T.PC:x}u));
'''
        body += '  return 0;\n}\n'
        harness = OUT / f'ownership-{owner}.c'
        harness.write_text(prefix.replace('"native.c"', f'"{filename}"') + body)
        binary = OUT / f'ownership-{owner}.exe'
        flags = [cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                 '-Wno-unused-const-variable', '-I', str(OUT), str(harness), '-o', str(binary)]
        subprocess.run(flags, check=True)
        subprocess.run([str(binary)], check=True, capture_output=True, timeout=30)
        if owner == 'mixed':
            at = changed.index('/* Preflight the complete transaction')
            first = changed.index('  for (w = p >> 2;', at)
            second = changed.index('  for (w = p >> 2;', first + 1)
            try:
                (OUT / filename).write_text(changed[:first] + changed[second:])
                subprocess.run(flags, check=True)
                mutant = subprocess.run([str(binary)], capture_output=True, timeout=30)
                assert mutant.returncode != 0, 'removed transaction preflight escaped mixed-owner refusal'
                (OUT / 'removed-preflight.stderr').write_bytes(mutant.stderr)
            finally:
                (OUT / filename).write_text(changed)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('mapped_alias_asm', T.SLICE / 'run.py')
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    original = T._module_words, A.assemble, A.label_pcs
    try:
        T._module_words = lambda A: ([A.addiu(A.v0, A.v0, 7), A.jr(A.ra), A.addiu(A.v0, A.v0, 3)],
                                     [A.jr(A.ra), A.nop])
        def rewrite(items):
            result = []
            marker = A.jalr(A.ra, A.t9)
            fixed_call = 3 << 26 | ((0x80000000 | T.P0) >> 2 & 0x03ffffff)
            for index, word in enumerate(items):
                result.append(word)
                if (index and items[index - 1] == marker and
                        (index + 1 == len(items) or items[index + 1] != fixed_call)):
                    result += [fixed_call, A.nop]
            return result
        A.assemble = lambda items: original[1](rewrite(items))
        A.label_pcs = lambda items: original[2](rewrite(items))
        raw, labels, one, two = T._fixture(A)
        offset = labels['module0'] - T.BASE
        assert raw[offset:offset + len(one) * 4] == b''.join(w.to_bytes(4, 'big') for w in one)
    finally:
        T._module_words, A.assemble, A.label_pcs = original
    program = OUT / 'program.bin'
    program.write_bytes(raw)
    rom = bytearray(0x1000)
    rom[:4] = bytes.fromhex('80371240')
    rom.extend(raw)
    source = OUT / 'input.z64'
    source.write_bytes(rom)
    loads = OUT / 'loads.json'
    loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='synthetic fixed/mapped physical alias', loads=[
        dict(destination=hex(0x80000000 | T.P0), size=hex(len(one) * 4),
             rom=hex(0x1000 + labels['module0'] - T.BASE), encoding='raw'),
        *[dict(destination=hex(v), size=hex(len(words) * 4),
               rom=hex(0x1000 + labels[label] - T.BASE), encoding='tlb_raw', slot=True,
               text_size=hex(len(words) * 4))
          for v, words, label in [(T.E0, one, 'module0'), (T.E1, two, 'module1')]]])))
    runtime = OUT / 'runtime.json'
    runtime.write_text(json.dumps(dict(format='plaid-runtime-functions-v0', source='synthetic TLB ABI',
        functions=[dict(entry=hex(labels['map']), name='map', callbacks=[])])))
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    mapping, native = OUT / 'map.json', OUT / 'native.c'
    for args in [('discover', source, '0x1000', hex(T.BASE), hex(len(raw)), hex(T.BASE), mapping,
                  runtime, '--loads', loads, '--address-taken'),
                 ('lower-map', source, mapping, hex(T.BASE), hex(T.EXIT), native, '--residual-dispatch')]:
        p = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True)
        assert p.returncode == 0, (p.stdout, p.stderr)
    harness = T._native_harness(one, two, labels)
    prefix = harness.split('int main(void)')[0]
    serializer = harness[harness.index('  printf("{'):harness.index('  /* Inactive remap')]
    post = f'''  {{
    int k = find_tlb(&s, 0); static plaid_state before;
    assert(k >= 0 && s.prot[0x{T.P0:x}u >> 2] == 255 && s.load_ok[0]);
    #define REFUSE(expr) do {{ before = s; assert(expr); assert(s.fault == 2); s.fault = before.fault; s.fault_pc = before.fault_pc; assert(!memcmp(&before, &s, sizeof s)); }} while (0)
    s.ovl_active[k] = 1;
    REFUSE(plaid_runtime_write(&s, 0x{T.P0:x}u, 4, 0x{T.PC:x}u));
    s.ovl_active[k] = 0;
    const plaid_text_range ranges[] = {{{{0x{T.P0:x}u, 0x{T.P0 + 12:x}u}}}};
    plaid_native_frame frame = {{0}}; frame.overlay = -1; frame.ranges = ranges; frame.count = 1;
    plaid_text_pin(&s, &frame);
    REFUSE(plaid_runtime_write(&s, 0x{T.P0:x}u, 4, 0x{T.PC:x}u));
    plaid_text_unpin(&s, &frame);
    assert(!plaid_runtime_write(&s, 0x{T.P0:x}u, 4, 0x{T.PC:x}u));
    assert(!s.ovl_ok[k] && s.prot[0x{T.P0:x}u >> 2] == 2 && !s.load_ok[0]);
    s.ram[0x{T.P0:x}u] ^= 1;
    assert(plaid_link(&s, 0x{T.E0:x}u) == 1);
    before = s;
    assert(plaid_verify_load(&s, 0, 0x{T.PC:x}u) && s.fault == 8);
    s.fault = before.fault; s.fault_pc = before.fault_pc;
    assert(!memcmp(&before, &s, sizeof s));
  }}
'''
    (OUT / 'harness.c').write_text(prefix + f'''int main(void) {{
  static plaid_state s; plaid_load_images(&s); plaid_build_prot(&s);
  for(u32 w=0; w<PLAID_RAM_SIZE/4; w++) assert(plaid_base_prot(w<<2) == s.prot[w]);
  s.r[31] = SX32(0x{T.EXIT:x}u);
  int result = plaid_run(&s); if(result) {{ printf("fault=%u pc=%x\\n",s.fault,s.fault_pc); return 6; }}
{serializer}
{post}
  return 0;
}}
''')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    binary = OUT / ('check.exe' if os.name == 'nt' else 'check')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                    '-Wno-unused-const-variable', '-I', str(OUT), str(OUT / 'harness.c'), '-o', str(binary)], check=True)
    actual = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                            env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
    expected = T._ares_run(program)
    assert actual.returncode == expected.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
    assert json.loads(actual.stdout) == json.loads(expected.stdout), (actual.stdout, expected.stdout)
    (OUT / 'state.json').write_text(actual.stdout)
    text = native.read_text()
    guard = 'if (!plaid_ovls[k].verify(s->ram, PLAID_RAM_SIZE, b)) continue;'
    assert text.count(guard) == 1
    try:
        native.write_text(text.replace(guard, '/* removed source guard mutation */'))
        mutant = OUT / 'removed-source-guard.exe'
        subprocess.run([cc, '-O2', '-std=c11', '-w', '-I', str(OUT), str(OUT / 'harness.c'), '-o', str(mutant)], check=True)
        changed = subprocess.run([str(mutant)], capture_output=True, timeout=30)
        assert changed.returncode != 0, 'unverified fixed/mapped alias escaped corruption refusal'
        (OUT / 'removed-source-guard.stderr').write_bytes(changed.stderr)
    finally:
        native.write_text(text)
    ownership_units(cc, prefix, text, one)
    print('PASS fixed/mapped alias: full-state ares match, exact base tags, both frame owners pin, inactive revocation restores fixed witness, corrupt bytes refuse both entries')


if __name__ == '__main__':
    main()
