"""Actual cached store64 subwrites -> canonical resident/writeback ancestry."""
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
FORMAT='plaid-dcache-store64-writeback-history-v2'
REFERENCE='9408cb43d4948fc3ea6e152a307a34348df3fe04'
MODEL='768ff87e0f0690e427a5efad86af02dba7a0a4d56dabceff1adec66bdbfba03e'


def line(words):
    return list(b''.join(w.to_bytes(4,'big') for w in words))


def normalize(case):
    actual=case['traced']
    records=sorted([(e['ordinal'],'cache',e) for e in actual['dcache_events']]
        +[(e['ordinal'],'burst',e) for e in actual['burst_events']],key=lambda item:item[0])
    assert [item[0] for item in records]==list(range(1,len(records)+1))
    steps={s['phase']:s for s in actual['steps']}
    events,parents,owners,expected,receipts=[],{}, {}, [], {}

    def append(record,**fields):
        events.append(dict(record=record,ordinal=len(events)+1,**fields));return len(events)

    def operation(phase):
        s=steps[phase];assert s['before']==s['after'] and s['before'][0]==0
        assert s['word']>>26 in (0x3f,0x2c,0x2d)
        selected=[e for e in actual['dcache_events'] if e['phase']==phase and e['kind']=='store']
        writes=[]
        for sequence,e in enumerate(selected):
            assert e['pc']==s['pc'] and e['bytes'] in (1,2,4,8)
            payload=line(e['words'])[e['paddr']&15:(e['paddr']&15)+e['bytes']]
            handler=(e['paddr']^(8-e['bytes'] if s['little'] else 0))|0x80000000
            writes.append(dict(sequence=sequence,event='raw-write:'+str(e['ordinal']),handler_address=handler,
                               sink_physical=e['paddr'],bytes=e['bytes'],value=int.from_bytes(bytes(payload),'big'),
                               layer='dcache_resident'))
        rs=(s['word']>>21)&31;rt=(s['word']>>16)&31
        immediate=s['word']&65535;immediate-=65536 if immediate&32768 else 0
        receipt=dict(reference_revision=REFERENCE,model_sha256=MODEL,operation_event='decoded-step:'+str(phase),
                     site=s['pc']&0xffffffff,address=(s['before'][rs]+immediate)&0xffffffff,
                     source_value=s['before'][rt],kind=case['operation'].lower(),endian=case['endian'],cached=True,
                     outcome='rejected_before_mutation' if s['exception'] else 'completed',subwrites=writes)
        context=dict(pc=s['pc'],word=s['word'],gpr=s['before'],after_gpr=s['after'],after_pc=s['next'],
                     little=s['little'],exception=s['exception'])
        parents[phase]=append('store64',context=context,receipt=receipt)
        receipts[phase]=receipt

    for original,kind,e in records:
        if kind=='burst':
            assert e['dcache'] and not e['icache'] and e['bytes']==16
            payload=line(e['words'])
            ordinal=append('backing_write' if e['write'] else 'backing_read',physical_line=e['address'],payload=payload)
            if e['write']:
                expected.append(dict(backing_write_ordinal=ordinal,origins=[owners[e['address']+i] for i in range(16)]))
        elif e['kind']=='fill':
            assert e['phase']==0 and e['bytes']==16
            fill=append('fill',slot=e['slot'],physical_line=e['paddr'],payload=line(e['words']))
            for i in range(16):
                owners[e['paddr']+i]=dict(kind='backing_fill',backing_read_ordinal=fill-1,
                                         fill_ordinal=fill,physical=e['paddr']+i)
        elif e['kind']=='store':
            if e['phase'] not in parents:
                operation(e['phase'])
            spec=next(w for w in receipts[e['phase']]['subwrites'] if w['event']=='raw-write:'+str(original))
            payload=line(e['words'])[e['paddr']&15:(e['paddr']&15)+e['bytes']]
            ordinal=append('store64_subwrite',sequence=spec['sequence'],event=spec['event'],physical=e['paddr'],
                           slot=e['slot'],payload=payload,resident_after=line(e['words']))
            for i in range(e['bytes']):
                owners[e['paddr']+i]=dict(kind='store64_subwrite',operation_ordinal=parents[e['phase']],
                                         subwrite_ordinal=ordinal,sequence=spec['sequence'],byte_index=i)
        elif e['kind']=='writeback_begin':
            s=steps[3];assert s['word']==(0x2f<<26)|(1<<21)|(0x19<<16) and e['pc']==s['pc']
            append('writeback_begin',slot=e['slot'],physical_line=e['paddr'])
        elif e['kind']=='writeback_end':
            append('writeback_end',slot=e['slot'])
        else:
            raise AssertionError(e['kind'])
    for phase,s in steps.items():
        if phase in (1,2) and phase not in parents:
            assert s['exception']==5
            operation(phase)
    return dict(format=FORMAT,events=events),expected


def main():
    cargo=shutil.which('cargo') or str(Path.home()/'.cargo/bin/cargo.exe')
    subprocess.run([cargo,'build','--locked','-p','plaid'],cwd=ROOT,check=True)
    exe=ROOT/('target/debug/plaid.exe' if os.name=='nt' else 'target/debug/plaid')
    capture=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'target/store64-writeback-primary/reference/results.json'
    raw=capture.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='28d34bb07660e39fbed5b652d10d687c011622142ae4555828b08a50920bf7aa'
    document=json.loads(raw);assert document['reference']==REFERENCE and document['repeat_equal']
    reports=[];sources=[];exports=0;attempts=0;rejections=0
    with tempfile.TemporaryDirectory(prefix='store64-compose-',dir=ROOT/'target') as temporary:
        directory=Path(temporary);source=directory/'source.json';output=directory/'report.json'

        def save(data):
            source.write_text(json.dumps(data),encoding='utf-8')
            return hashlib.sha256(source.read_bytes()).hexdigest()

        def run(command,digest,ok=True,target=output):
            result=subprocess.run([str(exe),command,str(source),digest,str(target)],capture_output=True,text=True)
            assert (result.returncode==0)==ok,(command,result.stdout,result.stderr)

        for case in document['cases']:
            actual=case['traced'];semantic=lambda d:{k:v for k,v in d.items() if k not in ('dcache_events','burst_events')}
            assert semantic(actual)==semantic(case['baseline'])==semantic(case['disabled'])
            normalized,expected=normalize(case);sources.append(normalized)
            digest=save(normalized);run('inspect-dcache-store64',digest);run('verify-dcache-store64',digest)
            report=json.loads(output.read_bytes());reports.append(report)
            assert len(report['store64_operations'])==len(actual['steps'])-(1 if expected else 0)
            attempts+=len(report['store64_operations']);exports+=len(expected)
            for got,want in zip(report['writeback']['receipts'],expected):
                assert got['backing_write_ordinal']==want['backing_write_ordinal'] and got['origins']==want['origins']
                assert all(o['kind']!='store64_subwrite' or report['store64_operations'][1]['ordinal']==o['operation_ordinal']
                           for o in got['origins'])
            assert len(report['writeback']['receipts'])==len(expected)
            assert not report['writeback']['native_complete'] and not report['cpu_operand_dataflow_certified']
            before=source.read_bytes();run('inspect-dcache-store64',digest,ok=False,target=source);assert source.read_bytes()==before
            run('inspect-dcache-store64','0'*64,ok=False)
            forged=copy.deepcopy(normalized)
            next(e for e in forged['events'] if e['record']=='store64')['context']['word']=0
            run('inspect-dcache-store64',save(forged),ok=False);rejections+=1
            if expected:
                # Deleting a same-value callback must fail even after renumbering.
                forged=copy.deepcopy(normalized)
                last=max(i for i,e in enumerate(forged['events']) if e['record']=='store64_subwrite')
                forged['events'].pop(last)
                for i,e in enumerate(forged['events']):e['ordinal']=i+1
                run('inspect-dcache-store64',save(forged),ok=False);rejections+=1
                forged=copy.deepcopy(normalized)
                next(e for e in forged['events'] if e['record']=='store64_subwrite')['resident_after'][15]^=1
                run('inspect-dcache-store64',save(forged),ok=False);rejections+=1
                save(normalized);output.write_text(json.dumps(report),encoding='utf-8')
                forged=copy.deepcopy(report)
                selected=next(o for o in forged['writeback']['receipts'][0]['origins'] if o['kind']=='store64_subwrite')
                selected['operation_ordinal']=report['store64_operations'][0]['ordinal']
                output.write_text(json.dumps(forged),encoding='utf-8')
                run('verify-dcache-store64',digest,ok=False);rejections+=1
        assert (len(reports),attempts,exports,rejections)==(48,82,34,150)
        for label,data in [('NORMALIZED_SET',sources),('REPORT_SET',reports)]:
            print(label+'_SHA256='+hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    print('PASS 48 actual cases, 82 decoded attempts, 34 exact backing exports and 150 fresh source/report forgeries')


if __name__=='__main__':
    main()
