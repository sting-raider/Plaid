"""Actual PIF reads/no-effect write attempts and exact complete v3 projection."""
from collections import Counter
import hashlib
import json
import struct

FORMAT='plaid-ares-access-history-v4'
POLICY='identity_ram_pi_queue_sp_and_observed_pif_backing'
COMMON={'record','ordinal','context','pc'}


def inspect(rows,firmware,projection):
    header=next(rows)
    assert set(header)=={'record','format','revision','rom_sha256','budget','mapped_cartridge_size',
        'firmware_sha256','policy','lifecycle_policy','paired_fetch_format'}
    assert header['record']=='header' and header['format']==FORMAT and header['policy']==POLICY
    assert len(firmware)==1984 and hashlib.sha256(firmware).hexdigest()==header['firmware_sha256']
    def emit(row):projection.write((json.dumps(row,separators=(',',':'))+'\n').encode())
    emit(dict(header,format='plaid-ares-access-history-v3',policy='identity_ram_pi_queue_and_observed_sp_backing'))
    raw=ordinal=active=mapped_active=pending=mapped_pending=fetches=witnesses=matching=0
    began=fetched=None;ended=copying=False;reads=[];counts=Counter();samples={};writes=[]
    ordered=hashlib.sha256()
    for e in rows:
        assert not ended
        kind=e['record']
        if kind=='end':
            assert set(e)=={'record','record_count','fetch_count','reason'}
            assert type(e['record_count']) is int and type(e['fetch_count']) is int
            assert e['record_count']==raw and e['fetch_count']==fetches and not active and not pending and not copying
            assert e['reason']=='instruction_call_budget'
            emit(dict(e,record_count=ordinal));ended=True;continue
        raw+=1;assert raw<=100000000 and type(e['ordinal']) is int and e['ordinal']==raw
        assert type(e['context']) is int and type(e['pc']) is int and 0<=e['pc']<1<<64
        if pending:assert kind=='fetch'
        counts[kind]+=1
        if kind=='fetch_begin':
            assert active==pending==0 and e['context']==raw
            active=raw;mapped_active=ordinal+1;began=e;reads=[]
        assert e['context']==active
        if active:assert e['pc']==began['pc']
        if kind in ('pif_rom_word','pif_rom_write_attempt'):
            assert not copying and set(e)==COMMON|{'write','offset','bytes','value'}
            assert type(e['write']) is bool
            assert e['write']==(kind=='pif_rom_write_attempt')
            assert all(type(e[k]) is int for k in ('offset','bytes','value'))
            assert e['bytes']==4 and 0<=e['offset']<=0x7bc and e['offset']%4==0 and 0<=e['value']<1<<32
            if e['write']:
                assert not active;writes.append(dict(ordinal=raw,pc=e['pc'],offset=e['offset'],value=e['value']))
            elif active:reads.append(e)
            continue
        if kind=='pi_dma' and e['event']==1:copying=True
        if kind=='pi_dma' and e['event']==7:copying=False
        if kind=='fetch_end':
            assert active and all(e[k]==began[k] for k in ('pc','vaddr','translated','bus','cached'))
            pending=active;mapped_pending=mapped_active;active=mapped_active=0;fetched=e
        if kind=='fetch':
            assert pending and e['fetch_context']==pending and e['fetch_seq']==fetches
            assert all(e[k]==fetched[v] for k,v in (('pc','pc'),('physical','bus'),('cached','cached'),('word','value')))
            physical=e['physical']
            eligible=[r for r in reads if r['offset']==physical&0x7fc]
            r=eligible[0] if not e['cached'] and 0x1fc00000<=physical<=0x1fcfffff and len(eligible)==1 else None
            equals=False
            if r is not None:
                assert r['value']==e['word'];witnesses+=1
                offset=r['offset'];equals=int.from_bytes(firmware[offset:offset+4],'big')==e['word']
                matching+=equals
                key=(e['pc'],physical,e['word'],offset)
                if key not in samples:
                    samples[key]=dict(pc=e['pc'],physical=physical,word=e['word'],offset=offset,matches_supplied_firmware=equals,
                        first_fetch=fetches,last_fetch=fetches,first_read_ordinal=r['ordinal'],last_read_ordinal=r['ordinal'],observations=0)
                sample=samples[key];sample.update(last_fetch=fetches,last_read_ordinal=r['ordinal']);sample['observations']+=1
            ordered.update(struct.pack('>4Q',fetches,e['pc'],physical,e['word']));ordered.update(bytes([r is not None]))
            if r is not None:ordered.update(struct.pack('>2Q',r['offset'],r['ordinal'])+bytes([equals]))
            fetches+=1
        ordinal+=1;row=dict(e,ordinal=ordinal,context=mapped_active)
        if kind=='fetch_end':row['context']=mapped_pending
        if kind=='fetch':row['fetch_context']=mapped_pending;pending=mapped_pending=0
        emit(row)
    assert ended
    return dict(format='plaid-observed-pif-backing-report-v0',scope='finite_actual_pif_bank_reads_and_write_attempts',
        records=raw,v3_records=ordinal,counts=dict(counts),fetches=fetches,pif_backed_fetches=witnesses,
        supplied_firmware_matching_fetches=matching,other_or_unwitnessed_fetches=fetches-witnesses,
        samples=[samples[k] for k in sorted(samples)],write_attempts=writes,ordered_fetch_backing_sha256=ordered.hexdigest(),
        mutation_coverage_certified=False,executable_lifetime_certified=False,native_complete=False)
