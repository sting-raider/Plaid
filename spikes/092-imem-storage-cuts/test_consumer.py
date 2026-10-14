"""Lower IMEM effects revoke code parents while preserving earlier read identity."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def main():
    previous=load('read_fixture',ROOT/'spikes/091-raw-rsp-executable-consumption/test_consumer.py')
    clock=load('clock',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
    model=load('model',ROOT/'spikes/038-boot-pi-fetch-lineage/replay.py')
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='imem-cut-') as temporary:
        base=Path(temporary);rom=base/'rom.z64';fw=base/'firmware.bin'
        history=base/'history.ndjson';fetched=base/'fetch.ndjson';report=base/'report.json'
        data,firmware,rows,fetches=previous.source();rom.write_bytes(data);fw.write_bytes(firmware)
        rows[0].update(format='plaid-ares-access-history-v8',
            policy='observed_storage_dmem_imem_and_rsp_consumption_with_pi_queue_sp_backing')
        read=next(n for n,e in enumerate(rows) if e['record']=='rsp_imem_read')
        word=fetches[2]['word']
        def run(events,ok=True):
            clock.reclock(events);reads={}
            for event in events:
                if event['record']=='rsp_imem_read':reads[event['_read_id']]=event['ordinal']
                elif event['record']=='rsp_instruction':event['read_ordinal']=reads.get(event['_read_id'],0)
            for path,items in [(history,events),(fetched,fetches)]:
                path.write_text(''.join(json.dumps({k:v for k,v in e.items() if not k.startswith('_')})+'\n' for e in items),encoding='utf-8')
            h=hashlib.sha256(history.read_bytes()).hexdigest();f=hashlib.sha256(fetched.read_bytes()).hexdigest()
            args=[str(rom),str(fw),str(fetched),str(history),h,f,str(report)]
            result=subprocess.run([str(exe),'inspect-sp-pi-fetch-lineage',*args],capture_output=True,text=True)
            assert (result.returncode==0)==ok,result.stderr
            if not ok:return
            actual=json.loads(report.read_bytes());expected,mh,mf=model.inspect(history,fetched,data)
            assert (mh,mf)==(h,f)
            for key,value in expected.items():assert actual[key]==value,key
            subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],check=True,capture_output=True)
            writers=base/'writers.json'
            subprocess.run([str(exe),'inspect-sp-writer-fetch',*args[:-1],str(writers)],check=True,capture_output=True)
            captured=json.loads(writers.read_bytes())
            assert captured['projection']['format']=='plaid-observed-sp-backing-report-v4'
            assert captured['fully_compatible_fetches']==actual['fully_attributed_fetches']
            assert captured['partially_compatible_fetches']==actual['partially_attributed_fetches']
            return actual
        for kind in (0,1,2):
            cut=dict(record='imem_storage_effect',pc=rows[read]['pc'],kind=kind,
                offset=0,bytes=4 if kind==0 else 4096,value=word if kind==0 else 0)
            for position in (read,read+1,read+2,read+3):
                changed=copy.deepcopy(rows);changed.insert(position,cut)
                actual=run(changed)
                assert actual['rsp_consumption']['fully_attributed_instructions']==int(position>read)
                assert actual['fully_attributed_fetches']==0
                assert not any(actual[k] for k in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'))
            # An already captured CPU Word survives a later storage mutation too.
            cpu_read=next(n for n,e in enumerate(rows) if e['record']=='sp_word' and not e['write'])
            changed=copy.deepcopy(rows);changed.insert(cpu_read+1,dict(cut,pc=rows[cpu_read]['pc']))
            assert run(changed)['fully_attributed_fetches']==1
        for width,offset in ((1,3),(2,2)):
            changed=copy.deepcopy(rows);changed.insert(read,dict(record='imem_storage_effect',pc=rows[read]['pc'],
                kind=0,offset=offset,bytes=width,value=word&((1<<(width*8))-1)))
            actual=run(changed)
            assert actual['rsp_consumption']['partially_attributed_instructions']==1
            assert actual['partially_attributed_fetches']==1
        install=next(n for n,e in enumerate(rows) if e['record']=='sp_dma_store')
        for kind in (0,1,2):
            cut=dict(record='imem_storage_effect',pc=rows[install]['pc'],kind=kind,
                offset=0,bytes=4 if kind==0 else 4096,value=word if kind==0 else 0)
            changed=copy.deepcopy(rows);changed.insert(install,cut)
            actual=run(changed)
            assert actual['fully_attributed_fetches']==actual['rsp_consumption']['fully_attributed_instructions']==1
        for field,value in [('kind',3),('kind',4),('kind',9),('offset',4096),('offset',1),
            ('bytes',0),('bytes',8),('value',1<<32),('extra',True)]:
            changed=copy.deepcopy(rows);bad=dict(record='imem_storage_effect',pc=rows[read]['pc'],kind=0,offset=0,bytes=4,value=word)
            bad[field]=value;changed.insert(read,bad);run(changed,False)
        changed=copy.deepcopy(rows);changed.insert(read,dict(record='imem_storage_effect',pc=rows[read]['pc'],kind=1,offset=0,bytes=4,value=0))
        run(changed,False)
        for version,policy in [('v7','observed_storage_dmem_and_performed_rsp_instructions_with_pi_queue_sp_backing'),
            ('v6','observed_ordinary_storage_and_dmem_mutations_with_pi_queue_sp_backing')]:
            changed=copy.deepcopy(rows);changed[0].update(format='plaid-ares-access-history-'+version,policy=policy)
            changed.insert(read,dict(record='imem_storage_effect',pc=rows[read]['pc'],kind=0,offset=0,bytes=4,value=word))
            run(changed,False)
    print('PASS IMEM equal/scalar/full cuts, frozen CPU/RSP reads, partial lanes, DMA installation, malformed effects and legacy admission; both consumers/model agree')


if __name__=='__main__':main()
