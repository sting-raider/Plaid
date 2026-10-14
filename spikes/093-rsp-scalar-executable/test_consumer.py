"""Executable IMEM reads feed exact rooted ORI/ADDU producer occurrences."""
from pathlib import Path
import copy,hashlib,importlib.util,json,os,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    prior=load('prior',ROOT/'spikes/091-raw-rsp-executable-consumption/test_consumer.py')
    clock=load('clock',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
    model=load('model',ROOT/'spikes/038-boot-pi-fetch-lineage/replay.py')
    scalar=load('scalar',Path(__file__).with_name('verify.py'))
    data,fw,rows,fetch=prior.source();rows[0].update(format='plaid-ares-access-history-v9',policy='observed_storage_sp_execution_and_rooted_scalar_operands_with_pi_queue_sp_backing')
    at=next(i for i,r in enumerate(rows) if r['record']=='rsp_imem_read');pc=rows[at]['pc']
    zero=[0]*32;defined=zero.copy();defined[8]=0x1111
    rows.insert(at,dict(record='rsp_operand_root',pc=pc,epoch=1,rsp_pc=0,registers=zero.copy()))
    for r in rows:
        if r['record']=='rsp_instruction':r['registers']=zero.copy() if r['begin'] else defined.copy()
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='rsp-scalar-') as tmp:
        tmp=Path(tmp);rom=tmp/'rom.z64';firmware=tmp/'firmware.bin';rom.write_bytes(data);firmware.write_bytes(fw)
        history=tmp/'history.ndjson';fetched=tmp/'fetch.ndjson';report=tmp/'report.json'
        def run(events,ok=True):
            clock.reclock(events);reads={}
            for r in events:
                if r['record']=='rsp_imem_read':reads[r['_read_id']]=r['ordinal']
                elif r['record']=='rsp_instruction':r['read_ordinal']=reads[r['_read_id']]
            for p,items in [(history,events),(fetched,fetch)]:p.write_text(''.join(json.dumps({k:v for k,v in r.items() if not k.startswith('_')})+'\n' for r in items),encoding='utf-8')
            h=hashlib.sha256(history.read_bytes()).hexdigest();f=hashlib.sha256(fetched.read_bytes()).hexdigest()
            args=[str(rom),str(firmware),str(fetched),str(history),h,f,str(report)]
            result=subprocess.run([str(exe),'inspect-sp-pi-fetch-lineage',*args],capture_output=True,text=True)
            assert (result.returncode==0)==ok,result.stderr
            if not ok:return
            actual=json.loads(report.read_bytes());assert actual['projection']['rsp_scalar_producers']==scalar.inspect(events)
            expected,_,_=model.inspect(history,fetched,data)
            for k,v in expected.items():assert actual[k]==v,k
            subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],check=True,capture_output=True)
            producers=actual['projection']['rsp_scalar_producers'];sample=actual['rsp_consumption']['samples'][0]
            assert producers['samples'][0]['read_ordinal']==sample['first_read_ordinal']
            assert producers['samples'][0]['definition']['context']==sample['first_begin_ordinal']
            writers=tmp/'writers.json';subprocess.run([str(exe),'inspect-sp-writer-fetch',*args[:-1],str(writers)],check=True,capture_output=True)
            assert json.loads(writers.read_bytes())['projection']['rsp_scalar_producers']==producers
            return actual
        result=run(copy.deepcopy(rows));assert result['projection']['rsp_scalar_producers']['definitions']==1
        assert result['rsp_consumption']['fully_attributed_instructions']==1
        root=next(i for i,r in enumerate(rows) if r['record']=='rsp_operand_root');begin=root+2
        # A fresh unknown code word consumes the earlier observed ORI definition.
        # Its opaque IMEM writer must never inherit the first instruction's PI bytes.
        def addu_tail(events,cut=False):
            changed=copy.deepcopy(events);end=next(i for i,r in enumerate(changed) if r['record']=='rsp_instruction' and not r['begin'])
            word=0x01084821;after=defined.copy();after[9]=0x2222
            tail=[dict(record='sp_word',pc=pc,write=True,address=0x04001004,bank=1,offset=4,bytes=4,value=word,cpu=False)]
            if cut:tail.append(dict(record='rsp_operand_root',pc=pc,epoch=2,rsp_pc=4,registers=defined.copy()))
            tail += [dict(record='rsp_imem_read',pc=pc,address=4,offset=4,word=word,_read_id='addu'),
                dict(record='rsp_instruction',pc=pc,begin=True,rsp_pc=4,word=word,next_pc=4,halted=False,_read_id='addu',registers=defined.copy()),
                dict(record='rsp_instruction',pc=pc,begin=False,rsp_pc=4,word=word,next_pc=8,halted=False,_read_id='addu',registers=after)]
            changed[end+1:end+1]=tail;return changed
        chained=run(addu_tail(rows));facts=chained['projection']['rsp_scalar_producers']['samples']
        assert facts[1]['definition']['expression']['left']=={'kind':'definition','context':facts[0]['definition']['context']}
        assert chained['rsp_consumption']['fully_attributed_instructions']==1
        cut=run(addu_tail(rows,True));expression=cut['projection']['rsp_scalar_producers']['samples'][1]['definition']['expression']
        assert expression['left']==expression['right']=={'kind':'captured_input','register':8,'value':0x1111}
        # Equal redefinition selects the later occurrence, even though r8's bits repeat.
        repeated=copy.deepcopy(rows);end=next(i for i,r in enumerate(repeated) if r['record']=='rsp_instruction' and not r['begin'])
        word=fetch[2]['word'];repeat=[dict(record='sp_word',pc=pc,write=True,address=0x04001004,bank=1,offset=4,bytes=4,value=word,cpu=False),
            dict(record='rsp_imem_read',pc=pc,address=4,offset=4,word=word,_read_id='repeat'),
            dict(record='rsp_instruction',pc=pc,begin=True,rsp_pc=4,word=word,next_pc=4,halted=False,_read_id='repeat',registers=defined.copy()),
            dict(record='rsp_instruction',pc=pc,begin=False,rsp_pc=4,word=word,next_pc=8,halted=False,_read_id='repeat',registers=defined.copy())]
        repeated[end+1:end+1]=repeat
        tail=addu_tail(rows)[end+1:end+5]
        for r in tail:
            if 'rsp_pc' in r:r['rsp_pc']=8;r['next_pc']=8 if r['begin'] else 12
            if r['record']=='sp_word':r['address']=0x04001008;r['offset']=8
            if r['record']=='rsp_imem_read':r['address']=r['offset']=8
        repeated[end+1+len(repeat):end+1+len(repeat)]=tail
        facts=run(repeated)['projection']['rsp_scalar_producers']['samples']
        assert len(facts)==3 and facts[2]['definition']['expression']['left']['context']==facts[1]['definition']['context']
        # Report deletion or a forged scalar expression cannot survive source rechecking.
        run(copy.deepcopy(rows));saved=report.read_bytes();doc=json.loads(saved)
        for key in ['delete','forge']:
            changed=copy.deepcopy(doc)
            if key=='delete':changed['projection'].pop('rsp_scalar_producers')
            else:changed['projection']['rsp_scalar_producers']['samples'][0]['definition']['value']^=1
            report.write_text(json.dumps(changed),encoding='utf-8')
            args=[str(rom),str(firmware),str(fetched),str(history),hashlib.sha256(history.read_bytes()).hexdigest(),hashlib.sha256(fetched.read_bytes()).hexdigest(),str(report)]
            assert subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],capture_output=True).returncode!=0
        report.write_bytes(saved)
        for kind in ['missing_root','missing_snapshot','short_snapshot','nonzero_zero','wrong_destination','foreign_change','root_inside','root_reuse','wrong_pc']:
            changed=copy.deepcopy(rows)
            if kind=='missing_root':changed.pop(root)
            elif kind=='missing_snapshot':changed[begin].pop('registers')
            elif kind=='short_snapshot':changed[begin]['registers'].pop()
            elif kind=='nonzero_zero':changed[root]['registers'][0]=1
            elif kind=='wrong_destination':changed[begin+1]['registers'][8]=2
            elif kind=='foreign_change':changed[begin+1]['registers'][4]=2
            elif kind=='root_inside':changed.insert(begin+1,copy.deepcopy(changed[root]))
            elif kind=='root_reuse':changed.insert(root+1,copy.deepcopy(changed[root]))
            elif kind=='wrong_pc':changed[root]['rsp_pc']=4
            run(changed,False)
        changed=copy.deepcopy(rows);changed[0].update(format='plaid-ares-access-history-v8',policy='observed_storage_dmem_imem_and_rsp_consumption_with_pi_queue_sp_backing');run(changed,False)
    print('PASS read-bound rooted scalar definitions, both consumers, independent graph/digest, malformed roots/snapshots and legacy rejection')
if __name__=='__main__':main()
