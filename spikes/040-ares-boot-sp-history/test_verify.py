"""Adversaries for the original finite SP projection; no reference execution."""
import copy
import io
import json
from verify import inspect,FORMAT,POLICY


def sample(cached=False,mirror=False):
    pc=0xffffffffa4021000 if mirror else 0xffffffffa4001000
    physical=0x04021000 if mirror else 0x04001000
    rows=[dict(record='header',format=FORMAT,policy=POLICY,
        revision='9408cb43d4948fc3ea6e152a307a34348df3fe04',rom_sha256='0'*64,budget=1,
        mapped_cartridge_size=8,firmware_sha256='0'*64,lifecycle_policy='single_run_no_host_restore',
        paired_fetch_format='plaid-ares-fetch-research-v5')]
    def add(kind,context=0,**fields):
        rows.append(dict(record=kind,ordinal=len(rows),context=context,pc=pc,**fields))
    add('scalar',write=False,address=0x1000,aligned_address=0x1000,bytes=8,device=4,value=0x3408111100000000)
    add('sp_dma_store',dram=0x1000,bank=1,offset=0,bytes=8,value=0x3408111100000000)
    add('sp_word',write=True,address=physical,bank=1,offset=0,bytes=4,value=0x34081111,cpu=True)
    context=len(rows)
    add('fetch_begin',context,vaddr=pc,translated=physical,bus=physical,cached=cached,value=0)
    add('sp_word',context,write=False,address=physical,bank=1,offset=0,bytes=4,value=0x34081111,cpu=True)
    add('fetch_end',context,vaddr=pc,translated=physical,bus=physical,cached=cached,value=0x34081111)
    add('fetch',fetch_context=context,fetch_seq=0,word=0x34081111,physical=physical,cached=cached)
    rows.append(dict(record='end',record_count=len(rows)-1,fetch_count=1,reason='instruction_call_budget'))
    return rows


def evaluate(rows):
    stream=io.BytesIO();report=inspect(iter(rows),stream)
    projected=[json.loads(row) for row in stream.getvalue().splitlines()]
    assert projected[0]['format']=='plaid-ares-access-history-v2'
    assert [e['ordinal'] for e in projected[1:-1]]==[1,2,3,4]
    assert projected[2]['context']==projected[3]['context']==2
    assert projected[4]['context']==0 and projected[4]['fetch_context']==2
    return report


def main():
    result=evaluate(sample())
    assert result['sp_backed_fetches']==1 and len(result['samples'])==1
    assert result['dma_store_receipts'][0]['read_ordinal']==1
    assert all(result[k] is False for k in ('mutation_coverage_certified','executable_lifetime_certified','native_complete'))
    assert evaluate(sample(mirror=True))['samples'][0]['physical']==0x04021000
    assert evaluate(sample(cached=True))['sp_backed_fetches']==0
    rows=sample();rows[5]['cpu']=False
    assert evaluate(rows)['sp_backed_fetches']==0
    for duplicate in (False,True):
        rows=sample()
        if duplicate:rows.insert(5,copy.deepcopy(rows[5]))
        else:rows.pop(5)
        for n,e in enumerate(rows[1:-1],1):e['ordinal']=n
        rows[-1]['record_count']=len(rows)-2
        assert evaluate(rows)['sp_backed_fetches']==0
    rows=sample();rows[2]['value']^=1
    assert evaluate(rows)['dma_store_receipts'][0]['read_ordinal'] is None
    rows=sample();rows.insert(2,copy.deepcopy(rows[3]))
    for n,e in enumerate(rows[1:-1],1):e['ordinal']=n
    for e in rows:
        if e.get('context')==4:e['context']=5
        if 'fetch_context' in e:e['fetch_context']=5
    rows[-1]['record_count']=len(rows)-2
    result=evaluate(rows)
    assert result['dma_store_receipts'][0]['read_ordinal'] is None and result['unconsumed_dma_read_receipts']==1
    cases=[('bank',0),('offset',4),('bytes',1),('value',0),('context',0),('cpu',1),('address',0x04040000),('surprise',1)]
    for field,value in cases:
        rows=sample();rows[5][field]=value
        try:inspect(iter(rows),io.BytesIO())
        except (AssertionError,KeyError):continue
        raise AssertionError('forged SP read accepted: '+field)
    for field,value in [('record_count',6),('fetch_count',0),('reason','other')]:
        rows=sample();rows[-1][field]=value
        try:inspect(iter(rows),io.BytesIO())
        except AssertionError:continue
        raise AssertionError('forged footer accepted: '+field)
    print('PASS finite SP projection, mirrors/cached/foreign reads, missing DMA receipt and eleven forgeries')


if __name__=='__main__':main()
