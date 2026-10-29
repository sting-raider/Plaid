"""Global CP0 facts require complete, unchanged host-boundary source witnesses."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from test_cop0 import A, ares_oracle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/cp0-boundary-contract'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc')
    cp = lambda sub, rt, rd: 16 << 26 | sub << 21 | rt << 16 | rd << 11
    host = [A.addiu(A.v0, 0, 42), A.jr(A.ra), A.nop]
    prefix = [A.lui(A.t0, 0x1230), cp(4, A.t0, 4), A.addiu(A.t0, 0, 2),
              A.dsll32(A.t0, A.t0, 0), cp(5, A.t0, 20), A.addiu(A.t0, 0, 7), cp(4, A.t0, 6),
              A.jal('host'), A.nop, cp(1, A.a1, 4), cp(0, A.a2, 6), cp(1, A.a3, 20), *A.DONE]
    raw = OUT / 'program.bin'
    runtime = OUT / 'runtime.json'
    labels = A.label_pcs([*prefix, 'host', *host])
    host_pc = labels['host']
    declaration = dict(format='plaid-runtime-functions-v0', source='original synthetic host implementation',
                       functions=[dict(entry=hex(host_pc), name='host', size=12, callbacks=[])])
    runtime.write_text(json.dumps(declaration))
    source = (ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
    source = source.replace('cpu.context.setMode();', 'cpu.setControlRegister(12,0x24000000); cpu.setControlRegister(4,0); cpu.setControlRegister(20,0); cpu.context.setMode();')
    source = source.replace('  std::printf("]}\\n");', '''  std::printf("],\\"global_cp0\\":[%llu,%llu,%llu]}\\n",
    (unsigned long long)cpu.getControlRegister(4),(unsigned long long)cpu.getControlRegister(6),(unsigned long long)cpu.getControlRegister(20));''')
    (OUT / 'driver.cpp').write_text(source)
    oracle = ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')
    native = (ROOT / 'spikes/096-native-slice/harness.c').read_text()
    native = native.replace('#include "runtime.c"', '#include <assert.h>\n#include <stdlib.h>')
    native = native.replace('int main(void) {', '''static int damage,calls;
int plaid_rt_host(plaid_state *p) {
  calls++;
  if (damage==2 && plaid_runtime_write(p,HOST_PC&0x1fffffffu,4,0x80000000u)) return 1;
  p->r[2]=42; return 0;
}
int main(int argc,char **argv) { damage=argc>1?atoi(argv[1]):0;''')
    native = native.replace('  s.r[31] =', '''  s.status_known=1; s.cp0_status=0x24000000; s.fr_mode=2;
  s.cp0_readonly_known=(1u<<4)|(1u<<20);
  if (damage==1) s.ram[HOST_PC&0x1fffffffu]^=1;
  s.r[31] =''')
    native = native.replace('  printf("]}\\n");', '''  printf("],\\"global_cp0\\":[%llu,%u,%llu]}\\n",
    (unsigned long long)s.cp0_context,s.cp0_wired,(unsigned long long)s.cp0_xcontext);''')
    (OUT / 'harness.c').write_text(native)
    binary = OUT / 'check.exe'
    compile_command = [cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                       '-Wno-unused-function', '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u',
                       f'-DHOST_PC={host_pc}u', '-I', str(OUT), str(OUT / 'harness.c'), '-lm', '-o', str(binary)]

    def build(body=host, declared=declaration):
        raw.write_bytes(A.assemble([*prefix, 'host', *body]))
        runtime.write_text(json.dumps(declared))
        subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
                        str(OUT / 'native.c'), str(runtime)], check=True)
        subprocess.run(compile_command, check=True)

    build()
    expected = json.loads(ares_oracle.execute(oracle, raw, hex(A.EXIT), capture_output=True, text=True, check=True, timeout=30).stdout)
    actual = json.loads(subprocess.check_output([str(binary)], text=True, timeout=30))
    assert actual == expected, {k: (actual[k], expected[k]) for k in expected if actual[k] != expected[k]}
    generated = (OUT / 'native.c').read_text()
    for damage, fault in ((1, 8), (2, 2)):
        bad = subprocess.run([str(binary), str(damage)], capture_output=True, text=True, timeout=30)
        assert bad.returncode and json.loads(bad.stdout)['fault'] == fault, bad.stdout
    absent = json.loads(json.dumps(declaration))
    absent['functions'][0].pop('size')
    build(declared=absent)
    bad = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    assert bad.returncode and json.loads(bad.stdout)['fault'] == 12
    # A real CP0 writer in the guest implementation invalidates just that
    # global fact, even when its declared host replacement has no such effect.
    writer = [A.addiu(A.v0, 0, 42), A.jr(A.ra), cp(4, A.zero, 6)]
    build(writer)
    bad = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    assert bad.returncode and json.loads(bad.stdout)['fault'] == 12
    writer_generated = (OUT / 'native.c').read_text()
    mask = 's->cp0_known &= 0x100410u;'
    assert mask in writer_generated
    (OUT / 'native.c').write_text(writer_generated.replace(mask, 's->cp0_known &= 0x100450u;'))
    subprocess.run(compile_command, check=True)
    mutant = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    writer_reference = json.loads(ares_oracle.execute(oracle, raw, hex(A.EXIT), capture_output=True, text=True, check=True, timeout=30).stdout)
    assert mutant.returncode == 0 and json.loads(mutant.stdout) != writer_reference, 'clobber-mask mutation survived'
    (OUT / 'native.c').write_text(generated)
    for name in ('__ull_div', '__ll_div', 'osRecvMesg', 'osCreatePiManager'):
        queue = name == 'osRecvMesg'
        signed = name == '__ll_div'
        domain_body = [A.lw(A.t0, 16, A.a0)] if queue else [A.or_(A.t0, A.a2, A.a3)]
        if queue:
            domain_body = [A.lw(A.t0, 8, A.a0), A.bne(A.t0, 0, 'count'), A.nop,
                           A.bne(A.a2, 0, 'count'), A.nop, A.addiu(A.v0, 0, -1), A.jr(A.ra), A.nop,
                           'count', *domain_body]
        domain_body += [A.bne(A.t0, 0, 'nonzero'), A.nop, 0x0007000d, 'nonzero']
        if signed:
            domain_body += [A.addiu(A.at, 0, -1), A.bne(A.a2, A.at, 'normal'), A.nop,
                            A.bne(A.a3, A.at, 'normal'), A.nop, A.lui(A.at, 0x8000),
                            A.bne(A.a0, A.at, 'normal'), A.nop, A.bne(A.a1, 0, 'normal'), A.nop,
                            0x0006000d, 'normal']
        domain_body += [A.addiu(A.v0, 0, 42), A.jr(A.ra), A.nop]
        declared = json.loads(json.dumps(declaration))
        declared['functions'][0].update(name=name, size=4 * sum(not isinstance(word, str) for word in domain_body))
        positive = '  cpu.ipu.r[4].u64=0xffffffff80002000ull; rdram.ram.write<Word>(0x2008,argc>3?0:1,RBusDevice::ARES_DEBUGGER); rdram.ram.write<Word>(0x2010,argc>3?0:1,RBusDevice::ARES_DEBUGGER);\n' if queue else '  cpu.ipu.r[7].u64=1;\n'
        oracle_source = source.replace('  cpu.pipeline.setPc(', positive + '  cpu.pipeline.setPc(')
        (OUT / f'{name}-driver.cpp').write_text(oracle_source)
        domain_oracle = ares_oracle.build(OUT / f'{name}-driver.cpp', OUT / f'{name}-oracle')
        domain_native = native.replace('plaid_rt_host(', f'plaid_rt_{name}(')
        domain_native = domain_native.replace('  p->r[2]=42;', ('  p->r[1]=SX32(0xffffffffu);' if signed else '') + ' p->r[8]=1; p->r[2]=42;')
        if queue:
            domain_native = domain_native.replace('p->r[8]=1; p->r[2]=42;', 'p->r[8]=p->ram[0x200b]?1:0; p->r[2]=p->ram[0x200b]?42:SX32(0xffffffffu);')
        seed = '  s.r[4]=SX32(0x80002000u); s.ram[0x200b]=1; s.ram[0x2013]=1; if(damage==3) s.ram[0x2013]=0; if(damage==5) s.ram[0x200b]=s.ram[0x2013]=0;\n' if queue else '  s.r[7]=damage==3?0:1;\n'
        if signed:
            seed += '  if(damage==4) { s.r[4]=SX32(0x80000000u); s.r[5]=0; s.r[6]=s.r[7]=SX32(0xffffffffu); }\n'
        domain_native = domain_native.replace('  s.r[31] =', seed + '  s.r[31] =')
        domain_native = domain_native.replace('    printf("{\\"fault\\"', '    if(s.fault==12) assert(calls==0);\n    printf("{\\"fault\\"')
        (OUT / 'harness.c').write_text(domain_native)
        build(domain_body, declared)
        domain_expected = json.loads(ares_oracle.execute(domain_oracle, raw, hex(A.EXIT), capture_output=True, text=True, check=True, timeout=30).stdout)
        domain_actual = json.loads(subprocess.check_output([str(binary)], text=True, timeout=30))
        assert domain_actual == domain_expected, (name, {k: (domain_actual[k], domain_expected[k]) for k in domain_expected if domain_actual[k] != domain_expected[k]})
        if queue:
            empty_expected=json.loads(ares_oracle.execute(domain_oracle,raw,hex(A.EXIT),'empty',capture_output=True,text=True,check=True,timeout=30).stdout)
            empty_actual=json.loads(subprocess.check_output([str(binary),'5'],text=True,timeout=30))
            assert empty_actual==empty_expected,{k:(empty_actual[k],empty_expected[k]) for k in empty_expected if empty_actual[k]!=empty_expected[k]}
            early_generated=(OUT/'native.c').read_text()
            needle='q_early = fields[0] == 0u;'
            assert needle in early_generated
            (OUT/'native.c').write_text(early_generated.replace(needle,'q_early = 0; (void)fields;'))
            subprocess.run(compile_command,check=True)
            lost_probe=subprocess.run([str(binary),'5'],capture_output=True,text=True,timeout=30)
            assert lost_probe.returncode and json.loads(lost_probe.stdout)['fault']==12,'empty-probe guard mutation survived'
            (OUT/'native.c').write_text(early_generated)
            subprocess.run(compile_command,check=True)
        for damage in ((3, 4) if signed else (3,)):
            bad = subprocess.run([str(binary), str(damage)], capture_output=True, text=True, timeout=30)
            assert bad.returncode and json.loads(bad.stdout)['fault'] == 12, (name, damage, bad.stdout)
        if not signed and name != 'osCreatePiManager':
            domain_generated = (OUT / 'native.c').read_text()
            needle, replacement = (('return !count || count >', 'return 0 || count >') if queue
                                   else ('if (!divisor)', 'if (0 && !divisor)'))
            assert needle in domain_generated
            (OUT / 'native.c').write_text(domain_generated.replace(needle, replacement))
            subprocess.run(compile_command, check=True)
            mutant = subprocess.run([str(binary), '3'], capture_output=True, text=True, timeout=30)
            assert mutant.returncode == 0, 'normal-ABI domain guard mutation was not detected'
            (OUT / 'native.c').write_text(domain_generated)
    print('PASS CP0 host boundaries: full pinned-ares state, global preservation, writer/unknown refusal, source corruption, active-source protection; clobber-mask mutation killed')


if __name__ == '__main__':
    main()
