"""Build and execute exact pinned ares RSP-DMEM -> CPU-SP refetch composition."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
from prepare import generate

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REF=ROOT/'.refs/ares'
OUTPUT=ROOT/'target/ares-rsp-dmem-cpu-refetch'


def load_builder():
    spec=importlib.util.spec_from_file_location('mix_builder',ROOT/'spikes/003-ares-oracle/run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def build_sensor(builder):
    inputs=(HERE/'driver.cpp',HERE/'observer.hpp',HERE/'prepare.py',Path(builder.__file__),
            ROOT/'spikes/039-ares-cpu-sp-fetch/prepare.py',ROOT/'spikes/042-ares-rsp-dmem-history/prepare.py')
    key=hashlib.sha256(b''.join(p.read_bytes() for p in inputs)).hexdigest()
    out=OUTPUT/('sensor-'+key[:12]);exe=out/'oracle-mixed'
    if exe.exists(): return exe
    builder.build(HERE/'driver.cpp',out,raw_fetch_access=True,physical_fetch_access=True,
        fetch_boundary_access=True,extra_sources=inputs)
    generate(REF,out)
    flags=['-O1','-std=c++20','-msse4.1','-DSLJIT_HAVE_CONFIG_PRE=1','-DSLJIT_HAVE_CONFIG_POST=1','-DPLAID_COMPOSE_SENSOR=1']
    includes=[out/'include',*(REF/p for p in ('ares','nall','.','thirdparty','thirdparty/xxhash','ares/n64/system'))]
    include_flags=[part for p in includes for part in ('-I',str(p))]
    sources=[HERE/'driver.cpp',out/'core.cpp',out/'n64.cpp',REF/'ares/component/processor/sm5k/sm5k.cpp',
        REF/'ares/ares/memory/fixed-allocator.cpp',REF/'nall/nall/nall.cpp',REF/'thirdparty/sljitAllocator.cpp']
    with (out/'sensor-build.log').open('w',encoding='utf-8') as log:
        try:
            subprocess.run(['g++',*flags,*include_flags,*map(str,sources),str(out/'sljit.o'),str(out/'libco.o'),
                '-pthread','-ldl','-o',str(exe)],check=True,stdout=log,stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print('\n'.join((out/'sensor-build.log').read_text(encoding='utf-8').splitlines()[-60:]),flush=True)
            raise
    return exe


def bytes_of(value,width):
    return [(value >> (8*(width-1-i))) & 0xff for i in range(width)]


def check(events,initial):
    assert [e['ordinal'] for e in events]==list(range(1,len(events)+1))
    data={i:initial[i] for i in range(8)}
    writer={i:'initial' for i in range(8)}
    rsp_active=None
    fetch_active=None
    fetch_pending=None
    phase_writers={}
    rsp_sinks=[];foreign_sinks=[];cpu_writes=[];reads=[]
    rsp_labels={};foreign_labels={}
    for e in events:
        kind=e['kind']
        if kind=='rsp_begin':
            assert rsp_active is None and e['context']==e['ordinal']
            rsp_active=(e['context'],e['pc'],e['word'])
        elif kind=='rsp_end':
            assert rsp_active is not None and e['context']==rsp_active[0] and e['pc']==rsp_active[1] and e['word']==rsp_active[2]
            rsp_active=None
        elif kind=='rsp_sink':
            assert rsp_active is not None and e['context']==rsp_active[0] and e['pc']==rsp_active[1] and e['word']==rsp_active[2]
            assert e['bytes'] in (1,2,4,8)
            vals=bytes_of(e['value'],e['bytes']);label=f"rsp:{e['context']}:{e['ordinal']}"
            for i,b in enumerate(vals):
                off=(e['offset']+i)&0xfff
                if off<8: data[off]=b;writer[off]=label
            rsp_sinks.append(e);rsp_labels[e['phase']]=label
        elif kind=='foreign_sink':
            assert rsp_active is None and e['context']==0 and e['bytes'] in (1,2,4,8)
            vals=bytes_of(e['value'],e['bytes']);label=f"unknown:{e['ordinal']}"
            for i,b in enumerate(vals):
                off=(e['offset']+i)&0xfff
                if off<8: data[off]=b;writer[off]=label
            foreign_sinks.append(e);foreign_labels[e['phase']]=label
        elif kind=='cpu_fetch_begin':
            assert fetch_active is None and fetch_pending is None and e['context']==e['ordinal']
            fetch_active=e['context']
        elif kind=='cpu_fetch_end':
            assert fetch_active==e['context'];fetch_pending=fetch_active;fetch_active=None
        elif kind=='cpu_fetch':
            assert fetch_active is None and fetch_pending==e['context'];fetch_pending=None
        elif kind=='sp_write':
            assert e['cpu'] and e['bank']==0 and e['bytes']==4 and e['context']==0
            paired=[s for s in foreign_sinks if s['phase']==e['phase'] and s['offset']==e['offset'] and s['bytes']==e['bytes'] and s['value']==e['value'] and s['ordinal']<e['ordinal']]
            assert len(paired)==1
            vals=bytes_of(e['value'],4);label=f"cpu:{e['ordinal']}"
            for i,b in enumerate(vals):
                off=e['offset']+i
                if off<8:data[off]=b;writer[off]=label
            cpu_writes.append(e)
        elif kind=='sp_read':
            assert e['cpu'] and e['bank']==0 and e['bytes']==4 and fetch_active==e['context']
            vals=[data[e['offset']+i] for i in range(4)]
            assert vals==bytes_of(e['value'],4)
            labels=tuple(writer[e['offset']+i] for i in range(4))
            phase_writers[e['phase']]=labels;reads.append(e)
        else:
            raise AssertionError('unknown event '+kind)
    assert rsp_active is fetch_active is fetch_pending is None
    assert [r['phase'] for r in reads]==[1,3,5,7,9,11,13,15,17]
    assert [s['phase'] for s in rsp_sinks]==[2,4,8,10,12,16]
    assert [s['phase'] for s in foreign_sinks]==[6,14]
    assert [w['phase'] for w in cpu_writes]==[6]
    assert foreign_sinks[0]['ordinal']<cpu_writes[0]['ordinal']

    assert len(set(phase_writers[1]))==1 and phase_writers[1][0]=='initial'
    assert len(set(phase_writers[3]))==1 and phase_writers[3][0]==rsp_labels[2]
    assert len(set(phase_writers[5]))==1 and phase_writers[5][0]==rsp_labels[4]
    assert rsp_labels[4]!=rsp_labels[2]  # same-value RSP SW is a new generation
    assert len(set(phase_writers[7]))==1 and phase_writers[7][0].startswith('cpu:')
    assert phase_writers[9]==phase_writers[7]  # equal-valued neighbor write cannot steal lineage

    cpu_label=phase_writers[7][0]
    assert phase_writers[11]==(cpu_label,cpu_label,cpu_label,rsp_labels[10])
    assert phase_writers[13]==(cpu_label,cpu_label,rsp_labels[12],rsp_labels[10])
    assert phase_writers[15]==(cpu_label,cpu_label,rsp_labels[12],foreign_labels[14])
    assert phase_writers[17]==(cpu_label,cpu_label,rsp_labels[12],rsp_labels[16])
    assert rsp_labels[16]!=rsp_labels[10]  # same-value decoded SB restores a distinct known generation

    return dict(phase_writers={str(k):list(v) for k,v in sorted(phase_writers.items())},
                rsp_sink_ordinals=[e['ordinal'] for e in rsp_sinks],
                foreign_sink_ordinals=[e['ordinal'] for e in foreign_sinks],
                cpu_write_ordinal=cpu_writes[0]['ordinal'])


def naive_value_only(events):
    plausible={0x340800aa,0x34081111,0x34081122,0x34087722}
    return all(e['value'] in plausible for e in events if e['kind']=='sp_read')


def reject_forgeries(events,initial):
    rejected=[];cases=[]
    x=copy.deepcopy(events);x.remove(next(e for e in x if e['kind']=='rsp_sink' and e['phase']==4))
    for n,e in enumerate(x,1):e['ordinal']=n
    cases.append(('delete_same_value_rsp_generation',x,True))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='rsp_sink' and e['phase']==8)['offset']=0;cases.append(('decoy_wrong_offset',x,False))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='rsp_sink' and e['phase']==2)['context']=0;cases.append(('lost_rsp_context',x,False))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='sp_write')['cpu']=False;cases.append(('cpu_writer_flag',x,False))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='foreign_sink' and e['phase']==6)['value']^=1;cases.append(('foreign_sink_pairing',x,False))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='rsp_sink' and e['phase']==10)['offset']=2;cases.append(('partial_rsp_wrong_offset',x,False))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='rsp_sink' and e['phase']==12)['offset']=3;cases.append(('vector_rsp_wrong_offset',x,False))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='foreign_sink' and e['phase']==14)['offset']=4;cases.append(('same_value_foreign_wrong_offset',x,True))
    x=copy.deepcopy(events);next(e for e in x if e['kind']=='sp_read' and e['phase']==5)['value']^=1;cases.append(('forged_read_value',x,False))
    x=copy.deepcopy(events);x[1]['ordinal']=x[0]['ordinal'];cases.append(('duplicate_ordinal',x,False))
    naive_accepted=[]
    for name,history,naive_case in cases:
        if naive_case and naive_value_only(history): naive_accepted.append(name)
        try:check(history,initial)
        except AssertionError: rejected.append(name)
        else: raise AssertionError('forged history accepted: '+name)
    assert naive_accepted==['delete_same_value_rsp_generation','same_value_foreign_wrong_offset']
    return dict(rejected=rejected,naive_value_only_accepts=naive_accepted)


def parse(raw):
    rows=[line for line in raw.splitlines() if line.startswith('{')]
    assert len(rows)==1,raw
    return json.loads(rows[0])


def main():
    if os.name=='nt':
        path=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path],check=True);return
    builder=load_builder()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REF,text=True).strip()==builder.REV=='9408cb43d4948fc3ea6e152a307a34348df3fe04'
    subprocess.run(['git','diff','--quiet','HEAD'],cwd=REF,check=True)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    baseline=builder.build(HERE/'driver.cpp',OUTPUT/'baseline',raw_fetch_access=True,physical_fetch_access=True,
        fetch_boundary_access=True,extra_sources=(HERE/'driver.cpp',))
    sensor=build_sensor(builder)
    original=parse(subprocess.check_output([str(baseline),'plain'],text=True,timeout=30))
    plain=parse(subprocess.check_output([str(sensor),'plain'],text=True,timeout=30))
    traced_raw=subprocess.check_output([str(sensor),'traced'],text=True,timeout=30)
    repeat_raw=subprocess.check_output([str(sensor),'traced'],text=True,timeout=30)
    traced=parse(traced_raw);repeat=parse(repeat_raw)
    assert traced_raw==repeat_raw and traced==repeat
    for key in ('initial_bytes','word0','word4','t0'):
        assert original[key]==plain[key]==traced[key]==repeat[key]
    assert plain['trace']['events']==[] and original['trace']['events']==[]
    assert plain['machine_sha256']==traced['machine_sha256']==repeat['machine_sha256']
    assert traced['word0']==0x34087722 and traced['word4']==0x34081111 and traced['t0']==0x7722
    lineage=check(traced['trace']['events'],traced['initial_bytes'])
    forged=reject_forgeries(traced['trace']['events'],traced['initial_bytes'])
    result=dict(pin=builder.REV,baseline_equal=True,repeat_equal=True,lineage=lineage,forgeries=forged,raw=traced)
    path=OUTPUT/'results.json';path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ('pin','baseline_equal','repeat_equal','lineage','forgeries')},sort_keys=True),flush=True)
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)
    print('PASS exact RSP DMEM generations compose into CPU SP refetch across split and unknown-byte adversaries',flush=True)


if __name__=='__main__':main()
