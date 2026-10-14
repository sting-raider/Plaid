"""Rooted RSP store -> frozen DMA read -> RAM writer -> executable read."""
from pathlib import Path
import copy, hashlib, importlib.util, json, os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[2]

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def source():
    prior=load('prior',ROOT/'spikes/094-rsp-scalar-store-actor/test_consumer.py')
    data,fw,rows,fetch=prior.source()
    rows[0].update(format='plaid-ares-access-history-v11',policy='observed_scalar_rsp_stores_and_exact_reverse_sp_dma_with_pi_queue_sp_backing')
    at=max(i for i,r in enumerate(rows) if r['record']=='fetch_begin');pc=rows[at]['pc']
    rows[at:at]=[
        dict(record='sp_dma_egress_read',pc=pc,dram=0x2000,bank=0,offset=0,bytes=4,value=0x1111,_egress_read='copy'),
        dict(record='storage_effect',pc=pc,kind=0,address=0x2000,bytes=4,value=0x1111),
        dict(record='scalar',pc=pc,write=True,address=0x2000,aligned_address=0x2000,bytes=4,device=4,value=0x1111,_egress_write='copy'),
        dict(record='sp_dma_egress_store',pc=pc,_egress_read='copy',_egress_write='copy')]
    at=max(i for i,r in enumerate(rows) if r['record']=='fetch_begin')
    for r in rows[at:-1]:
        r['pc']=0xffffffffa0002000
        if r['record']=='sp_word':r.clear();r.update(record='scalar',pc=0xffffffffa0002000,write=False,address=0x2000,aligned_address=0x2000,bytes=4,device=3,value=0x1111)
        elif r['record']=='fetch':r.update(physical=0x2000)
        elif r['record'] in ('fetch_begin','fetch_end'):r.update(vaddr=0xffffffffa0002000,translated=0x2000,bus=0x2000)
    fetch[2].update(pc=0xffffffffa0002000,physical=0x2000)
    return data,fw,rows,fetch

def main():
    clock=load('clock',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
    model=load('model',ROOT/'spikes/095-raw-sp-dma-executable/verify.py')
    data,fw,rows,fetch=source();exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='raw-egress-') as temp:
        p=Path(temp);rom=p/'rom.z64';firmware=p/'firmware.bin';history=p/'history.ndjson';fetched=p/'fetch.ndjson';report=p/'report.json'
        rom.write_bytes(data);firmware.write_bytes(fw)
        def run(events,ok=True,fetches=None):
            clock.reclock(events);reads={};instructions={};scopes={};egress_reads={};egress_writes={}
            for r in events:
                kind=r['record']
                if kind=='rsp_imem_read':reads[r['_read_id']]=r['ordinal']
                elif kind=='rsp_instruction':
                    r['read_ordinal']=reads[r['_read_id']]
                    if r['begin']:instructions[r['_instruction_id']]=r['ordinal']
                elif kind=='rsp_scalar_store_scope':
                    r['instruction_context']=instructions[r['_instruction_id']]
                    if r['begin']:scopes[r['_scope_id']]=r['ordinal']
                    r['store_scope']=scopes.get(r['_scope_id'],0)
                elif kind=='rsp_dmem_effect' and '_scope_id' in r:r['store_scope']=scopes.get(r['_scope_id'],0)
                elif kind=='sp_dma_egress_read':egress_reads[r['_egress_read']]=r['ordinal']
                elif kind=='scalar' and '_egress_write' in r:egress_writes[r['_egress_write']]=r['ordinal']
                elif kind=='sp_dma_egress_store':
                    r['read_ordinal']=egress_reads[r['_egress_read']];r['write_ordinal']=egress_writes[r['_egress_write']]
            for path,items in ((history,events),(fetched,fetches or fetch)):
                path.write_text(''.join(json.dumps({k:v for k,v in r.items() if not k.startswith('_')})+'\n' for r in items),encoding='utf-8')
            args=[str(rom),str(firmware),str(fetched),str(history),hashlib.sha256(history.read_bytes()).hexdigest(),hashlib.sha256(fetched.read_bytes()).hexdigest(),str(report)]
            result=subprocess.run([str(exe),'inspect-sp-pi-fetch-lineage',*args],capture_output=True,text=True)
            assert (result.returncode==0)==ok,result.stderr
            if not ok:return
            subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],check=True,capture_output=True)
            doc=json.loads(report.read_bytes())
            expected,_=model.inspect(events)
            assert doc['projection']['dma_egress']==expected
            return doc
        doc=run(copy.deepcopy(rows));facts=doc['sp_dma_consumption'];receipt=doc['projection']['dma_egress']['samples'][0]
        assert facts['fully_compatible_fetches']==1 and facts['unknown_fetches']==1
        assert all(b['writer']['kind']['kind']=='rsp_scalar_sink' for b in facts['samples'][0]['bytes'])
        assert facts['samples'][0]['bytes'][0]['read_ordinal']==receipt['read_ordinal']
        assert doc['fully_attributed_fetches']==0 # Computed RAM bytes never become PI origins.
        assert not any(doc[k] for k in ('native_complete','mutation_coverage_certified','executable_lifetime_certified'))
        # The exact read freezes parents before a same-value external SP cut.
        changed=copy.deepcopy(rows);at=next(i for i,r in enumerate(changed) if r['record']=='sp_dma_egress_read')+1
        cut=dict(record='rsp_dmem_effect',pc=changed[at-1]['pc'],offset=3,bytes=1,value=17,store_scope=0)
        changed.insert(at,cut);assert run(changed)['sp_dma_consumption']['fully_compatible_fetches']==1
        changed=copy.deepcopy(rows);changed.insert(at-1,cut)
        assert run(changed)['sp_dma_consumption']['partially_compatible_fetches']==1
        # RAM cuts after installation revoke lanes; cuts after the actual CPU
        # read preserve that read's frozen parents at the subsequent fetch.
        for after_read,full in ((False,False),(True,True)):
            changed=copy.deepcopy(rows);at=max(i for i,r in enumerate(changed) if r['record']==('scalar' if after_read else 'fetch_begin'))
            changed.insert(at+int(after_read),dict(record='storage_effect',pc=0xffffffffa0002000,kind=0,address=0x2003,bytes=1,value=17))
            result=run(changed)['sp_dma_consumption'];assert bool(result['fully_compatible_fetches'])==full
            assert bool(result['partially_compatible_fetches'])!=full
        for case in ('value','device','address','late','missing','duplicate','legacy','width','bank'):
            changed=copy.deepcopy(rows);read=next(i for i,r in enumerate(changed) if r['record']=='sp_dma_egress_read');write=next(i for i,r in enumerate(changed) if r.get('_egress_write')=='copy' and r['record']=='scalar');end=write+1
            if case=='value':changed[write]['value']^=1
            elif case=='device':changed[write]['device']=3
            elif case=='address':changed[write]['aligned_address']+=4
            elif case=='late':changed.insert(end,dict(record='storage_effect',pc=changed[end]['pc'],kind=0,address=0x2000,bytes=1,value=0))
            elif case=='missing':changed.pop(end)
            elif case=='duplicate':changed.insert(end+1,copy.deepcopy(changed[end]))
            elif case=='legacy':changed[0].update(format='plaid-ares-access-history-v10',policy='observed_instruction_scoped_scalar_rsp_stores_with_rooted_operands_and_pi_queue_sp_backing')
            elif case=='width':changed[read]['bytes']=8
            elif case=='bank':changed[read]['bank']=2
            run(changed,False)
        # The cache retains the copied generation after backing RAM changes.
        for before_fill in (False,True):
            changed=copy.deepcopy(rows);paired=copy.deepcopy(fetch)
            at=max(i for i,r in enumerate(changed) if r['record']=='fetch_begin')
            words=[0x1111,0,0,0,0,0,0,0];pc=0xffffffff80002000;slot=(pc>>5)&511
            changed[at+1:at+2]=[
                dict(record='burst',pc=pc,write=False,address=0x2000,bytes=32,device=1,words=words),
                dict(record='fill',pc=pc,slot=slot,physical=0x2000,index=0,words=words)]
            for r in changed[at:-1]:
                r['pc']=pc
                if 'cached' in r:r['cached']=True
                if 'vaddr' in r:r['vaddr']=pc
            changed.insert(at if before_fill else at+3,dict(record='storage_effect',pc=pc,kind=0,address=0x2003,bytes=1,value=17))
            paired[2].update(pc=pc,cached=True,cache_line=dict(slot=slot,tag_key=0x2001,index=0,words=words))
            facts=run(changed,fetches=paired)['sp_dma_consumption']
            assert bool(facts['fully_compatible_fetches'])!=before_fill
            assert bool(facts['partially_compatible_fetches'])==before_fill
            assert facts['samples'][0]['fill_ordinal'] is not None
    print('PASS raw RSP store / frozen reverse-DMA / RAM executable graph and adversarial cuts')
if __name__=='__main__':main()
