"""Actual equal RSP DMEM stores preserve behavior and revoke older SP parents."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/dmem-storage-cuts-primary'


def verify_controls(results,checkpoints,extra_cpu_imem_reads=0):
    states=results['baseline']['plain']['states'];assert len(states)==checkpoints
    assert all(result['states']==states for modes in results.values() for result in modes.values())
    assert all(not result['events'] for result in results['baseline'].values())
    assert not results['sensor']['plain']['events']
    source=results['sensor']['traced'];assert source==results['sensor']['repeat']
    assert [e['ordinal'] for e in source['events']]==list(range(1,len(source['events'])+1))
    for phase in (0,1):
        rows=[e for e in source['events'] if e['phase']==phase]
        cuts=[e for e in rows if e['record']=='rsp_dmem_effect']
        # The pin implements SW through four completed Byte effects, even aligned.
        expected=[(0,4,0x24100007),(4,4,0)]+[(n,1,v) for n,v in enumerate(bytes.fromhex('24100007'))]
        assert [(e['offset'],e['bytes'],e['value']) for e in cuts]==expected
        installs=[e for e in rows if e['record']=='sp_dma_store' and e['bank']==0]
        assert len(installs)==2
        for cut,install in zip(cuts[:2],installs,strict=True):
            assert cut['ordinal']+1==install['ordinal'] and cut['value']==install['value']
        fetches=[e for e in rows if e['record']=='sp_word']
        expected_fetches=[(0x04001000,0x24100007),(0x04000000,0x24100007),
            (0x04000000,0x24100007),(0x04001000,0x24100007)]+[(0x04001000,0x24100007)]*extra_cpu_imem_reads
        assert [(e['address'],e['value']) for e in fetches]==expected_fetches
        assert fetches[1]['ordinal']<cuts[-1]['ordinal']<fetches[2]['ordinal']
    return states,source


def main():
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(HERE/'run.py')],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script,*sys.argv[1:]],check=True);return
    spec=importlib.util.spec_from_file_location('builder',ROOT/'spikes/003-ares-oracle/run.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if '--verify-existing' not in sys.argv:
        for name,sensor in [('baseline',False),('sensor',True)]:
            print('Building',name,flush=True)
            executable=builder.build(HERE/('driver.cpp' if sensor else 'baseline.cpp'),OUTPUT/name,
                raw_fetch_access=True,physical_fetch_access=True,pi_dma_access=sensor,rdram_scalar_access=sensor,
                memory_mutation_access=sensor,sp_backing_access=sensor,rsp_dmem_access=sensor,
                extra_sources=[HERE/'driver.cpp',ROOT/'spikes/088-pi-storage-executable/driver.cpp',
                    ROOT/'spikes/089-pi-dma-sp-consumption/driver.cpp',ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp',
                    ROOT/'spikes/006-ares-rom-source/driver.cpp'])
            for mode in ('plain','traced','repeat'):
                (OUTPUT/f'{name}-{mode}.json').write_bytes(subprocess.check_output([str(executable),
                    'plain' if mode=='plain' else 'traced'],timeout=60))
    results={name:{mode:json.loads((OUTPUT/f'{name}-{mode}.json').read_bytes())
        for mode in ('plain','traced','repeat')} for name in ('baseline','sensor')}
    states,source=verify_controls(results,22)
    artifacts={f'{name}-{mode}.json':hashlib.sha256((OUTPUT/f'{name}-{mode}.json').read_bytes()).hexdigest()
        for name in ('baseline','sensor') for mode in ('plain','traced','repeat')}
    for name in ('baseline','sensor'):
        for filename in ('oracle','build.json'):
            path=OUTPUT/name/filename;artifacts[str(path.relative_to(OUTPUT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt=dict(format='plaid-dmem-storage-cut-receipt-v0',revision=builder.REV,records=len(source['events']),
        checkpoints=len(states),controls_equal=True,repeat_equal=True,artifacts=artifacts,
        source_sha256=artifacts['sensor-traced.json'],rsp_producer_ancestry_certified=False,
        mutation_census_certified=False,executable_lifetime_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('PASS actual lower DMEM writes/equal decoded RSP store and CPU DMEM/IMEM consumption controls',flush=True)
    print(json.dumps(receipt,sort_keys=True),flush=True)


if __name__=='__main__':main()
