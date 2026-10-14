"""Actual lower IMEM writes/fill/load coexist with separate installs and consumers."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/imem-storage-cuts-primary'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def main():
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(HERE/'run.py')],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script,*sys.argv[1:]],check=True);return
    builder=load('builder',ROOT/'spikes/003-ares-oracle/run.py')
    prior=load('controls',ROOT/'spikes/090-rsp-dmem-storage-cuts/run.py')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if '--verify-existing' not in sys.argv:
        for name,sensor in [('baseline',False),('sensor',True)]:
            print('Building',name,flush=True)
            executable=builder.build(HERE/('driver.cpp' if sensor else 'baseline.cpp'),OUTPUT/name,
                raw_fetch_access=True,physical_fetch_access=True,pi_dma_access=sensor,rdram_scalar_access=sensor,
                memory_mutation_access=sensor,sp_backing_access=sensor,rsp_dmem_access=sensor,rsp_instruction_fetch_access=sensor,
                extra_sources=[HERE/'driver.cpp',ROOT/'spikes/088-pi-storage-executable/driver.cpp',
                    ROOT/'spikes/089-pi-dma-sp-consumption/driver.cpp',ROOT/'spikes/090-rsp-dmem-storage-cuts/driver.cpp',
                    ROOT/'spikes/091-raw-rsp-executable-consumption/driver.cpp',
                    ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp',ROOT/'spikes/006-ares-rom-source/driver.cpp'])
            for mode in ('plain','traced','repeat'):
                (OUTPUT/f'{name}-{mode}.json').write_bytes(subprocess.check_output([str(executable),
                    'plain' if mode=='plain' else 'traced'],timeout=60))
    results={name:{mode:json.loads((OUTPUT/f'{name}-{mode}.json').read_bytes())
        for mode in ('plain','traced','repeat')} for name in ('baseline','sensor')}
    states,source=prior.verify_controls(results,40,extra_cpu_imem_reads=3)
    for phase in (0,1):
        rows=[e for e in source['events'] if e['phase']==phase]
        cuts=[e for e in rows if e['record']=='imem_storage_effect']
        assert len(cuts)==21
        assert [(e['kind'],e['offset'],e['bytes'],e['value']) for e in cuts if e['kind']!=0]==[(1,0,4096,0),(2,0,4096,0)]
        installs=[e for e in rows if e['record']=='sp_dma_store' and e['bank']==1]
        assert len(installs)==4
        for install in installs:
            at=source['events'].index(install)
            assert [(e['record'],e['kind'],e['offset'],e['bytes'],e['value']) for e in source['events'][at-2:at]] \
                == [('imem_storage_effect',0,0,4,0x24100007),('imem_storage_effect',0,4,4,0)]
            read=source['events'][at-3]
            assert (read['record'],read['write'],read['device'],read['bytes'],read['address'],read['value']) \
                == ('scalar',False,4,8,install['dram'],install['value'])
        assert [(e['offset'],e['value']) for e in cuts if e['kind']==0 and e['offset']==0]==[(0,0x24100007)]*5
        reads={e['ordinal']:e for e in rows if e['record']=='rsp_imem_read'}
        begins=[e for e in rows if e['record']=='rsp_instruction' and e['begin']]
        ends=[e for e in rows if e['record']=='rsp_instruction' and not e['begin']]
        assert len(reads)==28 and len(begins)==len(ends)==21
        for begin,end in zip(begins,ends,strict=True):
            assert begin['read_ordinal']==end['read_ordinal']
            assert reads[begin['read_ordinal']]['word']==begin['word']==end['word']
        assert [(e['rsp_pc'],e['word']) for e in begins[-9:]]==[(0,0x24100007),(4,0),(8,13),
            (0,0x24100007),(4,0x24100007),(8,13),(0,0x24100007),(4,0),(8,13)]
    artifacts={f'{name}-{mode}.json':hashlib.sha256((OUTPUT/f'{name}-{mode}.json').read_bytes()).hexdigest()
        for name in ('baseline','sensor') for mode in ('plain','traced','repeat')}
    for name in ('baseline','sensor'):
        for filename in ('oracle','build.json'):
            path=OUTPUT/name/filename;artifacts[str(path.relative_to(OUTPUT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt=dict(format='plaid-imem-storage-cut-receipt-v0',revision=builder.REV,records=len(source['events']),
        checkpoints=len(states),imem_effects=42,performed_instructions=42,imem_reads=56,
        controls_equal=True,repeat_equal=True,artifacts=artifacts,source_sha256=artifacts['sensor-traced.json'],
        mutation_census_certified=False,executable_lifetime_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('PASS actual IMEM lower/equal/fill/load effects, separate DMA installation and CPU/RSP consumption controls',flush=True)
    print(json.dumps(receipt,sort_keys=True),flush=True)


if __name__=='__main__':main()
