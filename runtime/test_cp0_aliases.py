"""A host effect proof may cross a fragment only through a pinned physical alias."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from test_cop0 import A, ares_oracle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/cp0-alias-contract'
EXIT = 0x80003f00


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc')
    cp = lambda sub, rt, rd: 16 << 26 | sub << 21 | rt << 16 | rd << 11
    li = lambda r, v: [A.lui(r, v >> 16 & 0xffff), A.ori(r, r, v & 0xffff)]
    write = lambda rd, value: [*li(A.k0, value), cp(4, A.k0, rd)]
    items = [*write(4, 0x12300000), *write(20, 0), *write(6, 7),
             *write(0, 0), *write(5, 0x6000), A.beq(A.s0,0,'mask_ready'),A.nop,*write(5,0),'mask_ready',
             *write(10, 0x60000000), *write(2, 0x1f), *write(3, 0x11f), 0x42000002,
             *write(0,1),*write(5,0),*write(10,0x60002000),*write(2,0x9f),*write(3,0xdf),0x42000002,
             *li(A.t9, 0x60000200), A.jalr(A.ra, A.t9), A.nop,
             cp(1, A.a1, 4), cp(0, A.a2, 6), cp(1, A.a3, 20), *A.DONE]
    items += [A.nop] * ((0x200 - sum(not isinstance(word,str) for word in items) * 4) // 4)
    body = [A.addu(A.t8, A.ra, 0), A.jal('helper'), A.nop, A.addu(A.ra, A.t8, 0), A.jr(A.ra), A.nop]
    items += ['host', *body]
    items += [A.nop] * ((0x2240 - (0x200 + len(body) * 4)) // 4)
    items += ['helper', A.addiu(A.v0, 0, 42), A.jr(A.ra), A.nop]
    previous_exit = A.EXIT
    try:
        A.EXIT = EXIT
        raw = A.assemble(items)
    finally:
        A.EXIT = previous_exit
    (OUT / 'program.bin').write_bytes(raw)
    rom = OUT / 'input.z64'
    rom.write_bytes(bytes.fromhex('80371240') + bytes(0xffc) + raw)
    loads = OUT / 'loads.json'
    loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='original synthetic physical alias', loads=[
        dict(destination='0x60000200', size='0x18', text_size='0x18', rom='0x1200', encoding='tlb_raw', slot=True)])))
    runtime = OUT / 'runtime.json'
    runtime.write_text(json.dumps(dict(format='plaid-runtime-functions-v0', source='original synthetic ABI', functions=[
        dict(entry=hex(pc), name='host', size=24, callbacks=[]) for pc in (0x80000200, 0x80800200)])))
    mapping = OUT / 'map.json'
    subprocess.run([str(exe), 'discover', str(rom), '0x1000', hex(A.BASE), hex(len(raw)), hex(A.BASE), str(mapping),
                    str(runtime), '--loads', str(loads), '--address-taken'], check=True)
    subprocess.run([str(exe), 'lower-map', str(rom), str(mapping), hex(A.BASE), hex(EXIT), str(OUT / 'native.c'), '--parts', '3'], check=True)
    source = (ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
    source = source.replace('cpu.context.setMode();', 'cpu.setControlRegister(12,0x24000000); cpu.setControlRegister(4,0); cpu.setControlRegister(20,0); cpu.context.setMode();')
    source = source.replace('  std::printf("]}\\n");', '''  std::printf("],\\"globals\\":[%llu,%llu,%llu]}\\n",
    (unsigned long long)cpu.getControlRegister(4),(unsigned long long)cpu.getControlRegister(6),(unsigned long long)cpu.getControlRegister(20));''')
    (OUT / 'driver.cpp').write_text(source)
    oracle = ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')
    native = (ROOT / 'spikes/096-native-slice/harness.c').read_text()
    native = native.replace('#include "runtime.c"', '#include <assert.h>\n#include <stdlib.h>')
    native = native.replace('int main(void) {', '''static int damage,calls;
int plaid_rt_host(plaid_state *p) {
  calls++; if(damage==2 && plaid_runtime_write(p,0x2240,4,0x80000000u)) return 1;
  p->r[24]=p->r[31]; p->r[2]=42; return 0;
}
int main(int argc,char **argv) { damage=argc>1?atoi(argv[1]):0;''')
    native = native.replace('  s.r[31] =', '''  s.status_known=1; s.cp0_status=0x24000000; s.fr_mode=2;
  s.cp0_readonly_known=(1u<<4)|(1u<<20);
  if(damage==1) s.ram[0x2240]^=1;
  if(damage==3) s.r[16]=1;
  s.r[31] =''')
    native = native.replace('  printf("]}\\n");', '''  printf("],\\"globals\\":[%llu,%u,%llu]}\\n",
    (unsigned long long)s.cp0_context,s.cp0_wired,(unsigned long long)s.cp0_xcontext);''')
    (OUT / 'harness.c').write_text(native)
    binary = OUT / 'check.exe'
    command = [cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
               '-Wno-unused-const-variable', '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={EXIT}u',
               '-I', str(OUT), str(OUT / 'harness.c'), '-lm', '-o', str(binary)]
    objects=[]
    for part in sorted(OUT.glob('native.part*.c')):
        obj=part.with_suffix('.o')
        subprocess.run([cc,'-O2','-std=c11','-Wno-unused-function','-c',str(part),'-o',str(obj)],check=True)
        objects.append(str(obj))
    link_at=command.index('-lm')
    command[link_at:link_at]=objects
    subprocess.run(command, check=True)
    expected = json.loads(ares_oracle.execute(oracle, OUT / 'program.bin', hex(EXIT), capture_output=True, text=True, check=True, timeout=30).stdout)
    actual = json.loads(subprocess.check_output([str(binary)], text=True, timeout=30))
    assert actual == expected, {k: (actual[k], expected[k]) for k in expected if actual[k] != expected[k]}
    for damage, fault in ((1, 8), (2, 2), (3,12)):
        bad = subprocess.run([str(binary), str(damage)], capture_output=True, text=True, timeout=30)
        assert bad.returncode and json.loads(bad.stdout)['fault'] == fault, bad.stdout
    generated = (OUT / 'native.c').read_text()
    guard = 'if (((u32)s->ram[q] << 24'
    assert guard in generated
    (OUT / 'native.c').write_text(generated.replace(guard, 'if (0 && ((u32)s->ram[q] << 24'))
    subprocess.run(command, check=True)
    mutant = subprocess.run([str(binary), '1'], capture_output=True, text=True, timeout=30)
    assert mutant.returncode == 0 and json.loads(mutant.stdout) == expected, 'transitive alias source mutation survived'
    mapping_guard='|| index + 1 != tlb'
    assert mapping_guard in generated
    (OUT / 'native.c').write_text(generated.replace(mapping_guard,'|| 0'))
    subprocess.run(command,check=True)
    mutant=subprocess.run([str(binary),'3'],capture_output=True,text=True,timeout=30)
    assert mutant.returncode==0,'transitive alias mapping-owner mutation survived'
    (OUT / 'native.c').write_text(generated)
    print('PASS CP0 physical aliases: transitive native/reference state, dependency corruption, active dependency writes; source-guard mutation killed')


if __name__ == '__main__':
    main()
