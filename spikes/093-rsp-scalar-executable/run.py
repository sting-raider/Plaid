"""Actual rooted ORI/ADDU snapshots at existing exact RSP read occurrences."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/rsp-scalar-executable-primary'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(HERE/'run.py')],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script,*sys.argv[1:]],check=True);return
    builder=load('builder',ROOT/'spikes/003-ares-oracle/run.py');model=load('scalar',HERE/'verify.py')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if '--verify-existing' not in sys.argv:
        for name,sensor in [('baseline',False),('sensor',True)]:
            print('Building',name,flush=True)
            executable=builder.build(HERE/('driver.cpp' if sensor else 'baseline.cpp'),OUTPUT/name,
                raw_fetch_access=True,physical_fetch_access=True,pi_dma_access=sensor,rdram_scalar_access=sensor,
                memory_mutation_access=sensor,sp_backing_access=sensor,rsp_dmem_access=sensor,rsp_instruction_fetch_access=sensor,
                extra_sources=[HERE/'driver.cpp',ROOT/'spikes/088-pi-storage-executable/driver.cpp',ROOT/'spikes/089-pi-dma-sp-consumption/driver.cpp',
                    ROOT/'spikes/090-rsp-dmem-storage-cuts/driver.cpp',ROOT/'spikes/091-raw-rsp-executable-consumption/driver.cpp',ROOT/'spikes/092-imem-storage-cuts/driver.cpp',
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
    assert facts['roots']>0 and facts['definitions']>0
    assert any(r['definition']['expression']['kind']=='addu' for r in facts['samples'])
    reads={r['ordinal']:r for r in events if r['record']=='rsp_imem_read'}
    for sample in facts['samples']:
        definition=sample['definition'];read=reads[sample['read_ordinal']]
        assert read['word']==definition['word'] and read['offset']==definition['pc']&0xffc
    artifacts={f'{name}-{mode}.json':hashlib.sha256((OUTPUT/f'{name}-{mode}.json').read_bytes()).hexdigest() for name in ('baseline','sensor') for mode in ('plain','traced','repeat')}
    for name in ('baseline','sensor'):
        for f in ('oracle','build.json'):artifacts[f'{name}/{f}']=hashlib.sha256((OUTPUT/name/f).read_bytes()).hexdigest()
    receipt=dict(format='plaid-rsp-scalar-executable-receipt-v0',revision=builder.REV,records=len(events),checkpoints=len(base['states']),
        roots=facts['roots'],instructions=facts['instructions'],definitions=facts['definitions'],opaque_instructions=facts['opaque_instructions'],
        ordered_producers_sha256=facts['ordered_producers_sha256'],controls_equal=True,repeat_equal=True,artifacts=artifacts,
        source_sha256=artifacts['sensor-traced.json'],mutation_census_certified=False,executable_lifetime_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('PASS actual read-bound rooted ORI/ADDU producer snapshots and complete machine/backing controls',flush=True)
    print(json.dumps(receipt,sort_keys=True),flush=True)
if __name__=='__main__':main()
