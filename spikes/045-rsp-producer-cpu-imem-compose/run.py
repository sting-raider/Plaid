#!/usr/bin/env python3
"""Build and execute exact pinned ares RSP-producer -> CPU-copy -> IMEM composition."""
from pathlib import Path
import copy, hashlib, importlib.util, json, os, subprocess
from prepare import generate

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REF=ROOT/'.refs/ares'
OUTPUT=ROOT/'target/ares-rsp-producer-cpu-imem-compose'
PIN='9408cb43d4948fc3ea6e152a307a34348df3fe04'

def load_builder():
    spec=importlib.util.spec_from_file_location('compose_builder',ROOT/'spikes/003-ares-oracle/run.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def build_sensor(builder):
    inputs=(HERE/'driver.cpp',HERE/'observer.hpp',HERE/'prepare.py',Path(builder.__file__),ROOT/'spikes/039-ares-cpu-sp-fetch/prepare.py',ROOT/'spikes/042-ares-rsp-dmem-history/prepare.py')
    key=hashlib.sha256(b''.join(p.read_bytes() for p in inputs)).hexdigest()
    out=OUTPUT/('sensor-'+key[:12]);exe=out/'oracle-compose'
    if exe.exists(): return exe
    builder.build(HERE/'driver.cpp',out,extra_sources=inputs);generate(REF,out)
    flags=['-O1','-std=c++20','-msse4.1','-DSLJIT_HAVE_CONFIG_PRE=1','-DSLJIT_HAVE_CONFIG_POST=1','-DPLAID_RSP_CPU_IMEM_SENSOR=1']
    includes=[out/'include',*(REF/p for p in ('ares','nall','.','thirdparty','thirdparty/xxhash','ares/n64/system'))];include_flags=[x for p in includes for x in ('-I',str(p))]
    sources=[HERE/'driver.cpp',out/'core.cpp',out/'n64.cpp',REF/'ares/component/processor/sm5k/sm5k.cpp',REF/'ares/ares/memory/fixed-allocator.cpp',REF/'nall/nall/nall.cpp',REF/'thirdparty/sljitAllocator.cpp']
    with (out/'sensor-build.log').open('w',encoding='utf-8') as log:
        try: subprocess.run(['g++',*flags,*include_flags,*map(str,sources),str(out/'sljit.o'),str(out/'libco.o'),'-pthread','-ldl','-o',str(exe)],check=True,stdout=log,stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print('\n'.join((out/'sensor-build.log').read_text(encoding='utf-8').splitlines()[-80:]),flush=True);raise
    return exe

def bytes_of(value,width): return [(value>>(8*(width-1-i)))&0xff for i in range(width)]
def low32(x): return x & 0xffffffff

def decode(step):
    w=step['word'];op=w>>26;rs=(w>>21)&31;rt=(w>>16)&31;rd=(w>>11)&31;funct=w&63
    if op==0x23:return ('lw',rs,rt,None)
    if op==0x2b:return ('sw',rs,rt,None)
    if op==0 and funct==0x21:return ('addu',rs,rt,rd)
    return ('other',rs,rt,rd)

def replay(events,steps):
    assert [e['ordinal'] for e in events]==list(range(1,len(events)+1))
    step_by_phase={s['phase']:s for s in steps};assert len(step_by_phase)==len(steps)
    dbytes=bytes_of(0x340800aa,4)+bytes_of(0xaaee7722,4);dorig=[f'initial:{i}' for i in range(8)]
    rsp_active=None;foreign=[];reads={};writes={};rsp_by_phase={};unknown_by_phase={};cpu_by_phase={}
    for e in events:
        k=e['kind']
        if k=='rsp_begin': assert rsp_active is None and e['context']==e['ordinal'];rsp_active=(e['context'],e['pc'],e['word'])
        elif k=='rsp_end': assert rsp_active and (e['context'],e['pc'],e['word'])==rsp_active;rsp_active=None
        elif k=='rsp_sink':
            assert rsp_active and e['context']==rsp_active[0];label=f"rsp:p{e['phase']}:c{e['context']}:o{e['ordinal']}"
            for i,b in enumerate(bytes_of(e['value'],e['bytes'])):
                off=(e['offset']+i)&0xfff
                if off<8:dbytes[off]=b;dorig[off]=label;rsp_by_phase.setdefault(e['phase'],{})[off]=label
        elif k=='foreign_sink':
            assert rsp_active is None and e['context']==0;label=f"unknown:p{e['phase']}:o{e['ordinal']}"
            for i,b in enumerate(bytes_of(e['value'],e['bytes'])):
                off=(e['offset']+i)&0xfff
                if off<8:dbytes[off]=b;dorig[off]=label;unknown_by_phase.setdefault(e['phase'],{})[off]=label
            foreign.append(e)
        elif k=='sp_read':
            assert e['cpu'] and e['bank']==0 and e['bytes']==4;assert bytes_of(e['value'],4)==dbytes[e['offset']:e['offset']+4]
            reads[e['phase']]=(e,tuple(dorig[e['offset']:e['offset']+4]))
        elif k=='sp_write':
            assert e['cpu'] and e['bytes']==4;writes.setdefault(e['phase'],[]).append(e)
            if e['bank']==0:
                matches=[x for x in foreign if x['phase']==e['phase'] and x['offset']==e['offset'] and x['bytes']==4 and x['value']==e['value'] and x['ordinal']<e['ordinal']];assert len(matches)==1
                label=f"cpu:p{e['phase']}:o{e['ordinal']}"
                for i,b in enumerate(bytes_of(e['value'],4)):
                    off=e['offset']+i
                    if off<8:dbytes[off]=b;dorig[off]=label;cpu_by_phase.setdefault(e['phase'],{})[off]=label
        else: raise AssertionError(k)
    assert rsp_active is None
    reg_origin={};cert=[]
    for phase in sorted(step_by_phase):
        s=step_by_phase[phase];kind,rs,rt,rd=decode(s)
        if kind=='lw':
            assert phase in reads and len(writes.get(phase,[]))==0;e,orig=reads[phase];assert low32(s['after'][rt])==e['value'];reg_origin[rt]=orig
        elif kind=='sw':
            ws=writes.get(phase,[]);assert len(ws)==1;e=ws[0];assert e['value']==low32(s['before'][rt])
            if e['bank']==1 and rt in reg_origin: cert.append({'phase':phase,'offset':e['offset'],'value':e['value'],'source_reg':rt,'ancestry':list(reg_origin[rt])})
        elif kind=='addu': reg_origin.pop(rd,None)
        elif rd is not None: reg_origin.pop(rd,None)
    assert [c['phase'] for c in cert]==[3,6,13],cert
    c3,c6,c13=cert;assert c3['value']==c6['value']==0x11223344;assert all(x.startswith('rsp:p1:') for x in c3['ancestry']);assert all(x.startswith('rsp:p4:') for x in c6['ancestry']);assert c3['ancestry']!=c6['ancestry']
    kinds=[x.split(':',1)[0] for x in c13['ancestry']];assert kinds==['cpu','unknown','rsp','rsp'],(kinds,c13);assert c13['ancestry'][2]==rsp_by_phase[9][2];assert c13['ancestry'][3]==rsp_by_phase[10][3];assert c13['ancestry'][1]==unknown_by_phase[8][1];assert c13['ancestry'][0]==cpu_by_phase[7][0]
    equal=[(p,e['value']) for p,(e,_) in reads.items() if p<13 and e['value']==0xaaee7722];assert [p for p,_ in equal][-2:]==[11,12]
    return {'certificates':cert,'naive_latest_equal_read_phase':12,'actual_source_read_phase':11,'rsp_primitive_sink_count':sum(1 for e in events if e['kind']=='rsp_sink'),'event_count':len(events)}

def reject_forgeries(events,steps):
    cases=[]
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='rsp_sink' and e['phase']==4)['context']=0;cases.append(('lost_same_value_rsp_context',x,steps))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='foreign_sink' and e['phase']==8)['offset']=4;cases.append(('unknown_byte_wrong_offset',x,steps))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='sp_read' and e['phase']==11)['value']^=1;cases.append(('forged_source_read_value',x,steps))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='sp_write' and e['phase']==13)['bank']=0;cases.append(('forged_imem_bank',x,steps))
    x=copy.deepcopy(events);x[1]['ordinal']=x[0]['ordinal'];cases.append(('duplicate_ordinal',x,steps))
    x=copy.deepcopy(events);victim=next(e for e in x if e['kind']=='rsp_sink' and e['phase']==1);x.remove(victim)
    for i,e in enumerate(x,1):e['ordinal']=i
    cases.append(('deleted_rsp_primitive',x,steps))
    y=copy.deepcopy(steps);next(s for s in y if s['phase']==12)['word']=(0x23<<26)|(16<<21)|(8<<16)|4;cases.append(('decoy_forged_to_t0',events,y))
    y=copy.deepcopy(steps);next(s for s in y if s['phase']==14)['word']=0;cases.append(('hidden_clobber_opcode',events,y))
    rejected=[]
    for name,ev,st in cases:
        try: replay(ev,st)
        except (AssertionError,KeyError,IndexError): rejected.append(name)
        else: raise AssertionError('forgery accepted: '+name)
    assert len(rejected)==len(cases);return rejected

def parse(raw):
    rows=[x for x in raw.splitlines() if x.startswith('{')];assert len(rows)==1,raw;return json.loads(rows[0])

def main():
    if os.name=='nt':
        p=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip();subprocess.run(['wsl','-d','Ubuntu','--exec','python3',p],check=True);return
    builder=load_builder();assert builder.REV==PIN;assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REF,text=True).strip()==PIN;subprocess.run(['git','diff','--quiet','HEAD'],cwd=REF,check=True)
    OUTPUT.mkdir(parents=True,exist_ok=True);baseline=builder.build(HERE/'driver.cpp',OUTPUT/'baseline',extra_sources=(HERE/'driver.cpp',));sensor=build_sensor(builder)
    original=parse(subprocess.check_output([str(baseline),'plain'],text=True,timeout=30));plain=parse(subprocess.check_output([str(sensor),'plain'],text=True,timeout=30));raw1=subprocess.check_output([str(sensor),'traced'],text=True,timeout=30);raw2=subprocess.check_output([str(sensor),'traced'],text=True,timeout=30);traced=parse(raw1);repeat=parse(raw2);assert raw1==raw2 and traced==repeat
    assert original['events']==plain['events']==[];assert original['state']==plain['state']==traced['state']==repeat['state'];assert original['steps']==plain['steps']==traced['steps']==repeat['steps']
    lineage=replay(traced['events'],traced['steps']);forged=reject_forgeries(traced['events'],traced['steps']);result={'pin':PIN,'baseline_equal':True,'repeat_equal':True,'lineage':lineage,'forgeries':forged,'raw':traced}
    path=OUTPUT/'results.json';path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n');print(json.dumps({k:result[k] for k in ('pin','baseline_equal','repeat_equal','lineage','forgeries')},sort_keys=True));print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest());print('PASS RSP DMEM byte generations compose through actual CPU LW/SW into executable IMEM without value-only collapse')

if __name__=='__main__': main()
