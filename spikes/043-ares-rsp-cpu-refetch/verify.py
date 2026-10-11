"""Fixed actual CPU/RSP composition replay; observed writers, not ultimate origin."""
import copy

FIELDS={'kind','ordinal','phase','context','rsp_context','rsp_pc','rsp_word','address','bank','offset','bytes','pc','value','write'}


def verify(events):
    cpu=None;rsp=None;reads=[];samples=[];backing=bytearray(bytes.fromhex('34081111'))
    writers=[None]*4;rsp_writes=[];cpu_writes=[];begins=[];phase=0
    for ordinal,e in enumerate(events,1):
        assert set(e)==FIELDS
        assert all(type(e[k]) is int and 0<=e[k]<(1<<64) for k in FIELDS-{'write'})
        assert type(e['write']) is bool and e['ordinal']==ordinal
        assert 1<=e['phase']<=7
        assert e['phase'] in (phase,phase+1);phase=e['phase']
        assert e['context']==(ordinal if e['kind']==0 else cpu['ordinal'] if cpu else 0)
        assert e['rsp_context']==(ordinal if e['kind']==3 else rsp['ordinal'] if rsp else 0)
        if e['kind'] in (3,4,5):
            assert e['phase'] in (2,4) and cpu is None
            if rsp:assert (e['rsp_pc'],e['rsp_word'])==(rsp['rsp_pc'],rsp['rsp_word'])
        else:assert e['rsp_pc']==e['rsp_word']==0 and rsp is None
        if e['kind']==0:
            assert cpu is None and e['phase'] in (1,3,5,6,7)
            assert not e['write'] and e['value']==e['bytes']==e['bank']==e['offset']==0
            expected=0x6000 if e['phase']==6 else 0x04020000 if e['phase']==5 else 0x04000000
            assert e['address']==expected and e['pc']==(0xffffffffa0000000|expected)
            cpu=e;reads=[]
        elif e['kind']==1:
            assert e['bank']==e['offset']==0 and e['bytes']==4
            if e['write']:
                assert cpu is None and e['phase']==6 and e['pc']==0xffffffffa0006000
                assert e['address']==0x04000000 and e['value']==0x34083333
                backing[:]=e['value'].to_bytes(4,'big');writers[:]=[e['ordinal']]*4;cpu_writes.append(e['ordinal'])
            else:
                assert cpu and e['pc']==cpu['pc'] and e['address']==cpu['address']
                assert e['value']==int.from_bytes(backing,'big');reads.append(e)
        elif e['kind']==2:
            assert cpu and not e['write'] and e['pc']==cpu['pc'] and e['address']==cpu['address']
            assert e['bytes']==4 and e['offset']==e['bank']==0
            if e['phase']==6:assert not reads and e['value']==0xae090000
            else:
                assert len(reads)==1 and reads[0]['value']==e['value']
                samples.append(dict(phase=e['phase'],physical=e['address'],word=e['value'],
                    read_ordinal=reads[0]['ordinal'],writer_ordinals=list(writers)))
            cpu=None
        elif e['kind']==3:
            assert rsp is None and not e['write'] and e['context']==0
            assert e['address']==e['bank']==e['offset']==e['bytes']==e['value']==0
            assert (e['rsp_pc'],e['rsp_word']) in ((0,0xac220000),(4,13))
            begins.append(e);rsp=e;rsp_writes=[]
        elif e['kind']==4:
            assert rsp and rsp['rsp_pc']==0 and e['pc']==rsp['pc']
            assert e['write'] and e['address']==e['bank']==0 and e['bytes']==1
            assert e['offset']==len(rsp_writes)<4 and e['value']==bytes.fromhex('34082222')[e['offset']]
            backing[e['offset']]=e['value'];writers[e['offset']]=e['ordinal'];rsp_writes.append(e['ordinal'])
        else:
            assert e['kind']==5 and rsp and not e['write'] and e['pc']==rsp['pc']
            assert e['address']==rsp['rsp_pc']+4 and e['value']==int(rsp['rsp_pc']==4)
            assert e['bank']==e['offset']==e['bytes']==0
            assert len(rsp_writes)==(4 if rsp['rsp_pc']==0 else 0);rsp=None
    assert cpu is None and rsp is None
    assert len(events)==31 and len(begins)==4 and len(cpu_writes)==1
    assert [(e['phase'],e['rsp_pc'],e['rsp_word']) for e in begins]==[(2,0,0xac220000),(2,4,13),(4,0,0xac220000),(4,4,13)]
    assert [s['phase'] for s in samples]==[1,3,5,7]
    assert samples[0]['writer_ordinals']==[None]*4
    assert all(w is not None for s in samples[1:] for w in s['writer_ordinals'])
    assert samples[1]['word']==samples[2]['word'] and samples[1]['writer_ordinals']!=samples[2]['writer_ordinals']
    assert samples[3]['writer_ordinals']==cpu_writes*4
    return dict(scope='finite_rsp_mutation_to_cpu_backing_reads',records=len(events),samples=samples,
        rsp_primitive_writes=8,cpu_word_writes=1,mutation_coverage_certified=False,executable_lifetime_certified=False,native_complete=False)


def reject_forgeries(events):
    count=0
    for field,value in [('rsp_context',0),('context',1),('offset',4),('value',256),('bytes',4),('bank',1),('rsp_word',13),('pc',0),('extra',0)]:
        forged=copy.deepcopy(events);next(e for e in forged if e['kind']==4)[field]=value
        try:verify(forged)
        except AssertionError:count+=1;continue
        raise AssertionError('forged composed RSP sink accepted '+field)
    # Deleting a repeated same-value effect must fail despite equal final bytes.
    forged=copy.deepcopy(events)
    at=next(n for n,e in enumerate(forged) if e['kind']==4 and e['phase']==4)
    old=forged.pop(at)['ordinal']
    for e in forged:
        if e['ordinal']>old:e['ordinal']-=1
        for field in ('context','rsp_context'):
            if e[field]>old:e[field]-=1
    try:verify(forged)
    except AssertionError:count+=1
    else:raise AssertionError('deleted same-value RSP sink accepted')
    return count
