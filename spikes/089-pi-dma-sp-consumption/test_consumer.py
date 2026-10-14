"""Reproduce the missing join between canonical PI and SP writer facts."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import copy

ROOT=Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def source(identity=False):
    pi=load('pi_storage_source',ROOT/'spikes/088-pi-storage-executable/test_consumer.py')
    old=load('storage_source',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
    if identity:
        rom,firmware,rows,fetches=old.source(False,0)
        rows=[e for e in rows if e['record']!='storage_effect']
    else:
        rom,firmware,rows,fetches=pi.source(False)
    begin=max(n for n,e in enumerate(rows) if e['record']=='fetch_begin')
    dram=fetches[2]['physical'];word=fetches[2]['word'];pc=rows[begin]['pc']
    rows[begin:begin]=[
        dict(record='scalar',pc=pc,write=False,address=dram,aligned_address=dram,
            bytes=8,device=4,value=word<<32),
        dict(record='sp_dma_store',pc=pc,dram=dram,bank=1,offset=0,bytes=8,value=word<<32)]
    for e in rows[begin+2:-1]:
        e['pc']=0xffffffffa4001000
        if e['record']=='scalar':
            e.clear();e.update(record='sp_word',pc=0xffffffffa4001000,write=False,
                address=0x04001000,bank=1,offset=0,bytes=4,value=word,cpu=True)
        elif e['record']=='fetch': e['physical']=0x04001000
        else: e.update(vaddr=0xffffffffa4001000,translated=0x04001000,bus=0x04001000)
    fetches[2].update(pc=0xffffffffa4001000,physical=0x04001000)
    old.reclock(rows)
    return rom,firmware,rows,fetches


def main():
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='pi-sp-join-') as directory:
        directory=Path(directory)
        data,fw,rows,fetches=source()
        rom=directory/'synthetic.z64';firmware=directory/'firmware.bin'
        history=directory/'history.ndjson';fetched=directory/'fetch.ndjson'
        rom.write_bytes(data);firmware.write_bytes(fw)
        old=load('storage_clock',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
        model=load('pi_sp_model',ROOT/'spikes/038-boot-pi-fetch-lineage/replay.py')
        def inspect(command,name):
            output=directory/name
            subprocess.run([str(exe),command,str(rom),str(firmware),str(fetched),str(history),h,f,str(output)],
                check=True,capture_output=True,text=True)
            return json.loads(output.read_bytes())
        def run(events):
            nonlocal h,f
            old.reclock(events)
            for path,items in [(history,events),(fetched,fetches)]:
                path.write_text(''.join(json.dumps(e)+'\n' for e in items),encoding='utf-8')
            h=hashlib.sha256(history.read_bytes()).hexdigest();f=hashlib.sha256(fetched.read_bytes()).hexdigest()
            result=inspect('inspect-sp-pi-fetch-lineage','pi.json')
            inspect('verify-sp-pi-fetch-lineage','pi.json')
            expected,mh,mf=model.inspect(history,fetched,data)
            assert (mh,mf)==(h,f)
            for key,value in expected.items(): assert result[key]==value,key
            assert not any(result[k] for k in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'))
            return result
        h=f=None
        pi=run(rows)
        sp=inspect('inspect-sp-writer-fetch','sp.json')
        assert sp['fully_compatible_fetches']==1
        assert all(w['kind']['kind']=='dma_sink' and w['kind']['read_ordinal'] is not None
            for w in sp['samples'][0]['writers'])
        assert pi['fully_attributed_fetches']==1
        assert pi['format']=='plaid-sp-pi-fetch-lineage-report-v1'
        assert [b['sp_writer'] for b in pi['samples'][0]['bytes']]==sp['samples'][0]['writers']
        assert pi['projection']['dma_store_receipts'][0]['read_ordinal'] is not None
        read=next(n for n,e in enumerate(rows) if e['record']=='scalar' and e.get('device')==4)
        install=read+1
        consume=next(n for n,e in enumerate(rows) if e['record']=='sp_word')
        cut=dict(record='storage_effect',pc=rows[read]['pc'],kind=0,
            address=rows[read]['address'],bytes=1,value=rows[read]['value']>>56)
        for position,full,partial in [(read,0,1),(install,1,0),(install+1,1,0)]:
            changed=copy.deepcopy(rows);changed.insert(position,copy.deepcopy(cut))
            result=run(changed)
            assert (result['fully_attributed_fetches'],result['partially_attributed_fetches'])==(full,partial)
        for variant in range(10):
            changed=copy.deepcopy(rows)
            if variant==0:
                changed.insert(install+1,dict(record='sp_word',pc=rows[read]['pc'],write=True,
                    address=0x04001000,bank=1,offset=0,bytes=4,value=fetches[2]['word'],cpu=False))
            elif variant==1: changed.insert(read,copy.deepcopy(changed[read]))
            elif variant==2: changed.pop(read)
            elif variant==3: changed[read]['pc']^=4
            elif variant==4: changed[install]['bank']=0
            elif variant==5: changed[install]['offset']=8
            elif variant==6: changed[install]['value']^=1<<56
            elif variant==7: changed.insert(read,changed.pop(install))
            elif variant==8: changed.insert(consume,copy.deepcopy(changed[consume]))
            else: changed[consume]['cpu']=False
            result=run(changed)
            assert result['fully_attributed_fetches']==result['partially_attributed_fetches']==0,variant
        # A contradictory non-fetch SP read permanently revokes the old byte.
        changed=copy.deepcopy(rows);contradiction=copy.deepcopy(rows[consume])
        contradiction.update(cpu=False,pc=rows[read]['pc'],value=fetches[2]['word']^1)
        changed.insert(install+1,contradiction)
        result=run(changed)
        assert result['fully_attributed_fetches']==0 and result['partially_attributed_fetches']==1
        pi=run(rows)
        for field in ('write_ordinal','byte_index','read_ordinal'):
            forged=copy.deepcopy(pi);writer=forged['samples'][0]['bytes'][0]['sp_writer']
            target=writer['kind'] if field=='read_ordinal' else writer
            target[field]+=1
            (directory/'pi.json').write_text(json.dumps(forged),encoding='utf-8')
            result=subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',str(rom),str(firmware),
                str(fetched),str(history),h,f,str(directory/'pi.json')],capture_output=True,text=True)
            assert result.returncode!=0,field
        data,fw,rows,fetches=source(True)
        rom.write_bytes(data);firmware.write_bytes(fw)
        identity=run(rows)
        assert identity['fully_attributed_fetches']==1
        wrappers=[e['ordinal'] for e in rows if e['record']=='scalar' and e.get('pi')]
        assert [b['writer_ordinal'] for b in identity['samples'][0]['bytes']]==wrappers[:4]
        print('PASS identity/physical PI -> frozen DMA read -> SP install -> CPU SP consumption; 14 lifetime/ambiguity controls and 3 forged receipts; CLI/model agree')


if __name__=='__main__': main()
