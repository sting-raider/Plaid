"""Complete source/CLI/model composition for storage cuts and legacy PI facts."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from test_pi_queue_history import fixture


def reclock(rows):
    active=pending=0
    for ordinal,e in enumerate(rows[1:-1],1):
        e['ordinal']=ordinal
        if e['record']=='fetch_begin': active=ordinal
        e['context']=active
        if e['record']=='fetch_end': pending,active=active,0
        if e['record']=='fetch': e['fetch_context'],pending=pending,0
    rows[-1]['record_count']=len(rows)-2


def source(cached,kind):
    rom,firmware,rows,fetches=fixture()
    rows[0].update(format='plaid-ares-access-history-v5',
        policy='observed_ordinary_storage_mutations_and_pi_queue_sp_backing')
    begin=max(n for n,e in enumerate(rows) if e['record']=='fetch_begin')
    insertion=begin
    pc=rows[begin]['pc']
    physical=fetches[2]['physical']
    if cached:
        pc=0xffffffff80000000|physical
        slot=(pc>>5)&511
        index=physical&0xfe0
        words=[fetches[2]['word'],0,0,0,0,0,0,0]
        rows[begin+1:begin+2]=[
            dict(record='burst',pc=pc,write=False,address=physical,bytes=32,device=1,words=words),
            dict(record='fill',pc=pc,slot=slot,physical=physical,index=index,words=words)]
        for e in rows[begin:-1]:
            e['pc']=pc
            if 'cached' in e: e['cached']=True
            if 'vaddr' in e: e['vaddr']=pc
        fetches[2].update(pc=pc,cached=True,cache_line=dict(slot=slot,tag_key=physical|1,index=index,words=words))
        insertion=begin+3
    rows.insert(insertion,dict(record='storage_effect',pc=pc,kind=kind,
        address=physical+3 if kind==0 else 0,bytes=1 if kind==0 else 8388608,
        value=fetches[2]['word']&255 if kind==0 else 0))
    reclock(rows)
    return rom,firmware,rows,fetches


def main():
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    spec=importlib.util.spec_from_file_location('storage_model',ROOT/'spikes/038-boot-pi-fetch-lineage/replay.py')
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    with tempfile.TemporaryDirectory(prefix='storage-fetch-',dir=ROOT/'target') as temporary:
        output=Path(temporary)
        rom=output/'synthetic.z64';firmware=output/'firmware.bin'
        history=output/'history.ndjson';fetched=output/'fetched.ndjson';report=output/'report.json'
        def write(path,rows): path.write_text(''.join(json.dumps(e)+'\n' for e in rows),encoding='utf-8')
        def run(command,expected_history,expected_fetch,ok=True):
            result=subprocess.run([str(exe),command,str(rom),str(firmware),str(fetched),str(history),
                expected_history,expected_fetch,str(report)],capture_output=True,text=True)
            assert (result.returncode==0)==ok,(command,result.stderr)
        for cached in (False,True):
            for kind in (0,1,2):
                data,fw,rows,fetches=source(cached,kind)
                rom.write_bytes(data);firmware.write_bytes(fw);write(history,rows);write(fetched,fetches)
                h=hashlib.sha256(history.read_bytes()).hexdigest();f=hashlib.sha256(fetched.read_bytes()).hexdigest()
                run('inspect-sp-pi-fetch-lineage',h,f);run('verify-sp-pi-fetch-lineage',h,f)
                rust=json.loads(report.read_bytes());expected,mh,mf=model.inspect(history,fetched,data)
                assert (h,f)==(mh,mf)
                for key,value in expected.items(): assert rust[key]==value,key
                assert rust['fully_attributed_fetches']==int(cached)
                assert rust['partially_attributed_fetches']==int(not cached and kind==0)
                effect=next(n for n,e in enumerate(rows) if e['record']=='storage_effect')
                original=report.read_bytes()
                for field,value in [('kind',3),('kind',4),('bytes',0),('value',1<<40),('extra',True)]:
                    altered=copy.deepcopy(rows);altered[effect][field]=value;write(history,altered)
                    report.write_bytes(original)
                    run('verify-sp-pi-fetch-lineage',h,f,ok=False)
                deleted=copy.deepcopy(rows);deleted.pop(effect);reclock(deleted);write(history,deleted)
                report.write_bytes(original);run('verify-sp-pi-fetch-lineage',h,f,ok=False)
                write(history,rows)
                forged=copy.deepcopy(rust);forged['mutation_coverage_certified']=True
                report.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-sp-pi-fetch-lineage',h,f,ok=False)
        print('PASS six complete storage/PI/cache CLI+independent model graphs; source deletion/edits and false coverage reject')


if __name__=='__main__': main()
