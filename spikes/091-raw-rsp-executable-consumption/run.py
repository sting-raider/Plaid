"""Actual PI/RAM/IMEM instruction consumption by the pinned interpreted RSP."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/raw-rsp-consumption-primary'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def main():
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(HERE/'run.py')],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script,*sys.argv[1:]],check=True);return
    builder=load('builder',ROOT/'spikes/003-ares-oracle/run.py')
    prior=load('prior_controls',ROOT/'spikes/090-rsp-dmem-storage-cuts/run.py')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    if '--verify-existing' not in sys.argv:
        for name,sensor in [('baseline',False),('sensor',True)]:
            print('Building',name,flush=True)
            executable=builder.build(HERE/('driver.cpp' if sensor else 'baseline.cpp'),OUTPUT/name,
                raw_fetch_access=True,physical_fetch_access=True,pi_dma_access=sensor,rdram_scalar_access=sensor,
                memory_mutation_access=sensor,sp_backing_access=sensor,rsp_dmem_access=sensor,rsp_instruction_fetch_access=sensor,
                extra_sources=[HERE/'driver.cpp',ROOT/'spikes/088-pi-storage-executable/driver.cpp',
                    ROOT/'spikes/089-pi-dma-sp-consumption/driver.cpp',ROOT/'spikes/090-rsp-dmem-storage-cuts/driver.cpp',
                    ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp',ROOT/'spikes/006-ares-rom-source/driver.cpp'])
            for mode in ('plain','traced','repeat'):
                (OUTPUT/f'{name}-{mode}.json').write_bytes(subprocess.check_output([str(executable),
                    'plain' if mode=='plain' else 'traced'],timeout=60))
    results={name:{mode:json.loads((OUTPUT/f'{name}-{mode}.json').read_bytes())
        for mode in ('plain','traced','repeat')} for name in ('baseline','sensor')}
    states,source=prior.verify_controls(results,28)
    for phase in (0,1):
        rows=[e for e in source['events'] if e['phase']==phase]
        instructions=[e for e in rows if e['record']=='rsp_instruction']
        expected=[]
        for pc,word,next_pc,begin_halted,halted in [
            (0x200,0xac220000,0x204,False,False),(0x204,13,0x208,False,True),
            (0,0x24100007,4,False,False),(4,0,8,False,False),(8,13,12,False,True),
            (0x300,0x00200008,0x304,False,False),(0x304,0,3,False,False),
            (3,0x24100007,7,False,False),(7,0,11,False,False),(11,13,15,False,True),
            (0x400,0x40822000,0x404,False,True),(0x404,0x4a000037,0x408,True,True)]:
            expected.extend([(True,pc,word,pc,begin_halted),(False,pc,word,next_pc,halted)])
        assert [(e['begin'],e['rsp_pc'],e['word'],e['next_pc'],e['halted']) for e in instructions]==expected
        cuts=[e for e in rows if e['record']=='rsp_dmem_effect' and e['bytes']==1]
        assert instructions[0]['ordinal']<cuts[0]['ordinal']<cuts[-1]['ordinal']<instructions[1]['ordinal']
        assert all(e['ordinal']>next(e['ordinal'] for e in rows if e['record']=='sp_dma_store')
            for e in instructions[4:])
        install=next(e for e in rows if e['record']=='sp_dma_store' and e['bank']==1)
        read=source['events'][install['ordinal']-2]
        assert (read['record'],read['write'],read['device'],read['bytes'],read['address'],read['value']) \
            == ('scalar',False,4,8,install['dram'],install['value'])
        assert instructions[4]['word']==install['value']>>32
        assert instructions[6]['word']==install['value']&0xffffffff
        reads={e['ordinal']:e for e in rows if e['record']=='rsp_imem_read'}
        used=set()
        for begin,end in zip(instructions[::2],instructions[1::2],strict=True):
            assert begin['read_ordinal']==end['read_ordinal']
            read=reads[begin['read_ordinal']]
            assert read['ordinal']<begin['ordinal'] and read['word']==begin['word']
            assert read['offset']==read['address']&0xffc
            assert read['ordinal'] not in used;used.add(read['ordinal'])
            if begin['rsp_pc'] in (3,7,11):assert read['offset']==begin['rsp_pc']&0xffc
        assert len(reads)==16 and len(used)==12
    artifacts={f'{name}-{mode}.json':hashlib.sha256((OUTPUT/f'{name}-{mode}.json').read_bytes()).hexdigest()
        for name in ('baseline','sensor') for mode in ('plain','traced','repeat')}
    for name in ('baseline','sensor'):
        for filename in ('oracle','build.json'):
            path=OUTPUT/name/filename;artifacts[str(path.relative_to(OUTPUT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt=dict(format='plaid-raw-rsp-consumption-receipt-v0',revision=builder.REV,
        records=len(source['events']),checkpoints=len(states),performed_instructions=24,imem_reads=32,unused_lookahead_reads=8,
        controls_equal=True,repeat_equal=True,artifacts=artifacts,source_sha256=artifacts['sensor-traced.json'],
        rsp_register_task_ancestry_certified=False,mutation_census_certified=False,
        executable_lifetime_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('PASS actual performed RSP words consume PI-installed IMEM, with independent machine/backing controls',flush=True)
    print(json.dumps(receipt,sort_keys=True),flush=True)


if __name__=='__main__':main()
