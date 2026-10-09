"""Strict fixed-fixture replay; no general RSP mutation/lifetime certificate."""
import copy
import hashlib
import re

FIELDS={'kind','ordinal','context','phase','pc','word','offset','bytes','next','value','halted'}
COUNTS={'SB':1,'SH':2,'SW-wrap':4,'SW-bit12':4,'SB-equal':1,
        'SBV':1,'SSV':2,'SLV':4,'SDV':8,'SPV':8,'SUV':8,'SHV':8,'SFV':4,'SWV':16,'STV':16}


def write_count(probe):
    name=probe['name'];family=name.split('@')[0]
    if family=='SQV':return 16-(probe['base']&15)
    if family=='SRV':return probe['base']&15
    return COUNTS[family]


def verify(history,machine):
    assert set(history)=={'format','foreign_writes','events'}
    assert history['format']=='plaid-rsp-dmem-component-v0' and history['foreign_writes']==30
    assert machine['probe_count']==len(machine['probes'])==30
    assert len({p['name'] for p in machine['probes']})==30
    active=None;phase=0;instructions=writes=0;by_phase={}
    for ordinal,e in enumerate(history['events'],1):
        assert set(e)==FIELDS
        assert all(type(e[k]) is int and 0<=e[k]<(1<<64) for k in FIELDS-{'halted'})
        assert type(e['halted']) is bool and e['ordinal']==ordinal
        assert 1<=e['phase']<=30
        if e['kind']==0:
            assert active is None and e['context']==ordinal
            if e['phase']!=phase:
                assert e['phase']==phase+1 and e['pc']==0
                phase=e['phase'];probe=machine['probes'][phase-1]
                assert type(probe['initial_word']) is int and 0<=probe['initial_word']<(1<<32)
                initial=probe['initial_word'].to_bytes(4,'big')*1024
                assert hashlib.sha256(initial).hexdigest()==probe['initial_sha256']
                by_phase[phase]=dict(backing=bytearray(initial),initial=initial,words=[],writes=0)
            b=by_phase[phase];b['words'].append(e['word'])
            assert len(b['words'])<=2 and e['pc']==(len(b['words'])-1)*4
            assert e['next']==e['pc'] and not e['halted']
            assert e['offset']==e['bytes']==e['value']==0
            active=e;instructions+=1
        elif e['kind']==1:
            assert active and (e['context'],e['phase'],e['pc'],e['word'])==(active['ordinal'],phase,active['pc'],active['word'])
            assert e['pc']==0 and e['bytes']==1 and 0<=e['offset']<4096 and e['value']<256
            assert e['next']==0 and not e['halted']
            b=by_phase[phase];b['backing'][e['offset']]=e['value'];b['writes']+=1;writes+=1
        else:
            assert e['kind']==2 and active
            assert (e['context'],e['phase'],e['pc'],e['word'])==(active['ordinal'],phase,active['pc'],active['word'])
            assert e['next']==e['pc']+4 and e['halted']==(e['pc']==4)
            assert e['offset']==e['bytes']==e['value']==0
            active=None
    assert active is None and phase==30 and instructions==60
    for phase,probe in enumerate(machine['probes'],1):
        b=by_phase[phase]
        assert b['words']==[probe['instruction'],13]
        assert re.fullmatch('[0-9a-f]{64}',probe['machine_sha256'])
        assert b['writes']==write_count(probe)
        assert hashlib.sha256(b['backing']).hexdigest()==probe['dmem_sha256']
        initial=b['initial']
        assert sum(a!=b for a,b in zip(initial,b['backing']))==probe['changed_dmem']
    assert machine['probes'][-1]['name']=='SB-equal' and machine['probes'][-1]['changed_dmem']==0
    return dict(scope='finite_actual_rsp_instruction_dmem_sinks',probes=30,instructions=instructions,
        primitive_writes=writes,records=len(history['events']),foreign_sinks_excluded=30,
        same_value_write_retained=True,mutation_coverage_certified=False,executable_lifetime_certified=False,native_complete=False)


def reject_forgeries(history,machine):
    rejected=0
    for field,value in [('context',0),('offset',4096),('bytes',2),('value',256),('pc',4),('word',13),('phase',31),('extra',0)]:
        forged=copy.deepcopy(history);row=next(e for e in forged['events'] if e['kind']==1);row[field]=value
        try:verify(forged,machine)
        except AssertionError:rejected+=1;continue
        raise AssertionError('forged RSP sink accepted '+field)
    for phase in (1,30):
        forged=copy.deepcopy(history)
        at=next(n for n,e in enumerate(forged['events']) if e['phase']==phase and e['kind']==1)
        old=forged['events'].pop(at)['ordinal']
        for e in forged['events']:
            if e['ordinal']>old:e['ordinal']-=1
            if e['context']>old:e['context']-=1
        try:verify(forged,machine)
        except AssertionError:rejected+=1;continue
        raise AssertionError('missing actual/same-value RSP sink accepted')
    return rejected
