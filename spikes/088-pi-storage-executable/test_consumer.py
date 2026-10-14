"""Complete existing CLI/model graphs for physical PI storage writer ancestry."""
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


def source(cached):
    previous=load('storage_fixture',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
    data,firmware,old,fetches=previous.source(cached,0)
    rows=[]
    for e in old:
        if e['record']=='storage_effect': continue
        if e['record']=='scalar' and e.get('pi',{}).get('transfer')==1:
            rows.append(dict(record='storage_effect',kind=0,address=e['aligned_address']+0x200000,
                bytes=e['bytes'],value=e['value'],pc=e['pc']))
        else: rows.append(e)
    physical=fetches[2]['physical']+0x200000
    pc=(0xffffffff80000000 if cached else 0xffffffffa0000000)|physical
    begin=max(n for n,e in enumerate(rows) if e['record']=='fetch_begin')
    for e in rows[begin:-1]:
        e['pc']=pc
        if 'vaddr' in e: e['vaddr']=pc
        for key in ('physical','translated','bus','address','aligned_address'):
            if key in e: e[key]=physical
    fetches[2].update(pc=pc,physical=physical)
    if cached: fetches[2]['cache_line']['tag_key']=physical|1
    previous.reclock(rows)
    return data,firmware,rows,fetches


def main():
    previous=load('storage_fixture',ROOT/'spikes/087-storage-writer-fetch-history/test_consumer.py')
    model=load('storage_model',ROOT/'spikes/038-boot-pi-fetch-lineage/replay.py')
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    with tempfile.TemporaryDirectory(dir=ROOT/'target',prefix='pi-storage-') as directory:
        directory=Path(directory)
        rom=directory/'synthetic.z64';firmware=directory/'firmware.bin'
        history=directory/'history.ndjson';fetched=directory/'fetch.ndjson';report=directory/'report.json'
        def run(rows,fetches,ok=True):
            for path,events in [(history,rows),(fetched,fetches)]:
                path.write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
            h=hashlib.sha256(history.read_bytes()).hexdigest();f=hashlib.sha256(fetched.read_bytes()).hexdigest()
            args=[str(rom),str(firmware),str(fetched),str(history),h,f,str(report)]
            result=subprocess.run([str(exe),'inspect-sp-pi-fetch-lineage',*args],capture_output=True,text=True)
            assert (result.returncode==0)==ok,result.stderr
            if not ok: return
            rust=json.loads(report.read_bytes());expected,mh,mf=model.inspect(history,fetched,rom.read_bytes())
            assert (mh,mf)==(h,f)
            for key,value in expected.items(): assert rust[key]==value,key
            subprocess.run([str(exe),'verify-sp-pi-fetch-lineage',*args],check=True,capture_output=True)
            assert not any(rust[k] for k in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'))
            return rust
        for cached in (False,True):
            data,fw,rows,fetches=source(cached);rom.write_bytes(data);firmware.write_bytes(fw)
            rust=run(rows,fetches)
            assert rust['fully_attributed_fetches']==1
            writers=[e['ordinal'] for e in rows if e['record']=='storage_effect']
            assert [b['writer_ordinal'] for b in rust['samples'][0]['bytes']]==writers[:4]
            at=next(n for n,e in enumerate(rows) if e['record']=='storage_effect')
            for variant in range(5):
                changed=copy.deepcopy(rows)
                if variant==0: changed[at]['value']^=1
                elif variant==1: changed[at]['bytes']=2
                elif variant==2: changed[at]['pc']^=4
                elif variant==3: changed.insert(at,copy.deepcopy(changed[at]))
                else: changed[at].update(kind=1,address=0,bytes=8388608,value=0)
                previous.reclock(changed);run(changed,fetches,False)
            for variant in range(3):
                changed=copy.deepcopy(rows)
                if variant==0: changed.pop(at)
                elif variant==1: changed.insert(at-1,changed.pop(at))
                else: changed=[e for e in changed if e['record']!='pi_rom_half']
                previous.reclock(changed);unknown=run(changed,fetches)
                assert unknown['fully_attributed_fetches']==0
                assert unknown['partially_attributed_fetches']==int(variant<2)
    print('PASS two physical PI storage-to-execution CLI/model graphs; ten malformed attempts and six missing-origin controls')


if __name__=='__main__': main()
