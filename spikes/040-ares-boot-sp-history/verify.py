"""Finite SP backing witnesses; strict v3 to complete v2 projection."""
from collections import Counter
import hashlib
import json
import struct

FORMAT='plaid-ares-access-history-v3'
POLICY='identity_ram_pi_queue_and_observed_sp_backing'
COMMON={'record','ordinal','context','pc'}
SP_WORD={'write','address','bank','offset','bytes','value','cpu'}
SP_DMA={'dram','bank','offset','bytes','value'}


def inspect(rows, projection):
    header=next(rows)
    assert header['record']=='header' and header['format']==FORMAT and header['policy']==POLICY
    assert set(header)=={'record','format','revision','rom_sha256','budget','mapped_cartridge_size',
        'firmware_sha256','policy','lifecycle_policy','paired_fetch_format'}
    def emit(row):projection.write((json.dumps(row,separators=(',',':'))+'\n').encode())
    emit(dict(header,format='plaid-ares-access-history-v2',policy='identity_ram_buffered_pi_and_actual_queue_scopes'))
    raw=ordinal=active=mapped_active=pending=mapped_pending=fetches=witnesses=0
    began=None;ended=False;copying=False;reads=[];receipts=[];unconsumed=0;counts=Counter();samples={};links=[]
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
        raw+=1
        assert raw<=100000000 and type(e['ordinal']) is int and e['ordinal']==raw
        assert type(e['context']) is int and type(e['pc']) is int and 0<=e['pc']<1<<64
        if pending:assert kind=='fetch'
        counts[kind]+=1
        dma_read=kind=='scalar' and not e['write'] and e['device']==4
        if kind!='sp_dma_store' and not dma_read:
            unconsumed+=len(receipts);receipts=[]
        if kind=='fetch_begin':
            assert active==pending==0 and e['context']==raw
            active=raw;mapped_active=ordinal+1;began=e;reads=[]
        assert e['context']==active
        if active:assert e['pc']==began['pc']
        if kind in ('sp_word','sp_dma_store'):
            assert not copying
            assert set(e)==COMMON|(SP_WORD if kind=='sp_word' else SP_DMA)
            bools={'write','cpu'} if kind=='sp_word' else set()
            fields=(SP_WORD if kind=='sp_word' else SP_DMA)-bools
            assert all(type(e[k]) is bool for k in bools)
            assert all(type(e[k]) is int and 0<=e[k]<1<<64 for k in fields)
            assert e['bank'] in (0,1) and e['bytes'] in (4,8)
            assert e['offset']<4096 and e['offset']%e['bytes']==0 and e['value']<1<<(8*e['bytes'])
            if kind=='sp_word':
                assert 0x04000000<=e['address']<=0x0403ffff and e['bytes']==4
                assert e['bank']==(e['address']>>12&1) and e['offset']==e['address']&0xffc
                assert not active or not e['write']
                if active and not e['write']:reads.append(e)
            else:
                assert active==0 and e['dram']<1<<24
                matches=[r for r in receipts if r['pc']==e['pc'] and r['address']==e['dram'] and
                    r['bytes']==e['bytes'] and r['value']==e['value']]
                receipt=matches[0] if len(matches)==1 else None
                if receipt is not None:receipts.remove(receipt)
                links.append(dict(write_ordinal=raw,read_ordinal=receipt['ordinal'] if receipt else None,
                    dram=e['dram'],bank=e['bank'],offset=e['offset'],bytes=e['bytes']))
            continue
        if kind=='pi_dma' and e['event']==1:copying=True
        if kind=='pi_dma' and e['event']==7:copying=False
        if kind=='scalar' and not e['write'] and e['device']==4:
            # Successful identity-RAM receipts only; absence/ambiguity stays unknown.
            receipts.append(e)
            assert len(receipts)<=1000000
        if kind=='fetch_end':
            assert active and all(e[k]==began[k] for k in ('pc','vaddr','translated','bus','cached'))
            pending=active;mapped_pending=mapped_active;active=mapped_active=0
            fetched=e
        if kind=='fetch':
            assert pending and e['fetch_context']==pending and e['fetch_seq']==fetches
            assert all(e[k]==fetched[v] for k,v in (('pc','pc'),('physical','bus'),('cached','cached'),('word','value')))
            eligible=[r for r in reads if r['cpu'] and r['address']==e['physical']]
            r=eligible[0] if not e['cached'] and len(eligible)==1 else None
            if r is not None:
                assert r['value']==e['word'];witnesses+=1
                key=(e['pc'],e['physical'],e['word'],r['bank'],r['offset'])
                if key not in samples:
                    samples[key]=dict(pc=e['pc'],physical=e['physical'],word=e['word'],bank=r['bank'],offset=r['offset'],
                        first_fetch=fetches,last_fetch=fetches,first_read_ordinal=r['ordinal'],last_read_ordinal=r['ordinal'],observations=0)
                sample=samples[key];sample.update(last_fetch=fetches,last_read_ordinal=r['ordinal'])
                sample['observations']+=1
            ordered.update(struct.pack('>4Q',fetches,e['pc'],e['physical'],e['word']))
            ordered.update(bytes([r is not None]))
            if r is not None:ordered.update(struct.pack('>3Q',r['bank'],r['offset'],r['ordinal']))
            fetches+=1
        ordinal+=1
        row=dict(e,ordinal=ordinal,context=mapped_active)
        if kind=='fetch_end':row['context']=mapped_pending
        if kind=='fetch':
            row['fetch_context']=mapped_pending;pending=mapped_pending=0
        emit(row)
    assert ended
    return dict(format='plaid-observed-sp-backing-report-v0',scope='finite_actual_cpu_sp_reads_and_observed_stores',
        records=raw,v2_records=ordinal,counts=dict(counts),fetches=fetches,sp_backed_fetches=witnesses,
        other_or_unwitnessed_fetches=fetches-witnesses,samples=[samples[k] for k in sorted(samples)],
        dma_store_receipts=links,unconsumed_dma_read_receipts=unconsumed+len(receipts),ordered_fetch_backing_sha256=ordered.hexdigest(),
        mutation_coverage_certified=False,executable_lifetime_certified=False,native_complete=False)
