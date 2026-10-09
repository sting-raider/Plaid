"""Build exact-reference baseline and original SP callback shadows separately."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from prepare import generate

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REF=ROOT/'.refs/ares'
OUTPUT=ROOT/'target/ares-cpu-sp-fetch-spike'


def load_builder():
    spec=importlib.util.spec_from_file_location('sp_builder',ROOT/'spikes/003-ares-oracle/run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def sensor(builder):
    inputs=(HERE/'driver.cpp',HERE/'observer.hpp',HERE/'prepare.py',Path(builder.__file__))
    key=hashlib.sha256(b''.join(p.read_bytes() for p in inputs)).hexdigest()
    out=OUTPUT/('sensor-'+key[:12]);exe=out/'oracle-traced'
    if exe.exists():return exe
    builder.build(HERE/'baseline.cpp',out,raw_fetch_access=True,physical_fetch_access=True,
        rdram_scalar_access=True,fetch_boundary_access=True,extra_sources=inputs)
    generate(REF,out)
    flags=['-O1','-std=c++20','-msse4.1','-DSLJIT_HAVE_CONFIG_PRE=1','-DSLJIT_HAVE_CONFIG_POST=1','-DPLAID_SP_SENSOR=1']
    includes=[out/'include',*(REF/p for p in ('ares','nall','.','thirdparty','thirdparty/xxhash','ares/n64/system'))]
    include_flags=[part for p in includes for part in ('-I',str(p))]
    sources=[HERE/'driver.cpp',out/'core.cpp',out/'n64.cpp',REF/'ares/component/processor/sm5k/sm5k.cpp',
        REF/'ares/ares/memory/fixed-allocator.cpp',REF/'nall/nall/nall.cpp',REF/'thirdparty/sljitAllocator.cpp']
    with (out/'sensor-build.log').open('w',encoding='utf-8') as log:
        try:
            subprocess.run(['g++',*flags,*include_flags,*map(str,sources),str(out/'sljit.o'),str(out/'libco.o'),
                '-pthread','-ldl','-o',str(exe)],check=True,stdout=log,stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print('\n'.join((out/'sensor-build.log').read_text(encoding='utf-8').splitlines()[-35:]),flush=True)
            raise
    return exe


def check(events):
    assert [e['ordinal'] for e in events]==list(range(1,len(events)+1))
    active=pending=None
    reads=[];samples=[];mutations=[];dma_reads=[];dma_links=[]
    for e in events:
        assert type(e['cpu']) is bool and type(e['cached']) is bool
        kind=e['kind']
        if pending is not None:assert kind=='fetch'
        if kind=='begin':
            assert active is None and pending is None and e['context']==e['ordinal'] and e['value']==0
            active=e;reads=[]
        elif kind=='end':
            assert active is not None
            assert all(e[k]==active[k] for k in ('context','pc','phase','address','cached','translated'))
            pending=(e,reads);active=None
        elif kind=='fetch':
            assert pending is not None and active is None
            end,within=pending
            assert all(e[k]==end[k] for k in ('context','pc','phase','address','cached','value'))
            eligible=[r for r in within if r['cpu'] and r['bytes']==4 and r['address']==e['address']]
            witness=None
            if not e['cached'] and len(eligible)==1:
                r=eligible[0];assert r['value']==e['value']
                witness=dict(bank=r['bank'],offset=r['offset'],read_ordinal=r['ordinal'])
            samples.append(dict(phase=e['phase'],physical=e['address'],pc=e['pc'],word=e['value'],
                cached=e['cached'],witness=witness));pending=None
        else:
            assert e['context']==(active['ordinal'] if active else 0)
            if active is not None:assert e['pc']==active['pc'] and e['phase']==active['phase']
            if kind in ('sp_read','sp_write'):
                assert 0x04000000<=e['address']<=0x0403ffff and e['bytes']==4
                assert e['bank']==(e['address']>>12&1) and e['offset']==e['address']&0xffc
                assert 0<=e['value']<1<<32 and not e['cached']
                if kind=='sp_read' and active is not None:reads.append(e)
                if kind=='sp_write':mutations.append(e)
            elif kind=='dma_read':
                assert e['device']==4 and e['bytes'] in (4,8) and e['context']==0
                dma_reads.append(e)
            else:
                assert kind=='dma_store' and e['bank'] in (0,1) and e['bytes'] in (4,8) and e['context']==0
                assert e['offset']<4096 and e['offset']%e['bytes']==0
                matching=[r for r in dma_reads if all(r[k]==e[k] for k in ('phase','address','bytes','value'))]
                assert len(matching)==1
                r=matching[0];dma_reads.remove(r)
                dma_links.append(dict(bank=e['bank'],offset=e['offset'],bytes=e['bytes'],
                    dram=e['address'],read_ordinal=r['ordinal'],write_ordinal=e['ordinal']))
    assert active is pending is None and not dma_reads
    return dict(samples=samples,mutations=mutations,dma_links=dma_links,
        mutation_coverage_certified=False,executable_lifetime_certified=False,native_complete=False)


def verify(data):
    result=check(data['events'])
    samples={s['phase']:s for s in result['samples']}
    assert len(samples)==len(result['samples'])==18
    for n in (1,2,3,4,5,6,8,10,12,14,16,18):assert samples[n]['witness'] is not None
    for n in (7,9,11,17,19,20):assert samples[n]['witness'] is None
    assert samples[1]['witness']['bank']==samples[3]['witness']['bank']==0
    assert samples[2]['witness']['bank']==samples[4]['witness']['bank']==1
    assert samples[1]['physical']!=samples[3]['physical'] and samples[1]['word']==samples[3]['word']
    assert samples[2]['physical']!=samples[4]['physical'] and samples[2]['word']==samples[4]['word']
    assert samples[20]['cached'] and data['state']['frozen'] and data['state']['exception']==0
    assert samples[8]['word']==samples[10]['word']==samples[12]['word']==0x34083333
    assert samples[14]['word']==0x34084444 and samples[16]['word']==0x34085555 and samples[18]['word']==0x34086666
    assert len(result['dma_links'])==3 and len(result['mutations'])==4
    assert [m['phase'] for m in result['mutations']]==[7,9,11,17]
    sb=result['mutations'][-1]
    assert sb['address']==0x04001003 and sb['offset']==0 and sb['bytes']==4 and sb['value']==0x34086666
    assert result['mutations'][0]['value']==result['mutations'][1]['value']
    assert result['mutations'][0]['ordinal']!=result['mutations'][1]['ordinal']
    return result


def negative(events):
    for field,value in [('bank',1),('offset',4),('context',0),('value',0),('cached',True)]:
        changed=copy.deepcopy(events)
        next(e for e in changed if e['kind']=='sp_read')[field]=value
        try:check(changed)
        except AssertionError:continue
        raise AssertionError('forged SP read accepted: '+field)
    changed=copy.deepcopy(events)
    next(e for e in changed if e['kind']=='dma_store')['value']^=1
    try:check(changed)
    except AssertionError:pass
    else:raise AssertionError('forged DMA sink accepted')
    changed=copy.deepcopy(events);changed[1]['ordinal']=1
    try:check(changed)
    except AssertionError:pass
    else:raise AssertionError('duplicate ordinal accepted')
    print('PASS seven forged read/sink/order histories',flush=True)


def worker():
    builder=load_builder()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REF,text=True).strip()==builder.REV
    subprocess.run(['git','-c','core.autocrlf=true','diff','--quiet','HEAD'],cwd=REF,check=True)
    baseline=builder.build(HERE/'baseline.cpp',OUTPUT/'baseline',extra_sources=(HERE/'driver.cpp',))
    exe=sensor(builder)
    def parse(raw):
        lines=raw.splitlines()
        assert lines[:-1]==['\x1b[96m[unusual] \x1b[0m[Bus::freezeUncached] CPU frozen because of cached access to non-RDRAM area: 0x04000000 (PC: 84000000)']
        return json.loads(lines[-1])
    original=parse(subprocess.check_output([str(baseline),'plain'],text=True,timeout=30))
    outputs=[subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ('plain','traced','traced')]
    plain,traced,repeat=map(parse,outputs)
    assert outputs[1]==outputs[2]
    assert original['state']==plain['state']==traced['state']==repeat['state']
    assert original['checkpoints']==plain['checkpoints']==traced['checkpoints']==repeat['checkpoints']
    assert not original['events'] and not plain['events']
    resolved=verify(traced);negative(traced['events'])
    result=dict(raw=traced,resolved=resolved,baseline_equal=True,repeat_equal=True)
    path=OUTPUT/'results.json';path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)
    print('PASS actual CPU SP read/fetch and CPU/DMA mutations; cached/IO paths remain unwitnessed',flush=True)


def main():
    if os.name=='nt':
        path=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path],check=True)
    else:worker()


if __name__=='__main__':main()
