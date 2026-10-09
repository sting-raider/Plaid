"""Execute a bounded exact-ares LW/LWU -> XORI -> SW provenance experiment."""
from pathlib import Path
import copy, hashlib, importlib.util, json, os, subprocess
from prepare import generate

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REF=ROOT/'.refs/ares'
OUTPUT=ROOT/'target/ares-cpu-xori-transform-spike'
REV='9408cb43d4948fc3ea6e152a307a34348df3fe04'


def load_builder():
    spec=importlib.util.spec_from_file_location('builder',ROOT/'spikes/003-ares-oracle/run.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def source_guard():
    decoder=(REF/'ares/n64/cpu/interpreter.cpp').read_text(encoding='utf-8')
    ipu=(REF/'ares/n64/cpu/interpreter-ipu.cpp').read_text(encoding='utf-8')
    assert 'op(0x0e, XORI, RT, RS, IMMu16);' in decoder
    assert 'auto CPU::XORI(r64& rt, cr64& rs, u16 imm) -> void {\n  rt.u64 = rs.u64 ^ imm;\n}' in ipu
    assert 'op(0x23, LW, RT, RS, IMMi16);' in decoder
    assert 'op(0x27, LWU, RT, RS, IMMi16);' in decoder
    assert 'op(0x2b, SW, RT, RS, IMMi16);' in decoder


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

def decode(word):
    return {'op':(word>>26)&63,'rs':(word>>21)&31,'rt':(word>>16)&31,'simm':simm16(word),'uimm':word&0xffff}


def ordered_contexts(data):
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
    return contexts


def replay(data):
    contexts=ordered_contexts(data)
    loads={}; transforms={}; certificates=[]
    for idx,c in enumerate(contexts):
        b,z=c['begin'],c['end'];d=decode(b['word']);sc=c['scalars'];assert z['gpr'][0]==0
        if d['op'] in (0x23,0x27):
            reads=[e for e in sc if not e['write'] and e['uncached_cpu'] and e['bytes']==4]
            if len(reads)==1:
                r=reads[0];assert r['address']==paddr((b['gpr'][d['rs']]+d['simm'])&0xffffffffffffffff)
                value=sx32(r['value']) if d['op']==0x23 else r['value']&0xffffffff
                assert z['gpr'][d['rt']]==value
                for n in range(1,32):
                    if n!=d['rt']: assert z['gpr'][n]==b['gpr'][n]
                loads[b['context']]={'rt':d['rt'],'read':r,'opcode':d['op'],'phase':b['phase']}
            else:
                assert not reads
        elif d['op']==0x0e:
            assert not sc
            expected=(b['gpr'][d['rs']] ^ d['uimm']) & 0xffffffffffffffff
            if d['rt']:
                assert z['gpr'][d['rt']]==expected
                for n in range(1,32):
                    if n!=d['rt']: assert z['gpr'][n]==b['gpr'][n]
            else:
                assert z['gpr']==b['gpr']
            transforms[b['context']]={'rs':d['rs'],'rt':d['rt'],'imm':d['uimm'],'phase':b['phase'],'result':expected}
        elif d['op']==0x2b:
            writes=[e for e in sc if e['write'] and e['uncached_cpu'] and e['bytes']==4];assert len(writes)==1
            w=writes[0];assert w['address']==paddr((b['gpr'][d['rs']]+d['simm'])&0xffffffffffffffff) and w['value']==(b['gpr'][d['rt']]&0xffffffff)
            assert z['gpr']==b['gpr']
            if idx>=2:
                lc,tc=contexts[idx-2],contexts[idx-1]
                src=loads.get(lc['begin']['context']);tr=transforms.get(tc['begin']['context'])
                if src and tr and lc['begin']['phase']==tc['begin']['phase']==b['phase'] and src['rt']==tr['rs']==tr['rt']==d['rt']:
                    mask=tr['imm']
                    byte_expr=[]
                    for off in range(4):
                        shift=8*(3-off)
                        byte_expr.append({'destination':w['address']+off,'source':src['read']['address']+off,'xor':(mask>>shift)&0xff})
                    certificates.append({'phase':b['phase'],'load_context':lc['begin']['context'],'transform_context':tc['begin']['context'],'store_context':b['context'],'source':src['read']['address'],'destination':w['address'],'source_word':src['read']['value']&0xffffffff,'xor_imm':mask,'result_word':w['value']&0xffffffff,'load_opcode':'LW' if src['opcode']==0x23 else 'LWU','byte_expr':byte_expr})
    return contexts,certificates


def naive_transform_matches(data):
    contexts=ordered_contexts(data);out=[]
    for idx,c in enumerate(contexts):
        d=decode(c['begin']['word'])
        if d['op']!=0x2b or idx==0: continue
        prev=contexts[idx-1];pd=decode(prev['begin']['word'])
        if pd['op']!=0x0e: continue
        writes=[e for e in c['scalars'] if e['write'] and e['uncached_cpu'] and e['bytes']==4]
        if len(writes)!=1: continue
        w=writes[0];matches=[]
        for earlier in contexts[:idx-1]:
            for r in earlier['scalars']:
                if not r['write'] and r['uncached_cpu'] and r['bytes']==4 and (((r['value']&0xffffffff)^pd['uimm'])&0xffffffff)==(w['value']&0xffffffff):
                    matches.append(r['address'])
        if matches: out.append({'phase':c['begin']['phase'],'sources':matches,'destination':w['address']})
    return out


def verify(data):
    contexts,certs=replay(data)
    got=[(c['phase'],c['load_opcode'],c['source'],c['destination'],c['xor_imm'],c['result_word']) for c in certs]
    expected=[
      (1,'LW',0x1000,0x2000,0x00ff,0x89abcd10),
      (2,'LWU',0x1000,0x2004,0xf00f,0x89ab3de0),
      (3,'LW',0x1000,0x2008,0x0000,0x12345678),
      (4,'LW',0x1000,0x200c,0x00ff,0x89abcd10),
    ]
    assert got==expected
    phases={p:[] for p in range(1,8)}
    for c in contexts: phases[c['begin']['phase']].append(c)
    assert [len(phases[p]) for p in range(1,8)]==[3,3,3,4,3,3,1]
    assert not phases[7][0]['scalars']
    f=data['facts']
    assert f['d1']==0x89abcd10 and f['d2']==0x89ab3de0 and f['d3']==0x12345678
    assert f['d4']==f['d5']==0x89abcd10 and f['d6']==0x1234
    assert f['p1']==0xffffffff89abcd10 and f['p2']==0x89ab3de0 and f['p3']==0x12345678
    assert f['failed_t0']==0xfeedface and f['final_exception']==4
    zero=next(c for c in certs if c['phase']==3)
    assert zero['load_context']!=zero['transform_context']!=zero['store_context'] and zero['xor_imm']==0
    assert [e['xor'] for e in next(c for c in certs if c['phase']==1)['byte_expr']]==[0,0,0,0xff]
    assert [e['xor'] for e in next(c for c in certs if c['phase']==2)['byte_expr']]==[0,0,0xf0,0x0f]
    naive=naive_transform_matches(data)
    p4=next(x for x in naive if x['phase']==4);assert set(p4['sources'])=={0x1000,0x1100}
    p5=next(x for x in naive if x['phase']==5);assert 0x1000 in p5['sources'] and not any(c['phase']==5 for c in certs)
    return {'certificates':certs,'naive_transform_matches':naive}


def negative(data):
    # Wrong backing address cannot be repaired by matching payload bits.
    x=copy.deepcopy(data);next(e for e in x['scalar_events'] if e['phase']==1 and not e['write'])['address']=0x1100
    try: replay(x)
    except AssertionError: pass
    else: raise AssertionError('forged load address accepted')
    # Forge XORI source register while preserving the observed post-state/write.
    x=copy.deepcopy(data);b=next(e for e in x['instruction_events'] if e['phase']==1 and e['begin'] and decode(e['word'])['op']==0x0e);b['word']=(b['word']&~(31<<21))|(9<<21)
    end=next(e for e in x['instruction_events'] if not e['begin'] and e['context']==b['context']);end['word']=b['word']
    try: replay(x)
    except AssertionError: pass
    else: raise AssertionError('forged XORI source register accepted')
    # Forge the SW source register while keeping the completed sink unchanged.
    x=copy.deepcopy(data);b=next(e for e in x['instruction_events'] if e['phase']==1 and e['begin'] and decode(e['word'])['op']==0x2b);b['word']=(b['word']&~(31<<16))|(9<<16)
    end=next(e for e in x['instruction_events'] if not e['begin'] and e['context']==b['context']);end['word']=b['word']
    try: replay(x)
    except AssertionError: pass
    else: raise AssertionError('forged SW source register accepted')
    # Fabricate a successful read inside the failed misaligned load.
    x=copy.deepcopy(data);b=next(e for e in x['instruction_events'] if e['phase']==7 and e['begin']);fake={'ordinal':b['ordinal']+1,'context':b['context'],'phase':7,'pc':b['pc'],'write':False,'address':0x1001,'bytes':4,'uncached_cpu':True,'value':0x89abcdef}
    for coll in (x['instruction_events'],x['scalar_events']):
        for e in coll:
            if e['ordinal']>b['ordinal']: e['ordinal']+=1
    x['scalar_events'].append(fake);x['scalar_events'].sort(key=lambda e:e['ordinal'])
    try: replay(x)
    except AssertionError: pass
    else: raise AssertionError('forged failed-load transaction accepted')
    print('PASS four forged transaction/instruction histories rejected',flush=True)


def worker():
    builder=load_builder();assert builder.REV==REV
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REF,text=True).strip()==REV
    subprocess.run(['git','-c','core.autocrlf=true','diff','--quiet','HEAD'],cwd=REF,check=True)
    source_guard()
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
    print('PASS exact interpreted LW/LWU->XORI->SW transformed provenance; zero-transform generation retained and adversarial equal-value chains fail closed',flush=True)


def main():
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip();subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script],check=True)
    else: worker()

if __name__=='__main__':main()
