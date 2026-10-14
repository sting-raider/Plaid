"""Actual PI requests through translated storage to decoded CPU execution."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/pi-storage-executable-primary'


def main():
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(HERE/'run.py')],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script,*sys.argv[1:]],check=True)
        return
    spec=importlib.util.spec_from_file_location('builder',ROOT/'spikes/003-ares-oracle/run.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if '--verify-existing' not in sys.argv:
        for name,sensor in [('baseline',False),('sensor',True)]:
            print('Building',name,flush=True)
            executable=builder.build(HERE/('driver.cpp' if sensor else 'baseline.cpp'),OUTPUT/name,
                raw_fetch_access=True,physical_fetch_access=True,pi_dma_access=sensor,
                rdram_scalar_access=sensor,memory_mutation_access=sensor,
                extra_sources=[HERE/'driver.cpp',ROOT/'spikes/006-ares-rom-source/driver.cpp'])
            for mode in ('plain','traced','repeat'):
                raw=subprocess.check_output([str(executable),'plain' if mode=='plain' else 'traced'],timeout=60)
                (OUTPUT/f'{name}-{mode}.json').write_bytes(raw)
    results={name:{mode:json.loads((OUTPUT/f'{name}-{mode}.json').read_bytes())
        for mode in ('plain','traced','repeat')} for name in ('baseline','sensor')}
    states=results['baseline']['plain']['states']
    for modes in results.values():
        for result in modes.values(): assert result['states']==states
    assert len(states)==8
    assert all(not result['events'] for result in results['baseline'].values())
    assert not results['sensor']['plain']['events']
    trace=results['sensor']['traced']
    assert trace==results['sensor']['repeat']
    assert [e['ordinal'] for e in trace['events']]==list(range(1,len(trace['events'])+1))
    for phase in range(3):
        rows=[e for e in trace['events'] if e['phase']==phase]
        stores=[e for e in rows if e['record']=='storage_effect']
        wrappers=[e for e in rows if e['record']=='scalar' and e['write']]
        halves=[e for e in rows if e['record']=='rom_half']
        assert [(e['offset'],e['value']) for e in halves]==[(0x1000,0x2410),(0x1002,7),(0x1004,0),(0x1006,0)]
        assert len(stores)==(8 if phase<2 else 0)
        assert len(wrappers)==(8 if phase==0 else 0)
        for e in stores:
            i=trace['events'].index(e)
            before=trace['events'][i-1];after=trace['events'][i+1]
            assert (before['record'],before['event'])==('pi_dma',4)
            assert e['kind']==0 and e['bytes']==1 and e['value']==before['value']
            assert e['address']==before['dram']+(0x200000 if phase==1 else 0)
            if phase==0:
                assert after['record']=='scalar' and after['address']==e['address']
                after=trace['events'][i+2]
            assert (after['record'],after['event'])==('pi_dma',5)
        copies=[s for s in states if s['phase']==phase and s['point']=='copied']
        assert copies[0]['ri_error']==int(phase==2)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUTPUT.glob('*.json') if p.name!='receipt.json'}
    for name in ('baseline','sensor'):
        for filename in ('oracle','build.json'):
            path=OUTPUT/name/filename
            hashes[str(path.relative_to(OUTPUT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt=dict(format='plaid-pi-storage-executable-receipt-v0',revision=builder.REV,
        controls_equal=True,repeat_equal=True,checkpoints=len(states),records=len(trace['events']),artifacts=hashes,
        source_sha256=hashes['sensor-traced.json'],baseline_sha256=hashes['baseline-plain.json'],
        guest_mmio_executed=False,guest_mapping_provenance=False,mutation_census_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('PASS actual PI requests, translated storage, failed mapping and decoded CPU controls',flush=True)
    print(json.dumps(receipt,sort_keys=True),flush=True)


if __name__=='__main__': main()
