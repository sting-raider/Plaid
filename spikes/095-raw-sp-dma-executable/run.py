"""Pinned actual reverse-DMA effects, frozen read identities and controls."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/raw-sp-dma-executable-primary'
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 if os.name=='nt':
  script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',str(HERE/'run.py')],text=True).strip()
  subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script,*sys.argv[1:]],check=True);return
 builder=load('builder',ROOT/'spikes/003-ares-oracle/run.py');OUTPUT.mkdir(parents=True,exist_ok=True)
 if '--verify-existing' not in sys.argv:
  for name,sensor in (('baseline',False),('sensor',True)):
   print('Building',name,flush=True)
   executable=builder.build(HERE/('driver.cpp' if sensor else 'baseline.cpp'),OUTPUT/name,
    raw_fetch_access=True,physical_fetch_access=True,pi_dma_access=sensor,rdram_scalar_access=sensor,
    memory_mutation_access=sensor,sp_backing_access=sensor,rsp_dmem_access=sensor,rsp_instruction_fetch_access=sensor,
    rsp_scalar_store_access=sensor,sp_dma_egress_access=sensor,
    extra_sources=[HERE/'driver.cpp',ROOT/'spikes/088-pi-storage-executable/driver.cpp',ROOT/'spikes/089-pi-dma-sp-consumption/driver.cpp',
     ROOT/'spikes/090-rsp-dmem-storage-cuts/driver.cpp',ROOT/'spikes/091-raw-rsp-executable-consumption/driver.cpp',ROOT/'spikes/092-imem-storage-cuts/driver.cpp',
     ROOT/'spikes/093-rsp-scalar-executable/driver.cpp',ROOT/'spikes/094-rsp-scalar-store-actor/driver.cpp',
     ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp',ROOT/'spikes/006-ares-rom-source/driver.cpp'])
   for mode in ('plain','traced','repeat'):
    (OUTPUT/f'{name}-{mode}.json').write_bytes(subprocess.check_output([str(executable),'plain' if mode=='plain' else 'traced'],timeout=60))
 results={name:{mode:json.loads((OUTPUT/f'{name}-{mode}.json').read_bytes()) for mode in ('plain','traced','repeat')} for name in ('baseline','sensor')}
 states=results['baseline']['plain']['states']
 for name in results:
  for mode,run in results[name].items():
   assert run['states']==states
   if name=='baseline' or mode=='plain':assert run['events']==[]
 assert results['sensor']['traced']==results['sensor']['repeat']
 events=results['sensor']['traced']['events'];reads={};stores=[]
 model=load('egress',HERE/'verify.py');expected,_=model.inspect(events)
 for i,r in enumerate(events):
  assert r['ordinal']==i+1
  if r['record']=='sp_dma_egress_read':reads[r['ordinal']]=r
  elif r['record']=='sp_dma_egress_store':
   read=reads.pop(r['read_ordinal']);write=events[i-1]
   assert write['ordinal']==r['write_ordinal'] and write['record']=='scalar' and write['write'] and write['device']==4
   assert (write['address'],write['bytes'],write['value'])==(read['dram'],read['bytes'],read['value'])
   stores.append((read,write,r))
 assert not reads and len(stores)==6 and {r['bank'] for r,w,e in stores}=={0,1}
 artifacts={str(p.relative_to(OUTPUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUTPUT.glob('*/*.json')}
 for name in results:
  for mode in results[name]:
   p=OUTPUT/f'{name}-{mode}.json';artifacts[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
  p=OUTPUT/name/'oracle';artifacts[str(p.relative_to(OUTPUT))]=hashlib.sha256(p.read_bytes()).hexdigest()
 receipt=dict(format='plaid-raw-sp-dma-executable-receipt-v0',revision=builder.REV,records=len(events),checkpoints=len(states),stores=len(stores),
  ordered_stores_sha256=expected['ordered_stores_sha256'],
  controls_equal=True,repeat_equal=True,artifacts=artifacts,mutation_census_certified=False,executable_lifetime_certified=False,native_complete=False)
 (OUTPUT/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
 print('PASS actual DMEM/IMEM reads -> exact completed RAM sinks, complete baseline/disabled/enabled/repeat controls',flush=True)
 print(json.dumps(receipt,sort_keys=True),flush=True)
if __name__=='__main__':main()
