"""Causal scalar RSP stores become fresh SP writers at executable consumption."""
from pathlib import Path
import copy,hashlib,importlib.util,json,os,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def source():
 prior=load('prior',ROOT/'spikes/091-raw-rsp-executable-consumption/test_consumer.py');clock=load('clock',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
 scalar=load('scalar',ROOT/'spikes/093-rsp-scalar-executable/verify.py');model=load('pi_model',ROOT/'spikes/038-boot-pi-fetch-lineage/replay.py')
 data,fw,rows,fetch=prior.source();rows[0].update(format='plaid-ares-access-history-v10',policy='observed_instruction_scoped_scalar_rsp_stores_with_rooted_operands_and_pi_queue_sp_backing')
 at=next(i for i,r in enumerate(rows) if r['record']=='rsp_imem_read');pc=rows[at]['pc'];before=[0]*32;after=before.copy();after[8]=0x1111
 rows.insert(at,dict(record='rsp_operand_root',pc=pc,epoch=1,rsp_pc=0,registers=before.copy()))
 for r in rows:
  if r['record']=='rsp_instruction':r['registers']=before.copy() if r['begin'] else after.copy();r['_instruction_id']='ori'
  elif r['record']=='rsp_dmem_effect':r['store_scope']=0
 at=next(i for i,r in enumerate(rows) if r['record']=='rsp_instruction' and not r['begin'])+1
 word=0xac080000
 tail=[dict(record='sp_word',pc=pc,write=True,address=0x04001004,bank=1,offset=4,bytes=4,value=word,cpu=False),
  dict(record='rsp_imem_read',pc=pc,address=4,offset=4,word=word,_read_id='store'),
  dict(record='rsp_instruction',pc=pc,begin=True,rsp_pc=4,word=word,next_pc=4,halted=False,_read_id='store',registers=after.copy(),_instruction_id='store'),
  dict(record='rsp_scalar_store_scope',pc=pc,begin=True,kind=2,_instruction_id='store',_scope_id='store')]
 tail += [dict(record='rsp_dmem_effect',pc=pc,offset=i,bytes=1,value=v,_scope_id='store') for i,v in enumerate(bytes.fromhex('00001111'))]
 tail += [dict(record='rsp_scalar_store_scope',pc=pc,begin=False,kind=2,_instruction_id='store',_scope_id='store'),
  dict(record='rsp_instruction',pc=pc,begin=False,rsp_pc=4,word=word,next_pc=8,halted=False,_read_id='store',registers=after.copy(),_instruction_id='store')]
 rows[at:at]=tail
 last=max(i for i,r in enumerate(rows) if r['record']=='fetch_begin')
 for r in rows[last:-1]:
  r['pc']=0xffffffffa4000000
  if r['record']=='sp_word':r.update(address=0x04000000,bank=0,offset=0,value=0x1111)
  elif r['record']=='fetch':r.update(physical=0x04000000,word=0x1111)
  elif r['record'] in ('fetch_begin','fetch_end'):r.update(vaddr=0xffffffffa4000000,translated=0x04000000,bus=0x04000000);r.update(value=0x1111) if r['record']=='fetch_end' else None
 fetch[2].update(pc=0xffffffffa4000000,physical=0x04000000,word=0x1111)
 return data,fw,rows,fetch

def main():
 data,fw,rows,fetch=source()
 pc=next(r['pc'] for r in rows if r['record']=='rsp_imem_read')
 clock=load('clock',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
 scalar=load('scalar',ROOT/'spikes/093-rsp-scalar-executable/verify.py')
 model=load('pi_model',ROOT/'spikes/038-boot-pi-fetch-lineage/replay.py')
 exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
 with tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='rsp-store-') as temp:
  p=Path(temp);rom=p/'rom.z64';firmware=p/'firmware.bin';history=p/'history.ndjson';fetched=p/'fetch.ndjson';report=p/'report.json';rom.write_bytes(data);firmware.write_bytes(fw)
  def run(events,ok=True):
   clock.reclock(events);reads={};instructions={};scopes={}
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
   for path,items in [(history,events),(fetched,fetch)]:path.write_text(''.join(json.dumps({k:v for k,v in r.items() if not k.startswith('_')})+'\n' for r in items),encoding='utf-8')
   h=hashlib.sha256(history.read_bytes()).hexdigest();f=hashlib.sha256(fetched.read_bytes()).hexdigest();args=[str(rom),str(firmware),str(fetched),str(history),h,f,str(report)]
   result=subprocess.run([str(exe),'inspect-sp-pi-fetch-lineage',*args],capture_output=True,text=True);assert (result.returncode==0)==ok,result.stderr
   if not ok:return
   doc=json.loads(report.read_bytes());assert doc['projection']['rsp_scalar_producers']==scalar.inspect(events,stores=True)
   expected,_,_=model.inspect(history,fetched,data)
   for k,v in expected.items():assert doc[k]==v,k
   subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],check=True,capture_output=True)
   writers=p/'writers.json';subprocess.run([str(exe),'inspect-sp-writer-fetch',*args[:-1],str(writers)],check=True,capture_output=True)
   return doc,json.loads(writers.read_bytes())
  doc,writers=run(copy.deepcopy(rows));facts=doc['projection']['rsp_scalar_producers'];store=facts['stores']['samples'][0]
  assert facts['stores']['effects']==4 and store['value_source']=={'kind':'definition','context':facts['samples'][0]['definition']['context']}
  assert writers['fully_compatible_fetches']==1
  assert all(w['kind']['kind']=='rsp_scalar_sink' and w['kind']['source_definition']==store['value_source']['context'] for w in writers['samples'][0]['writers'])
  assert doc['fully_attributed_fetches']==0 # Never substitute PI origins for a computed store.
  # Equal external writes are different actors, even inside a completed method interval.
  changed=copy.deepcopy(rows);finish=next(i for i,r in enumerate(changed) if r['record']=='rsp_scalar_store_scope' and not r['begin'])
  changed.insert(finish,dict(record='rsp_dmem_effect',pc=pc,offset=3,bytes=1,value=17,store_scope=0))
  _,partial=run(changed);assert partial['partially_compatible_fetches']==1
  assert partial['samples'][0]['writers'][3] is None
  for case in ['missing_scope','wrong_method','wrong_owner','wrong_lane','wrong_value','unowned_effect','incomplete','reused_scope','legacy']:
   changed=copy.deepcopy(rows);scope=next(i for i,r in enumerate(changed) if r['record']=='rsp_scalar_store_scope')
   if case=='missing_scope':changed.pop(scope)
   elif case=='wrong_method':changed[scope]['kind']=1
   elif case=='wrong_owner':changed[scope]['_instruction_id']='ori'
   elif case=='wrong_lane':changed[scope+1]['offset']=1
   elif case=='wrong_value':changed[scope+1]['value']=2
   elif case=='unowned_effect':changed[scope+1].pop('_scope_id');changed[scope+1]['store_scope']=0
   elif case=='incomplete':changed.pop(scope+1)
   elif case=='reused_scope':changed.insert(scope+1,copy.deepcopy(changed[scope]))
   else:changed[0].update(format='plaid-ares-access-history-v9',policy='observed_storage_sp_execution_and_rooted_scalar_operands_with_pi_queue_sp_backing')
   run(changed,False)
 print('PASS exact scalar actor/effect scopes -> fresh SP writers -> CPU executable backing, held definition ancestry, no false PI origins, malformed/legacy rejection')
if __name__=='__main__':main()
