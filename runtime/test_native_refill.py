"""A synthetic unmapped instruction fetch executes a lowered native refill vector."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from test_cop0 import A, ares_oracle, DUMP_ARES, DUMP_NATIVE

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'target/native-refill-contract'

REFUSALS = r'''
  { static plaid_state before;
    s.cp0_interrupt_pending=0;
    /* Reopen the target VPN without executing a guest handler. */
    s.tlb[31].hi=0x50000000;
    #define REFUSE() do { before=s; assert(plaid_native_refill(&s,0x60000000u)); assert(s.fault==12); s.fault=before.fault; s.fault_pc=before.fault_pc; assert(!memcmp(&s,&before,sizeof s)); } while(0)
    s.status_known=0; REFUSE(); s.status_known=1;
    s.cp0_status|=2u; REFUSE(); s.cp0_status&=~2u;
    s.cp0_status|=4u; REFUSE(); s.cp0_status&=~4u;
    s.native_refill_active=1; REFUSE(); s.native_refill_active=0;
    s.native_refill_active=1;
    const u32 unsupported_status[]={0x2400ff01u,0x24000080u,0x24000004u};
    for(unsigned i=0;i<3;i++) {
      before=s; assert(plaid_cp0_write(&s,12,unsupported_status[i],4));
      assert(s.fault==12); s.fault=before.fault; s.fault_pc=before.fault_pc;
      assert(!memcmp(&s,&before,sizeof s));
    }
    s.native_refill_active=0;
    u32 known=s.cp0_known;
    const u32 regs[]={4,10,13,20};
    for (unsigned i=0;i<4;i++) { s.cp0_known=known & ~(1u<<regs[i]); REFUSE(); }
    s.cp0_known=known;
    #undef REFUSE
  }
'''


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    exe=Path(os.environ.get('PLAID_EXE',ROOT/'target/debug'/('plaid.exe' if os.name=='nt' else 'plaid')))
    cc=shutil.which('gcc')
    cp=lambda sub,rt,rd: 16<<26|sub<<21|rt<<16|rd<<11
    li=lambda r,v:[A.lui(r,v>>16&0xffff),A.ori(r,r,v&0xffff)]
    write=lambda rd,v:[*li(26,v),cp(4,26,rd)]
    # Context.BadVPN indexes an original synthetic page table. The first
    # refill installs an invalid pair; the general vector makes its PTE valid.
    # The same fetch then refills again and enters the guarded mapped source.
    handler=[cp(0,26,4),A.lui(27,0xa000),A.or_(26,26,27),
             A.lw(27,0,26),cp(4,27,2),A.lw(27,4,26),cp(4,27,3),
             *write(5,0),0x42000006,0x42000018]
    general=[cp(0,27,12),*li(26,0xa000100c),A.sw(27,0,26),*li(26,0xfffffffc),
             A.and_(27,27,26),cp(4,27,12),*li(26,0xa0300000),*li(27,0x801f),A.sw(27,0,26),
             *li(27,0x805f),A.sw(27,4,26),*li(26,0xa0001008),
             A.lw(27,0,26),A.addiu(27,27,1),A.sw(27,0,26),
             *write(10,0x50000000),0x42000006,*li(26,0xa000100c),A.lw(27,0,26),cp(4,27,12),0x42000018]
    items=['handler',*handler,*[A.nop]*((0x180-len(handler)*4)//4),'general',*general]
    items += [A.nop]*((0x400-(0x180+len(general)*4))//4)+['entry']
    items += [*write(6,31),*write(5,0),*write(2,1),*write(3,1)]
    for i in range(32):
        items += [*write(0,i),*write(10,0x40000000+i*0x2000),0x42000002]
    items += [*li(26,0xa0300000),*li(27,1),A.sw(27,0,26),*li(27,0x41),A.sw(27,4,26)]
    payload=[A.jr(A.ra),A.addiu(A.v0,0,42)]
    items += [*li(A.at,0xa0200000)]
    for i,w in enumerate(payload):
        items += [*li(A.t0,w),A.sw(A.t0,i*4,A.at)]
    items += [A.addiu(A.t7,0,0),A.bne(A.t7,0,'declare'),A.nop,
              *li(A.t9,0x60000000),A.jalr(A.ra,A.t9),A.nop,
              *li(A.gp,0x80001000),A.sw(A.v0,0,A.gp),*A.DONE,
              'declare',A.jal('handler'),A.nop,A.jal('general'),A.nop,*A.DONE,'payload',*payload]
    labels=A.label_pcs(items)
    raw=A.assemble(items)
    image=OUT/'input.z64'; image.write_bytes(bytes.fromhex('80371240')+bytes(0xffc)+raw)
    (OUT/'input.bin').write_bytes(raw)
    loads=OUT/'loads.json'
    loads.write_text(json.dumps(dict(format='plaid-loads-v0',source='synthetic native refill',loads=[
        dict(destination='0x60000000',size='0x8',rom=hex(0x1000+labels['payload']-A.BASE),
             encoding='tlb_raw',slot=True,text_size='0x8')])))
    mapping=OUT/'map.json'
    subprocess.run([str(exe),'discover',str(image),'0x1000',hex(A.BASE),hex(len(raw)),hex(labels['entry']),str(mapping),
                    '--loads',str(loads),'--address-taken'],check=True)
    program=json.loads(mapping.read_text())
    vectors=[block for block in program['blocks'] if block['start']['pc'] in (A.BASE,A.BASE+0x180)]
    program['tlb_exception_vectors']=[block['start'] for block in vectors]
    for block in vectors:
        if not any(address==block['start'] for address,_ in program['entries']):
            program['entries'].append([block['start'],block['evidence']])
    assert len(program['tlb_exception_vectors'])==2
    mapping.write_text(json.dumps(program))
    subprocess.run([str(exe),'lower-map',str(image),str(mapping),hex(labels['entry']),hex(A.EXIT),
                    str(OUT/'native.c'),'--residual-dispatch'],check=True)
    source=(ROOT/'spikes/096-native-slice/driver.cpp').read_text()
    source=source.replace('cpu.context.setMode();', 'cpu.setControlRegister(12,argc>3?0x2400ff01:0x24000000); cpu.setControlRegister(4,0); cpu.setControlRegister(20,0); cpu.context.setMode();')
    source=source.replace('cpu.pipeline.setPc(0xffffffff80000000ull);',f'cpu.pipeline.setPc(0xffffffff{labels["entry"]:08x}ull);')
    source=source.replace(' || cpu.scc.cause.exceptionCode','')
    extra_ares='  std::printf(",\\"exception\\":["); { unsigned regs[]={4,8,13,14,20}; for(unsigned i=0;i<5;i++) std::printf("%s%llu",i?",":"",(unsigned long long)cpu.getControlRegister(regs[i])); } std::printf("]");\n'
    source=source.replace('  std::printf("]}\\n");','  std::printf("]");\n'+DUMP_ARES+extra_ares+'  std::printf("}\\n");')
    (OUT/'driver.cpp').write_text(source)
    oracle=ares_oracle.build(OUT/'driver.cpp',OUT/'oracle')
    native=(ROOT/'spikes/096-native-slice/harness.c').read_text()
    native=native.replace('#include "runtime.c"','#include <assert.h>')
    native=native.replace('int main(void) {', '''static u32 pending(plaid_state *p) { (void)p; return 0; }
int main(int argc,char **argv) { (void)argv;''')
    native=native.replace('  s.r[31] =','  s.status_known=1; s.cp0_status=0x24000000; s.fr_mode=2; s.cp0_known=(1u<<4)|(1u<<10)|(1u<<13)|(1u<<20);\n  s.r[31] =')
    native=native.replace('  if (plaid_run(&s))', '''  assert(plaid_link(&s,0x60000000u)==1);
  assert(!s.fault && !s.cp0_cause && !s.cp0_badvaddr && !s.cp0_readonly_known && !s.native_refill_active);
  if (plaid_run(&s))''')
    native=native.replace('  assert(plaid_link', '''  if (argc>1) { s.cp0_status=0x2400ff01; s.status_thread=0x80010000; s.cp0_known&=~(1u<<13); s.cp0_interrupt_pending=pending; }
  assert(plaid_link''')
    extra_native='  printf(",\\"exception\\":["); { u32 regs[]={4,8,13,14,20}; u64 v; for(unsigned i=0;i<5;i++) { assert(!plaid_cp0_read(&s,regs[i],&v,0)); printf("%s%llu",i?",":"",(unsigned long long)v); } } printf("]");\n'
    native=native.replace('  printf("]}\\n");','  printf("]");\n'+DUMP_NATIVE+extra_native+'  printf("}\\n");')
    native=native.replace('  return 0;\n}',REFUSALS+'  return 0;\n}')
    (OUT/'harness.c').write_text(native)
    binary=OUT/'check.exe'
    command=[cc,'-O2','-std=c11','-Wall','-Werror','-Wno-unused-label','-Wno-unused-function',
             '-DPLAID_LOWERED="native.c"',f'-DPLAID_EXIT={A.EXIT}u','-I',str(OUT),str(OUT/'harness.c'),'-lm','-o',str(binary)]
    subprocess.run(command,check=True)
    expected=json.loads(ares_oracle.execute(oracle,OUT/'input.bin',hex(A.EXIT),capture_output=True,text=True,check=True,timeout=30).stdout)
    actual=json.loads(subprocess.check_output([str(binary)],text=True,timeout=30))
    assert actual==expected,{k:(actual[k],expected[k]) for k in expected if expected[k]!=actual[k]}
    assert actual['ram'][0]==42 and actual['ram'][2]==1
    expected_sdk=json.loads(ares_oracle.execute(oracle,OUT/'input.bin',hex(A.EXIT),'sdk',capture_output=True,text=True,check=True,timeout=30).stdout)
    actual_sdk=json.loads(subprocess.check_output([str(binary),'sdk'],text=True,timeout=30))
    assert actual_sdk==expected_sdk,{k:(actual_sdk[k],expected_sdk[k]) for k in expected_sdk if expected_sdk[k]!=actual_sdk[k]}
    subprocess.run([str(exe),'lower-map',str(image),str(mapping),hex(labels['entry']),hex(A.EXIT),
                    str(OUT/'separate.c'),'--parts','3','--runtime-unit','--residual-dispatch'],check=True)
    separate_harness=native.replace('#include <assert.h>','#include <assert.h>\nint plaid_native_refill(plaid_state *,u32);')
    (OUT/'separate-harness.c').write_text(separate_harness)
    objects=[]
    for c in [OUT/'separate.c',*sorted(OUT.glob('separate.part*.c'))]:
        obj=c.with_suffix('.o');subprocess.run([cc,'-O2','-std=c11','-Wall','-Werror','-Wno-unused-label','-Wno-unused-function','-c',str(c),'-o',str(obj)],check=True);objects.append(obj)
    separate=OUT/'separate.exe'
    subprocess.run([cc,'-O2','-std=c11','-Wall','-Werror','-Wno-unused-label','-Wno-unused-function','-DPLAID_LOWERED="separate.runtime.h"',f'-DPLAID_EXIT={A.EXIT}u','-I',str(OUT),str(OUT/'separate-harness.c'),*map(str,objects),'-lm','-o',str(separate)],check=True)
    for args,wanted in [([],expected),(['sdk'],expected_sdk)]:
        split=json.loads(subprocess.check_output([str(separate),*args],text=True,timeout=30))
        assert split==wanted,{k:(split[k],wanted[k]) for k in wanted if split[k]!=wanted[k]}
    generated=(OUT/'native.c').read_text()
    vector='case 0x80000000u: return F_80000000(s, ret);'
    assert generated.count(vector)==1
    corrupt=generated.replace(vector,'case 0x80000000u: { int r=F_80000000(s,ret); if (s->cp0_tlb.lo[0]&2u) s->ram[0x200000]^=1; return r; }')
    try:
        (OUT/'native.c').write_text(corrupt)
        subprocess.run(command,check=True)
        result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30)
        assert result.returncode and json.loads(result.stdout)['fault']==3,result.stdout
        guard='if (!plaid_ovls[k].verify(s->ram, PLAID_RAM_SIZE, b)) continue;'
        assert corrupt.count(guard)==1
        (OUT/'native.c').write_text(corrupt.replace(guard,'if (0) continue;'))
        subprocess.run(command,check=True)
        mutant=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30)
        assert mutant.returncode==0 and json.loads(mutant.stdout)==expected, 'corrupt-source verifier mutation was not detected'
        # A matching invalid entry must choose the general vector, rather than
        # repeating the fast refill forever. Detect both this distinction and
        # accidental removal of the actual-fetch exception boundary.
        for old,new in [('miss = 0;', 'miss = 1;'),
                        ('t = SX32(plaid_fetch_link(s, (u32)t))', 't = SX32(plaid_link(s, (u32)t))')]:
            assert old in generated
            (OUT/'native.c').write_text(generated.replace(old,new))
            subprocess.run(command,check=True)
            result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30)
            assert result.returncode, 'native fetch/refill mutation was not detected'
    finally:
        (OUT/'native.c').write_text(generated)
    print('PASS lowered native refill vector and guarded mapped redispatch: full pinned-ares state; source corruption refused and verifier-removal mutation killed')


if __name__=='__main__':
    main()
