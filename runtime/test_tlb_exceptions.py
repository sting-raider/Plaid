"""Native TLB exception state versus actual pinned-ares faulting instructions."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from test_cop0 import A, ares_oracle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/tlb-exception-contract'
REGS = (4, 8, 10, 12, 13, 14, 20)
CONTEXT = 0xFEDCBA9876000000
XCONTEXT = 0x123456789ABCDEF0
EPC = 0xFFFFFFFF80001234
CAUSE = 0xB000A51C


def cases():
    return [(address, 0x24000000 | status, delay, kind)
            for address in (0x60000BD0, 0xE0001234)
            for status in (0, 2, 0x400000)
            for delay in (0, 1)
            for kind in range(5)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    variants = cases()
    params = 'static const unsigned params[][4] = {' + ','.join(
        '{' + ','.join(hex(v) + 'u' for v in row) + '}' for row in variants) + '};\n'
    # kind: fetch miss, load miss, store miss, load invalid, store modification.
    source = (ROOT / 'spikes/096-native-slice/driver.cpp').read_text()
    source = source.replace('int main(int argc, char** argv) {', params + 'int main(int argc, char** argv) {')
    source = source.replace('  bool fr0 =', '  auto p = params[std::strtoul(argv[3], nullptr, 0)];\n  bool fr0 =')
    setup = f'''  for(unsigned i=0;i<32;i++) {{
    cpu.setControlRegister(0,i); cpu.setControlRegister(5,0);
    cpu.setControlRegister(10,0x40000000u+i*0x2000u);
    cpu.setControlRegister(2,1); cpu.setControlRegister(3,1); cpu.TLBWI();
  }}
  if(p[3]>=3) {{
    cpu.setControlRegister(0,0); cpu.setControlRegister(10,(u64)(s64)(s32)(p[0]&~0x1fffu));
    cpu.setControlRegister(2,p[3]==3?1:0x1b); cpu.setControlRegister(3,p[3]==3?1:0x5b); cpu.TLBWI();
  }}
  cpu.setControlRegister(4,0x{CONTEXT:x}ull);
  cpu.scc.xcontext.badVirtualAddress=0xabcdef; cpu.scc.xcontext.region=2;
  cpu.setControlRegister(20,0x{XCONTEXT:x}ull);
  u64 written_xcontext=cpu.getControlRegister(20);
  cpu.setControlRegister(10,0xc00000ff123440a5ull);
  cpu.setControlRegister(14,0x{EPC:x}ull);
  cpu.scc.cause.interruptPending=0xa5; cpu.scc.cause.exceptionCode=7;
  cpu.scc.cause.coprocessorError=3; cpu.scc.cause.branchDelay=1;
  cpu.scc.llbit=1;
  cpu.setControlRegister(12,p[1]); cpu.context.setMode();
  cpu.ipu.r[9].u64=(u64)(s64)(s32)p[0];
  cpu.pipeline.setPc(p[3]==0?(u64)(s64)(s32)p[0]:0xffffffff80000000ull);
'''
    # A fetch miss cannot be a delay-slot data access.
    source = source.replace('  cpu.pipeline.setPc(0xffffffff80000000ull);', setup)
    start = source.index('  int n = 0;')
    end = source.index('  std::printf("{\\"pc\\"', start)
    source = source[:start] + '  for(unsigned i=0;i<(p[3] && p[2]?2u:1u);i++) cpu.instruction();\n' + source[end:]
    dump = '  std::printf("],\\"cp0\\":[");\n'
    dump += '  { unsigned regs[]={4,8,10,12,13,14,20}; for(unsigned i=0;i<7;i++) std::printf("%s%llu",i?",":"",(unsigned long long)cpu.getControlRegister(regs[i])); }\n'
    dump += '  std::printf("],\\"llbit\\":%u,\\"written_xcontext\\":%llu,\\"raised_cause\\":%u}\\n",(unsigned)cpu.scc.llbit,(unsigned long long)written_xcontext,(unsigned)cpu.getControlRegister(13));'
    source = source.replace('  std::printf("]}\\n");', dump)
    (OUT / 'driver.cpp').write_text(source)
    oracle = ares_oracle.build(OUT / 'driver.cpp', OUT / 'oracle')

    raw = OUT / 'native.bin'
    raw.write_bytes(A.assemble(A.DONE))
    subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
                    str(OUT / 'native.c')], check=True)
    native = (ROOT / 'spikes/096-native-slice/harness.c').read_text()
    native = native.replace('#include "runtime.c"', '#include <assert.h>\n#include <stdlib.h>')
    native = native.replace('int main(void) {', 'static u32 pending(plaid_state *s) { (void)s; return 0xa500u; }\n'+params + 'int main(int argc, char **argv) {\n  assert(argc==2 || argc==3); const unsigned *p=params[strtoul(argv[1],0,0)]; u32 vector;')
    native = native.replace('  plaid_load_images(&s);', f'''  s.status_known=1; s.cp0_status=p[1];
  s.cp0_context=0x{CONTEXT:x}ull & 0xffffffffff800000ull;
  s.cp0_xcontext=0x10abcdef0ull;
  assert(!plaid_cp0_write(&s,20,0x{XCONTEXT:x}ull,0));
  u64 written_xcontext=s.cp0_xcontext;
  s.cp0_entryhi=0xc00000ff123440a5ull; s.cp0_epc=0x{EPC:x}ull; s.cp0_cause=0x{CAUSE:x}u;
  s.cp0_known=(1u<<4)|(1u<<10)|(1u<<13)|(1u<<14)|(1u<<20);
  s.llbit=1; s.r[9]=SX32(p[0]);
  if(argc==3) {{ s.cp0_interrupt_pending=pending; s.cp0_cause&=~0xff00u; if(!(p[1]&2u)) s.cp0_known&=~(1u<<13); }}
''')
    native = native.replace('if (plaid_run(&s))', 'if (plaid_cp0_tlb_exception(&s,SX32(p[0]),p[3]?(0x80000000u+4u*p[2]):p[0],p[3]?p[2]:0,p[3]==4?1:p[3]==2?3:2,p[3]<3,&vector))')
    ndump = '  printf("],\\"cp0\\":[");\n'
    ndump += '  { u32 regs[]={4,8,10,12,13,14,20}; u64 v; for(unsigned i=0;i<7;i++) { assert(!plaid_cp0_read(&s,regs[i],&v,0)); printf("%s%llu",i?",":"",(unsigned long long)v); }}\n'
    ndump += '  printf("],\\"llbit\\":%u,\\"written_xcontext\\":%llu,\\"raised_cause\\":%u}\\n",s.llbit,(unsigned long long)written_xcontext,raised_cause);'
    native = native.replace('  printf("{\\"pc\\"', '  u32 raised_cause=s.cp0_cause;\n  printf("{\\"pc\\"')
    native = native.replace('  printf("]}\\n");', ndump)
    native = native.replace('  return 0;\n}', REFUSALS + '  return 0;\n}')
    (OUT / 'harness.c').write_text(native)
    binary = OUT / ('check.exe' if os.name == 'nt' else 'check')
    command = [cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-function', '-Wno-unused-label',
               '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u', '-I', str(OUT),
               str(OUT / 'harness.c'), '-lm', '-o', str(binary)]
    subprocess.run(command, check=True)
    expected_cases = []
    for index, (_, _, delay, kind) in enumerate(variants):
        instruction = A.sw(A.t0, 0, A.t1) if kind in (2, 4) else A.lw(A.t0, 0, A.t1)
        raw.write_bytes(A.assemble(([A.beq(0, 0, 'after'), instruction, 'after', A.nop]
                                    if delay and kind else [instruction])))
        expected = json.loads(ares_oracle.execute(oracle, raw, hex(A.EXIT), str(index),
            capture_output=True, text=True, check=True, timeout=30).stdout)
        actual = json.loads(subprocess.check_output([str(binary), str(index)], text=True, timeout=30))
        assert actual == expected, (index, {k: (actual[k], expected[k]) for k in expected if actual[k] != expected[k]})
        callback = json.loads(subprocess.check_output([str(binary), str(index), 'pending'], text=True, timeout=30))
        assert callback == expected, (index, 'pending callback', {k: (callback[k], expected[k]) for k in expected if callback[k] != expected[k]})
        expected_cases.append(expected)
    generated = (OUT / 'native.c').read_text()
    mutations = [('BD', 'pc - (delay ? 4u : 0u)', 'pc'),
                 ('refill vector', 'miss && !(status & 2u) ? 0 : 0x180u', '0x180u'),
                 ('Context', '((va >> 9) & 0x7ffff0ull)', '0'),
                 ('nested EPC', 'if (!(status & 2u)) {', 'if (1) {'),
                 ('pending Cause', 'cause = (cause & ~0xff00u) | (s->cp0_interrupt_pending(s) & 0xff00u);', 'cause &= ~0xff00u;')]
    try:
        for name, needle, changed in mutations:
            assert generated.count(needle) == 1, (name, generated.count(needle))
            (OUT / 'native.c').write_text(generated.replace(needle, changed))
            subprocess.run(command, check=True)
            killed = False
            for index in range(len(variants)):
                result = subprocess.run([str(binary), str(index), *(['pending'] if name == 'pending Cause' else [])], capture_output=True, text=True, timeout=30)
                if result.returncode or json.loads(result.stdout) != expected_cases[index]:
                    killed = True
                    break
            assert killed, name + ' mutation survived'
    finally:
        (OUT / 'native.c').write_text(generated)
    (OUT / 'receipt.json').write_text(json.dumps(dict(ares=ares_oracle.REV, cases=len(variants),
        matched=list(actual), mutations=[m[0] for m in mutations]), indent=2))
    print(f'PASS {len(variants)*2} TLB exception state oracle comparisons; miss/invalid/modification, BEV/EXL/BD, Context/XContext/ASID, GPR/FPR/RAM/LL, live pending Cause; five mutations killed')


REFUSALS = r'''  { static plaid_state before; u32 v=123;
    #define REFUSE(expr) do { before=s; assert(expr); assert(s.fault==12); s.fault=before.fault; s.fault_pc=before.fault_pc; assert(!memcmp(&s,&before,sizeof s)); assert(v==123); } while(0)
    #define RAISE() plaid_cp0_tlb_exception(&s,SX32(0x60001234u),0x80000004u,0,2,1,&v)
    for(unsigned bit=0;bit<32;bit++) if(((1u<<4)|(1u<<10)|(1u<<13)|(1u<<14)|(1u<<20))&(1u<<bit)) {
      u32 known=s.cp0_known; s.cp0_known&=~(1u<<bit); REFUSE(RAISE()); s.cp0_known=known;
    }
    s.status_known=0; REFUSE(RAISE()); s.status_known=1;
    s.cp0_status|=0x80; REFUSE(RAISE()); s.cp0_status&=~0x80u;
    REFUSE(plaid_cp0_tlb_exception(&s,0x60001234u,0x80000003u,0,2,1,&v));
    REFUSE(plaid_cp0_tlb_exception(&s,0x100000000ull,0x80000004u,0,2,1,&v));
    REFUSE(plaid_cp0_tlb_exception(&s,SX32(0x60001234u),0x80000004u,0,1,1,&v));
    #undef RAISE
    #undef REFUSE
  }
'''


if __name__ == '__main__':
    main()
