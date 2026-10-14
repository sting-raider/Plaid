"""Lower DMEM primitive effects cut compatible SP parents, including equal bytes."""
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
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def source(dmem):
    previous=load('pi_sp_fixture',ROOT/'spikes/089-pi-dma-sp-consumption/test_consumer.py')
    data,fw,rows,fetches=previous.source()
    rows[0].update(format='plaid-ares-access-history-v6',
        policy='observed_ordinary_storage_and_dmem_mutations_with_pi_queue_sp_backing')
    if dmem:
        for e in rows:
            if e['record']=='sp_dma_store': e['bank']=0
            elif e['record']=='sp_word': e.update(address=0x04000000,bank=0)
            if e.get('pc')==0xffffffffa4001000: e['pc']=0xffffffffa4000000
            for field in ('physical','bus','translated'):
                if e.get(field)==0x04001000: e[field]=0x04000000
            if e.get('vaddr')==0xffffffffa4001000: e['vaddr']=0xffffffffa4000000
        fetches[2].update(pc=0xffffffffa4000000,physical=0x04000000)
    return data,fw,rows,fetches


def main():
    clock=load('clock',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
    model=load('model',ROOT/'spikes/038-boot-pi-fetch-lineage/replay.py')
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='dmem-cut-') as temporary:
        base=Path(temporary);rom=base/'rom.z64';firmware=base/'firmware.bin'
        history=base/'history.ndjson';fetched=base/'fetch.ndjson';report=base/'report.json'
        def run(rows,fetches,ok=True):
            clock.reclock(rows)
            for path,items in [(history,rows),(fetched,fetches)]:
                path.write_text(''.join(json.dumps(e)+'\n' for e in items),encoding='utf-8')
            h=hashlib.sha256(history.read_bytes()).hexdigest();f=hashlib.sha256(fetched.read_bytes()).hexdigest()
            args=[str(rom),str(firmware),str(fetched),str(history),h,f,str(report)]
            result=subprocess.run([str(exe),'inspect-sp-pi-fetch-lineage',*args],capture_output=True,text=True)
            assert (result.returncode==0)==ok,result.stderr
            if not ok:return
            actual=json.loads(report.read_bytes());expected,mh,mf=model.inspect(history,fetched,rom.read_bytes())
            assert (mh,mf)==(h,f)
            for key,value in expected.items(): assert actual[key]==value,key
            subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],capture_output=True,check=True)
            writers=base/'writers.json'
            subprocess.run([str(exe),'inspect-sp-writer-fetch',*args[:-1],str(writers)],capture_output=True,check=True)
            captured=json.loads(writers.read_bytes())
            assert captured['projection']['format']=='plaid-observed-sp-backing-report-v2'
            assert captured['fully_compatible_fetches']==actual['fully_attributed_fetches']
            assert captured['partially_compatible_fetches']==actual['partially_attributed_fetches']
            assert not any(actual[k] for k in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'))
            return actual
        for dmem in (False,True):
            data,fw,rows,fetches=source(dmem);rom.write_bytes(data);firmware.write_bytes(fw)
            begin=max(n for n,e in enumerate(rows) if e['record']=='fetch_begin')
            install=next(n for n,e in enumerate(rows) if e['record']=='sp_dma_store')
            cut=dict(record='rsp_dmem_effect',pc=rows[install]['pc'],offset=3,bytes=1,value=fetches[2]['word']&255)
            assert run(copy.deepcopy(rows),fetches)['fully_attributed_fetches']==1
            changed=copy.deepcopy(rows);changed.insert(begin,cut)
            result=run(changed,fetches)
            assert (result['fully_attributed_fetches'],result['partially_attributed_fetches'])==((0,1) if dmem else (1,0))
            assert result['projection']['event_counts']['rsp_dmem_effect']==1
            changed=copy.deepcopy(rows);changed.insert(install,cut)
            assert run(changed,fetches)['fully_attributed_fetches']==1
            for field,value in [('offset',4096),('offset',3),('bytes',0),('bytes',16),('value',1<<32)]:
                changed=copy.deepcopy(rows);bad=dict(cut,offset=0,bytes=4,value=fetches[2]['word']);bad[field]=value
                changed.insert(begin,bad);run(changed,fetches,False)
            for width in (2,4,8):
                changed=copy.deepcopy(rows);effect=dict(cut,offset=0,bytes=width,value=0)
                changed.insert(begin,effect);result=run(changed,fetches)
                assert result['fully_attributed_fetches']==int(not dmem)
                assert result['partially_attributed_fetches']==int(dmem and width==2)
            changed=copy.deepcopy(rows)
            changed[begin:begin]=[dict(cut,offset=n,bytes=1,value=v)
                for n,v in enumerate(fetches[2]['word'].to_bytes(4,'big'))]
            result=run(changed,fetches)
            assert result['fully_attributed_fetches']==int(not dmem)
            assert result['partially_attributed_fetches']==0
            changed=copy.deepcopy(rows);changed.insert(begin,cut)
            changed[0].update(format='plaid-ares-access-history-v5',policy='observed_ordinary_storage_mutations_and_pi_queue_sp_backing')
            run(changed,fetches,False)
    print('PASS lower DMEM cuts, equal scalar/four-Byte effects, frozen reads, IMEM independence, widths and strict source admission; both CLI consumers/model agree')


if __name__=='__main__':main()
