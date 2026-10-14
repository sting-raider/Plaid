"""Actual RSP instruction occurrences retain frozen PI/IMEM installation parents."""
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


def source():
    prior=load('prior',ROOT/'spikes/089-pi-dma-sp-consumption/test_consumer.py')
    data,firmware,rows,fetches=prior.source()
    rows[0].update(format='plaid-ares-access-history-v7',
        policy='observed_storage_dmem_and_performed_rsp_instructions_with_pi_queue_sp_backing')
    at=max(n for n,e in enumerate(rows) if e['record']=='fetch_begin')
    pc=rows[at-1]['pc'];word=fetches[2]['word']
    rows[at:at]=[dict(record='rsp_imem_read',pc=pc,address=0,offset=0,word=word,_read_id='code'),
        dict(record='rsp_instruction',pc=pc,begin=True,rsp_pc=0,word=word,next_pc=0,halted=False,_read_id='code'),
        dict(record='rsp_instruction',pc=pc,begin=False,rsp_pc=0,word=word,next_pc=4,halted=False,_read_id='code')]
    return data,firmware,rows,fetches


def main():
    clock=load('clock',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
    model=load('model',ROOT/'spikes/038-boot-pi-fetch-lineage/replay.py')
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='rsp-consume-') as temporary:
        base=Path(temporary);rom=base/'rom.z64';firmware=base/'firmware.bin'
        history=base/'history.ndjson';fetched=base/'fetch.ndjson';report=base/'report.json'
        data,fw,rows,fetches=source();rom.write_bytes(data);firmware.write_bytes(fw)
        def run(events,ok=True):
            clock.reclock(events)
            reads={}
            for event in events:
                if event['record']=='rsp_imem_read':reads[event['_read_id']]=event['ordinal']
                elif event['record']=='rsp_instruction' and '_read_id' in event:
                    event['read_ordinal']=reads.get(event['_read_id'],0)
            for path,items in [(history,events),(fetched,fetches)]:
                path.write_text(''.join(json.dumps({k:v for k,v in e.items() if not k.startswith('_')})+'\n' for e in items),encoding='utf-8')
            h=hashlib.sha256(history.read_bytes()).hexdigest();f=hashlib.sha256(fetched.read_bytes()).hexdigest()
            args=[str(rom),str(firmware),str(fetched),str(history),h,f,str(report)]
            result=subprocess.run([str(exe),'inspect-sp-pi-fetch-lineage',*args],capture_output=True,text=True)
            assert (result.returncode==0)==ok,result.stderr
            if not ok:return
            actual=json.loads(report.read_bytes());expected,mh,mf=model.inspect(history,fetched,data)
            assert (mh,mf)==(h,f)
            for key,value in expected.items():assert actual[key]==value,key
            subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],capture_output=True,check=True)
            assert not any(actual[k] for k in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'))
            return actual,args
        actual,args=run(rows)
        rsp=actual['rsp_consumption']
        assert actual['format']=='plaid-sp-pi-fetch-lineage-report-v2'
        assert rsp['instructions']==rsp['fully_attributed_instructions']==1
        sample=rsp['samples'][0]
        begin=next(n for n,e in enumerate(rows) if e['record']=='rsp_instruction')
        read_index=begin-1
        assert sample['first_read_ordinal']==rows[read_index]['ordinal']
        assert (sample['first_begin_ordinal'],sample['first_end_ordinal'])==(rows[begin]['ordinal'],rows[begin+1]['ordinal'])
        assert sample['bytes']==actual['samples'][0]['bytes']
        changed=copy.deepcopy(rows);changed[begin+2:begin+2]=copy.deepcopy(rows[read_index:begin+2])
        repeated,_=run(changed)
        assert repeated['rsp_consumption']['instructions']==2
        assert repeated['rsp_consumption']['samples'][0]['observations']==2
        assert repeated['rsp_consumption']['samples'][0]['last_begin_ordinal']>sample['first_begin_ordinal']
        read=next(e for e in rows if e['record']=='scalar' and e.get('device')==4)
        install=next(e for e in rows if e['record']=='sp_dma_store')
        changed=copy.deepcopy(rows);changed[begin+1:begin+1]=[copy.deepcopy(read),copy.deepcopy(install)]
        replaced,_=run(changed)
        assert replaced['rsp_consumption']['fully_attributed_instructions']==replaced['fully_attributed_fetches']==1
        assert replaced['rsp_consumption']['samples'][0]['bytes']==sample['bytes']
        assert replaced['samples'][0]['bytes'][0]['sp_writer']['write_ordinal']>sample['bytes'][0]['sp_writer']['write_ordinal']
        for position in (read_index,begin,begin+1,begin+2):
            changed=copy.deepcopy(rows);changed.insert(position,dict(record='sp_word',pc=rows[begin]['pc'],
                write=True,address=0x04001000,bank=1,offset=0,bytes=4,value=fetches[2]['word'],cpu=False))
            result,_=run(changed)
            assert result['rsp_consumption']['fully_attributed_instructions']==int(position>read_index)
            assert result['fully_attributed_fetches']==0
        for variant in range(12):
            changed=copy.deepcopy(rows)
            if variant==0:changed.pop(begin+1)
            elif variant==1:changed.pop(begin)
            elif variant==2:changed.insert(begin+1,copy.deepcopy(changed[begin]))
            elif variant==3:changed[begin+1]['word']^=1
            elif variant==4:changed[begin+1]['rsp_pc']=4
            elif variant==5:changed[begin+1]['pc']^=4
            elif variant==6:changed[begin]['rsp_pc']=4096
            elif variant==7:changed[begin].pop('_read_id');changed[begin]['read_ordinal']=0
            elif variant==8:changed[begin+1]['next_pc']=4096
            elif variant==9:changed.pop(read_index)
            elif variant==10:changed[read_index]['offset']=4
            else:changed[read_index]['address']=4096
            run(changed,False)
        changed=copy.deepcopy(rows);pair=changed[read_index:begin+2];del changed[read_index:begin+2]
        cpu_begin=max(n for n,e in enumerate(changed) if e['record']=='fetch_begin')
        for event in pair:event['pc']=changed[cpu_begin]['pc']
        changed[cpu_begin+1:cpu_begin+1]=pair
        run(changed,False)
        changed=copy.deepcopy(rows)
        changed[read_index].update(address=4,offset=4,word=0)
        for event in changed[begin:begin+2]:event.update(rsp_pc=4,word=0,next_pc=4 if event['begin'] else 8)
        result,_=run(changed)
        assert result['rsp_consumption']['unattributed_instructions']==1
        assert all(b is None for b in result['rsp_consumption']['samples'][0]['bytes'])
        # An RSP read contradiction permanently cuts the old IMEM candidate.
        changed=copy.deepcopy(rows)
        for event in changed[read_index:begin+2]:event['word']^=1
        result,_=run(changed)
        assert result['rsp_consumption']['partially_attributed_instructions']==1
        assert result['partially_attributed_fetches']==1
        actual,args=run(rows)
        for field in ('first_read_ordinal','first_begin_ordinal','first_end_ordinal','last_end_ordinal','fetch_offset'):
            forged=copy.deepcopy(actual);forged['rsp_consumption']['samples'][0][field]+=1
            report.write_text(json.dumps(forged),encoding='utf-8')
            result=subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],capture_output=True)
            assert result.returncode!=0,field
        forged=copy.deepcopy(actual);forged['rsp_consumption']['ordered_instruction_chains_sha256']='0'*64
        report.write_text(json.dumps(forged),encoding='utf-8')
        assert subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],capture_output=True).returncode!=0
        forged=copy.deepcopy(actual);del forged['rsp_consumption']
        report.write_text(json.dumps(forged),encoding='utf-8')
        assert subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],capture_output=True).returncode!=0
        changed=copy.deepcopy(rows);changed[0].update(format='plaid-ares-access-history-v6',
            policy='observed_ordinary_storage_and_dmem_mutations_with_pi_queue_sp_backing')
        run(changed,False)
        # Logical PC low bits do not identify the actual aligned Word.
        changed=copy.deepcopy(rows);changed[read_index]['address']=3
        changed[begin].update(rsp_pc=3,next_pc=3)
        changed[begin+1].update(rsp_pc=3,next_pc=7)
        result,_=run(changed)
        unaligned=result['rsp_consumption']['samples'][0]
        assert (unaligned['rsp_pc'],unaligned['read_address'],unaligned['fetch_offset'])==(3,3,0)
        assert unaligned['bytes']==sample['bytes']
        changed=copy.deepcopy(rows)
        pc=rows[begin]['pc'];vnop=0x4a000037
        wrap=[dict(record='sp_word',pc=pc,write=True,address=0x04001ffc,bank=1,offset=4092,bytes=4,value=vnop,cpu=False),
            dict(record='rsp_imem_read',pc=pc,address=4092,offset=4092,word=vnop,_read_id='wrap'),
            dict(record='rsp_instruction',pc=pc,begin=True,rsp_pc=4092,word=vnop,next_pc=4092,halted=False,_read_id='wrap'),
            dict(rows[read_index],address=4096),
            dict(record='rsp_instruction',pc=pc,begin=False,rsp_pc=4092,word=vnop,next_pc=0,halted=False,_read_id='wrap')]
        changed[read_index:read_index+1]=wrap
        result,_=run(changed)
        assert result['rsp_consumption']['instructions']==2
        assert result['rsp_consumption']['fully_attributed_instructions']==1
        wrapped=next(s for s in result['rsp_consumption']['samples'] if s['rsp_pc']==0)
        assert (wrapped['read_address'],wrapped['fetch_offset'])==(4096,0)
        assert wrapped['bytes']==sample['bytes']
        # A status flag cannot erase an instruction that the pin actually performs.
        changed=copy.deepcopy(rows);changed[begin]['halted']=True
        result,_=run(changed)
        assert result['rsp_consumption']['samples'][0]['begin_halted']
        # An unused lookahead is a read, not an executed code root.
        changed=copy.deepcopy(rows);look=dict(record='rsp_imem_read',pc=rows[begin]['pc'],
            address=4,offset=4,word=0,_read_id='look')
        changed.insert(begin+1,look)
        result,_=run(changed)
        assert result['rsp_consumption']['instructions']==1
        next_frame=[dict(look,_read_id='next')]+[dict(record='rsp_instruction',pc=rows[begin]['pc'],
            begin=b,rsp_pc=4,word=0,next_pc=4 if b else 8,halted=False,_read_id='next') for b in (True,False)]
        changed[begin+3:begin+3]=next_frame
        result,_=run(changed)
        assert result['rsp_consumption']['instructions']==2
        assert result['rsp_consumption']['unattributed_instructions']==1
        # Equal bits cannot borrow the earlier unperformed read occurrence.
        changed[begin+4]['_read_id']='look';run(changed,False)
    print('PASS exact RSP IMEM read -> performed consumption, frozen parents, unaligned PCs, unused lookahead, unknown roots and complete-source identity gates; CLI/model agree')


if __name__=='__main__':main()
