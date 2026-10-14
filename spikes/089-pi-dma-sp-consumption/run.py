"""Real PI copy -> RAM read -> SP DMA installation -> CPU SP execution controls."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/pi-sp-consumption-primary'


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
                rdram_scalar_access=sensor,memory_mutation_access=sensor,sp_backing_access=sensor,
                extra_sources=[HERE/'driver.cpp',ROOT/'spikes/088-pi-storage-executable/driver.cpp',
                    ROOT/'spikes/006-ares-rom-source/driver.cpp'])
            for mode in ('plain','traced','repeat'):
                raw=subprocess.check_output([str(executable),'plain' if mode=='plain' else 'traced'],timeout=60)
                (OUTPUT/f'{name}-{mode}.json').write_bytes(raw)
    data={name:{mode:json.loads((OUTPUT/f'{name}-{mode}.json').read_bytes())
        for mode in ('plain','traced','repeat')} for name in ('baseline','sensor')}
    states=data['baseline']['plain']['states']
    assert len(states)==12
    for modes in data.values():
        for result in modes.values(): assert result['states']==states
    assert all(not result['events'] for result in data['baseline'].values())
    assert not data['sensor']['plain']['events']
    trace=data['sensor']['traced'];assert trace==data['sensor']['repeat']
    assert [e['ordinal'] for e in trace['events']]==list(range(1,len(trace['events'])+1))
    for phase in (0,1):
        rows=[e for e in trace['events'] if e['phase']==phase]
        installs=[e for e in rows if e['record']=='sp_dma_store']
        assert len(installs)==1
        store=installs[0];at=trace['events'].index(store);read=trace['events'][at-1]
        assert (read['record'],read['write'],read['device'],read['bytes'],read['address'],read['value']) \
            == ('scalar',False,4,8,0x1000+phase*0x200000,0x2410000700000000)
        assert (store['dram'],store['bank'],store['offset'],store['bytes'],store['value']) \
            == (read['address'],1,0,8,read['value'])
        fetches=[e for e in rows if e['record']=='sp_word']
        assert len(fetches)==1
        assert (fetches[0]['write'],fetches[0]['cpu'],fetches[0]['address'],fetches[0]['value']) \
            == (False,True,0x04001000,0x24100007)
        assert not any(e['record']=='storage_effect' for e in trace['events'][at+1:trace['events'].index(fetches[0])])
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUTPUT.glob('*.json') if p.name!='receipt.json'}
    for name in ('baseline','sensor'):
        for filename in ('oracle','build.json'):
            path=OUTPUT/name/filename;hashes[str(path.relative_to(OUTPUT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt=dict(format='plaid-pi-sp-executable-receipt-v0',revision=builder.REV,records=len(trace['events']),
        checkpoints=len(states),controls_equal=True,repeat_equal=True,artifacts=hashes,
        source_sha256=hashes['sensor-traced.json'],guest_mmio_executed=False,
        guest_mapping_provenance=False,rsp_execution_claimed=False,mutation_census_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('PASS actual PI -> RAM -> SP DMA -> CPU SP consumption controls',flush=True)
    print(json.dumps(receipt,sort_keys=True),flush=True)


if __name__=='__main__': main()
