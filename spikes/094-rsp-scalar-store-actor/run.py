"""Actual rooted ORI/ADDU snapshots at existing exact RSP read occurrences."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/rsp-scalar-store-actor-primary'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(HERE/'run.py')],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script,*sys.argv[1:]],check=True);return
    builder=load('builder',ROOT/'spikes/003-ares-oracle/run.py');model=load('scalar',ROOT/'spikes/093-rsp-scalar-executable/verify.py')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if '--verify-existing' not in sys.argv:
        for name,sensor in [('baseline',False),('sensor',True)]:
            print('Building',name,flush=True)
            executable=builder.build(HERE/('driver.cpp' if sensor else 'baseline.cpp'),OUTPUT/name,
                raw_fetch_access=True,physical_fetch_access=True,pi_dma_access=sensor,rdram_scalar_access=sensor,
                memory_mutation_access=sensor,sp_backing_access=sensor,rsp_dmem_access=sensor,rsp_instruction_fetch_access=sensor,rsp_scalar_store_access=sensor,
                extra_sources=[HERE/'driver.cpp',ROOT/'spikes/088-pi-storage-executable/driver.cpp',ROOT/'spikes/089-pi-dma-sp-consumption/driver.cpp',
                    ROOT/'spikes/090-rsp-dmem-storage-cuts/driver.cpp',ROOT/'spikes/091-raw-rsp-executable-consumption/driver.cpp',ROOT/'spikes/092-imem-storage-cuts/driver.cpp',ROOT/'spikes/093-rsp-scalar-executable/driver.cpp',
                    ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp',ROOT/'spikes/006-ares-rom-source/driver.cpp'])
            for mode in ('plain','traced','repeat'):
                (OUTPUT/f'{name}-{mode}.json').write_bytes(subprocess.check_output([str(executable),'plain' if mode=='plain' else 'traced'],timeout=60))
    results={name:{mode:json.loads((OUTPUT/f'{name}-{mode}.json').read_bytes()) for mode in ('plain','traced','repeat')} for name in ('baseline','sensor')}
    base=results['baseline']['plain']
    for name in results:
        for mode,run in results[name].items():
            assert run['states']==base['states']
            if name=='baseline' or mode=='plain':assert run['events']==[]
    assert results['sensor']['traced']==results['sensor']['repeat']
    events=results['sensor']['traced']['events']
    assert [r['ordinal'] for r in events]==list(range(1,len(events)+1))
    facts=model.inspect(events)
    active=None;scope=None;remaining=[];matched=0
    for row in events:
        if row['record']=='rsp_instruction':
            if row['begin']:active=row
            else:assert scope is None;active=None
        elif row['record']=='rsp_scalar_store_scope':
            assert active and row['instruction_context']==active['ordinal']
            assert row['kind'] in (0,1,2) and active['word']>>26==(0x28,0x29,0x2b)[row['kind']]
            if row['begin']:
                assert scope is None and row['store_scope']==row['ordinal'];scope=row['ordinal']
                registers=active['registers'];word=active['word'];width=(1,2,4)[row['kind']]
                immediate=word&65535;immediate=immediate-65536 if immediate&32768 else immediate
                address=(registers[(word>>21)&31]+immediate)&0xffffffff
                value=registers[(word>>16)&31]
                remaining=[((address+i)&4095,(value>>(8*(width-1-i)))&255) for i in range(width)]
            else:assert scope==row['store_scope'] and not remaining;scope=None
        elif row['record']=='rsp_dmem_effect':
            assert row['store_scope']==(scope or 0)
            if scope:
                assert row['bytes']==1 and (row['offset'],row['value'])==remaining.pop(0);matched+=1
    assert active is None and scope is None and matched==8

    assert facts['roots']>0 and facts['definitions']>0
    assert any(r['definition']['expression']['kind']=='addu' for r in facts['samples'])
    reads={r['ordinal']:r for r in events if r['record']=='rsp_imem_read'}
    for sample in facts['samples']:
        definition=sample['definition'];read=reads[sample['read_ordinal']]
        assert read['word']==definition['word'] and read['offset']==definition['pc']&0xffc
    artifacts={f'{name}-{mode}.json':hashlib.sha256((OUTPUT/f'{name}-{mode}.json').read_bytes()).hexdigest() for name in ('baseline','sensor') for mode in ('plain','traced','repeat')}
    for name in ('baseline','sensor'):
        for f in ('oracle','build.json'):artifacts[f'{name}/{f}']=hashlib.sha256((OUTPUT/name/f).read_bytes()).hexdigest()
    receipt=dict(format='plaid-rsp-scalar-store-actor-receipt-v0',revision=builder.REV,records=len(events),checkpoints=len(base['states']),
        scalar_store_effects=matched,roots=facts['roots'],instructions=facts['instructions'],definitions=facts['definitions'],opaque_instructions=facts['opaque_instructions'],
        ordered_producers_sha256=facts['ordered_producers_sha256'],controls_equal=True,repeat_equal=True,artifacts=artifacts,
        source_sha256=artifacts['sensor-traced.json'],mutation_census_certified=False,executable_lifetime_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('PASS actual scalar store method actors, exact caller/effect lanes, rooted snapshots and complete machine/backing controls',flush=True)
    print(json.dumps(receipt,sort_keys=True),flush=True)
if __name__=='__main__':main()
