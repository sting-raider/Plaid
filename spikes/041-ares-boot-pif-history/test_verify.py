"""Synthetic PIF backing/projection adversaries, not reference execution."""
import copy
import hashlib
import io
import json
from verify import FORMAT,POLICY,inspect

FW=bytes(1984)


def sample(physical=0x1fc00000,cached=False):
    pc=0xffffffffa0000000|physical
    rows=[dict(record='header',format=FORMAT,policy=POLICY,revision='9408cb43d4948fc3ea6e152a307a34348df3fe04',
        rom_sha256='0'*64,budget=1,mapped_cartridge_size=8,firmware_sha256=hashlib.sha256(FW).hexdigest(),
        lifecycle_policy='single_run_no_host_restore',paired_fetch_format='plaid-ares-fetch-research-v5')]
    def add(kind,context=0,**fields):rows.append(dict(record=kind,ordinal=len(rows),context=context,pc=pc,**fields))
    add('fetch_begin',1,vaddr=pc,translated=physical,bus=physical,cached=cached,value=0)
    add('pif_rom_word',1,write=False,offset=0,bytes=4,value=0)
    add('fetch_end',1,vaddr=pc,translated=physical,bus=physical,cached=cached,value=0)
    add('fetch',fetch_context=1,fetch_seq=0,word=0,physical=physical,cached=cached)
    rows.append(dict(record='end',record_count=4,fetch_count=1,reason='instruction_call_budget'))
    return rows


def evaluate(rows,firmware=FW):
    out=io.BytesIO();r=inspect(iter(rows),firmware,out)
    p=[json.loads(e) for e in out.getvalue().splitlines()]
    assert p[0]['format']=='plaid-ares-access-history-v3'
    assert [e['ordinal'] for e in p[1:-1]]==[1,2,3]
    assert p[1]['context']==p[2]['context']==p[3]['fetch_context']==1
    return r


def main():
    assert evaluate(sample())['pif_backed_fetches']==1
    assert evaluate(sample(0x1fcff800))['samples'][0]['offset']==0
    assert evaluate(sample(cached=True))['pif_backed_fetches']==0
    for address in (0x1fc007c0,0x1fd00000):assert evaluate(sample(address))['pif_backed_fetches']==0
    for duplicate in (False,True):
        rows=sample()
        if duplicate:rows.insert(2,copy.deepcopy(rows[2]))
        else:rows.pop(2)
        for n,e in enumerate(rows[1:-1],1):e['ordinal']=n
        rows[-1]['record_count']=len(rows)-2
        assert evaluate(rows)['pif_backed_fetches']==0
    # A read observation alone cannot prove equality to supplied firmware.
    rows=sample();rows[2]['value']=rows[3]['value']=rows[4]['word']=7
    r=evaluate(rows);assert r['pif_backed_fetches']==1 and r['supplied_firmware_matching_fetches']==0
    assert not r['samples'][0]['matches_supplied_firmware']
    for field,value in [('bytes',1),('offset',1),('offset',0x7c0),('value',1),('context',0),('write',True),('extra',0)]:
        rows=sample();rows[2][field]=value
        try:evaluate(rows)
        except (AssertionError,KeyError):continue
        raise AssertionError('forged PIF read accepted '+field)
    try:evaluate(sample(),bytes([1])+FW[1:])
    except AssertionError:pass
    else:raise AssertionError('changed firmware accepted')
    rows=sample()
    rows.insert(1,dict(record='pif_rom_write_attempt',ordinal=1,context=0,pc=rows[1]['pc'],
        write=True,offset=0,bytes=4,value=7))
    for n,e in enumerate(rows[1:-1],1):
        e['ordinal']=n
        if e['context']:e['context']=2
        if 'fetch_context' in e:e['fetch_context']=2
    rows[-1]['record_count']=5
    out=io.BytesIO();r=inspect(iter(rows),FW,out)
    assert r['pif_backed_fetches']==1 and len(r['write_attempts'])==1
    assert r['write_attempts'][0]['value']==7
    print('PASS PIF mirrors, cached/latch-equivalent/missing/ambiguous paths, firmware mismatch, no-effect attempt and eight forgeries')


if __name__=='__main__':main()
