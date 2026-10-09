"""Execute a bounded exact-ares adjacent LW/LWU -> SW dataflow experiment."""
from pathlib import Path
import copy, hashlib, importlib.util, json, os, subprocess
from prepare import generate

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REF=ROOT/'.refs/ares'
OUTPUT=ROOT/'target/ares-cpu-copy-dataflow-spike'
REV='9408cb43d4948fc3ea6e152a307a34348df3fe04'


def load_builder():
    spec=importlib.util.spec_from_file_location('builder',ROOT/'spikes/003-ares-oracle/run.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def sensor(builder):
    inputs=(HERE/'driver.cpp',HERE/'observer.hpp',HERE/'prepare.py',Path(builder.__file__))
    key=hashlib.sha256(b''.join(p.read_bytes() for p in inputs)).hexdigest()
    out=OUTPUT/('sensor-'+key[:12]);exe=out/'oracle-flow'
    if exe.exists(): return exe
    builder.build(HERE/'baseline.cpp',out,raw_fetch_access=True,physical_fetch_access=True,
        rdram_scalar_access=True,extra_sources=inputs)
    generate(REF,out)
    flags=['-O1','-std=c++20','-msse4.1','-DSLJIT_HAVE_CONFIG_PRE=1','-DSLJIT_HAVE_CONFIG_POST=1']
    includes=[out/'include',*(REF/p for p in ('ares','nall','.','thirdparty','thirdparty/xxhash','ares/n64/system'))]
    include_flags=[part for p in includes for part in ('-I',str(p))]
    sources=[HERE/'driver.cpp',out/'core.cpp',out/'n64.cpp',REF/'ares/component/processor/sm5k/sm5k.cpp',REF/'ares/ares/memory/fixed-allocator.cpp',REF/'nall/nall/nall.cpp',REF/'thirdparty/sljitAllocator.cpp']
    with (out/'flow-build.log').open('w') as log:
        try:
            subprocess.run(['g++',*flags,*include_flags,*map(str,sources),str(out/'sljit.o'),str(out/'libco.o'),'-pthread','-ldl','-o',str(exe)],check=True,stdout=log,stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print('\n'.join((out/'flow-build.log').read_text().splitlines()[-60:]),flush=True);raise
    return exe


def sx32(v):
    v &= 0xffffffff
    return v | 0xffffffff00000000 if v & 0x80000000 else v

def simm16(v):
    v &= 0xffff
    return v-0x10000 if v&0x8000 else v

def paddr(v): return v & 0x1fffffff

def decode(word): return (word>>26)&63,(word>>21)&31,(word>>16)&31,simm16(word)


def replay(data):
    ins=data['instruction_events'];scalars=data['scalar_events']
    merged=sorted([('i',e) for e in ins]+[('s',e) for e in scalars],key=lambda x:x[1]['ordinal'])
    assert [e['ordinal'] for _,e in merged]==list(range(1,len(merged)+1))
    contexts=[];active=None
    for kind,e in merged:
        if kind=='i':
            assert len(e['gpr'])==32
            if e['begin']:
                assert active is None and e['context']==e['ordinal'];active={'begin':e,'scalars':[]}
            else:
                assert active is not None and e['context']==active['begin']['context']
                assert e['phase']==active['begin']['phase'] and e['pc']==active['begin']['pc'] and e['word']==active['begin']['word']
                active['end']=e;contexts.append(active);active=None
        elif e['context']:
            assert active is not None and e['context']==active['begin']['context']
            assert e['phase']==active['begin']['phase'] and e['pc']==active['begin']['pc'];active['scalars'].append(e)
    assert active is None

    successful_load={};certificates=[]
    for idx,c in enumerate(contexts):
        b,z=c['begin'],c['end'];op,rs,rt,imm=decode(b['word']);sc=c['scalars'];assert z['gpr'][0]==0
        if op in (0x23,0x27):
            reads=[e for e in sc if not e['write'] and e['uncached_cpu'] and e['bytes']==4]
            if len(reads)==1:
                r=reads[0];assert r['address']==paddr((b['gpr'][rs]+imm)&0xffffffffffffffff)
                value=sx32(r['value']) if op==0x23 else r['value']&0xffffffff
                assert z['gpr'][rt]==value
                for n in range(1,32):
                    if n!=rt: assert z['gpr'][n]==b['gpr'][n]
                successful_load[b['context']]={'rt':rt,'read':r,'opcode':op,'phase':b['phase']}
            else: assert not reads
        elif op==0x2b:
            writes=[e for e in sc if e['write'] and e['uncached_cpu'] and e['bytes']==4];assert len(writes)==1
            w=writes[0];assert w['address']==paddr((b['gpr'][rs]+imm)&0xffffffffffffffff) and w['value']==(b['gpr'][rt]&0xffffffff)
            assert z['gpr']==b['gpr']
            if idx:
                prev=contexts[idx-1];src=successful_load.get(prev['begin']['context'])
                if src and prev['begin']['phase']==b['phase'] and src['rt']==rt:
                    certificates.append({'phase':b['phase'],'load_context':prev['begin']['context'],'store_context':b['context'],'source':src['read']['address'],'destination':w['address'],'value':w['value'],'load_opcode':'LW' if src['opcode']==0x23 else 'LWU'})
    return contexts,certificates


def naive_value_matches(data):
    out=[]
    for w in data['scalar_events']:
        if not (w['write'] and w['uncached_cpu'] and w['bytes']==4): continue
        reads=[r for r in data['scalar_events'] if not r['write'] and r['ordinal']<w['ordinal'] and r['uncached_cpu'] and r['bytes']==4 and (r['value']&0xffffffff)==(w['value']&0xffffffff)]
        if reads: out.append((w['phase'],reads[-1]['address'],w['address']))
    return out


def verify(data):
    contexts,certs=replay(data)
    assert [(c['phase'],c['load_opcode'],c['source'],c['destination']) for c in certs]==[(1,'LW',0x1000,0x2000),(2,'LWU',0x1000,0x2004)]
    phases={p:[] for p in range(1,7)}
    for c in contexts: phases[c['begin']['phase']].append(c)
    assert [len(phases[p]) for p in range(1,7)]==[2,2,3,3,3,1]
    assert not phases[6][0]['scalars']
    f=data['facts'];assert f['d1']==f['d2']==f['d3']==0x89abcdef and f['d4']==0x1234 and f['d5']==0x89abcdef
    assert f['t0_lw']==0xffffffff89abcdef and f['t0_lwu']==0x89abcdef and f['failed_t0']==0xfeedface and f['final_exception']==4
    naive=naive_value_matches(data)
    assert any(p==3 and src==0x1100 for p,src,_ in naive)
    assert any(p==4 for p,_,_ in naive) and any(p==5 for p,_,_ in naive)
    return {'certificates':certs,'naive_value_matches':naive}


def negative(data):
    x=copy.deepcopy(data);next(e for e in x['scalar_events'] if e['phase']==1 and not e['write'])['address']=0x1100
    try: replay(x)
    except AssertionError: pass
    else: raise AssertionError('forged load address accepted')
    x=copy.deepcopy(data);e=next(e for e in x['instruction_events'] if e['phase']==1 and e['begin'] and ((e['word']>>26)&63)==0x2b);e['word']=(e['word']&~(31<<16))|(9<<16)
    end=next(z for z in x['instruction_events'] if not z['begin'] and z['context']==e['context']);end['word']=e['word']
    try: replay(x)
    except AssertionError: pass
    else: raise AssertionError('forged SW source register accepted')
    x=copy.deepcopy(data);b=next(e for e in x['instruction_events'] if e['phase']==6 and e['begin']);fake={'ordinal':b['ordinal']+1,'context':b['context'],'phase':6,'pc':b['pc'],'write':False,'address':0x1001,'bytes':4,'uncached_cpu':True,'value':0x89abcdef}
    for coll in (x['instruction_events'],x['scalar_events']):
        for e in coll:
            if e['ordinal']>b['ordinal']: e['ordinal']+=1
    x['scalar_events'].append(fake);x['scalar_events'].sort(key=lambda e:e['ordinal'])
    try: replay(x)
    except AssertionError: pass
    else: raise AssertionError('forged failed-load transaction accepted')
    print('PASS three forged transaction/instruction histories rejected',flush=True)


def worker():
    builder=load_builder();assert builder.REV==REV
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REF,text=True).strip()==REV
    subprocess.run(['git','-c','core.autocrlf=true','diff','--quiet','HEAD'],cwd=REF,check=True)
    base=builder.build(HERE/'baseline.cpp',OUTPUT/'baseline',extra_sources=(HERE/'driver.cpp',HERE/'observer.hpp',HERE/'prepare.py'))
    traced_exe=sensor(builder)
    base_raw=subprocess.check_output([str(base),'plain'],text=True,timeout=30)
    plain_raw=subprocess.check_output([str(traced_exe),'plain'],text=True,timeout=30)
    traced_raw=subprocess.check_output([str(traced_exe),'traced'],text=True,timeout=30)
    repeat_raw=subprocess.check_output([str(traced_exe),'traced'],text=True,timeout=30)
    assert traced_raw==repeat_raw
    basej,plain,traced=map(json.loads,(base_raw,plain_raw,traced_raw))
    assert not basej['instruction_events'] and not basej['scalar_events'] and not plain['instruction_events'] and not plain['scalar_events']
    assert basej['facts']==plain['facts']==traced['facts'] and basej['state']==plain['state']==traced['state']
    resolved=verify(traced);negative(traced)
    result={'revision':REV,'baseline_equal':True,'repeat_equal':True,'raw':traced,'resolved':resolved}
    OUTPUT.mkdir(parents=True,exist_ok=True);path=OUTPUT/'results.json';path.write_text(json.dumps(result,indent=2)+'\n')
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)
    print('PASS exact interpreted adjacent LW/LWU->SW dataflow; equal-value decoy/clobber/gap and failed load stay uncertified',flush=True)


def main():
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip();subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script],check=True)
    else: worker()

if __name__=='__main__':main()
