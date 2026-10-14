"""Independent observed-byte replay; no complete mutation/lifetime certificate."""
from pathlib import Path
import argparse
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'target/ares-boot-pi-queue-history-spike/queue/610000'


def unique(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, 'duplicate field'
        result[key] = value
    return result


def rows(path, digest):
    with path.open('rb') as stream:
        for raw in stream:
            assert len(raw) <= 1024*1024 and raw.endswith(b'\n')
            digest.update(raw)
            yield json.loads(raw, object_pairs_hook=unique)


def inspect(history_path, fetch_path, source):
    history_hash, fetch_hash = hashlib.sha256(), hashlib.sha256()
    history = rows(history_path, history_hash)
    fetched = rows(fetch_path, fetch_hash)
    header, paired_header = next(history), next(fetched)
    assert header['format'] in ('plaid-ares-access-history-v2', 'plaid-ares-access-history-v3', 'plaid-ares-access-history-v5','plaid-ares-access-history-v6','plaid-ares-access-history-v7','plaid-ares-access-history-v8','plaid-ares-access-history-v9')
    operands = header['format'] == 'plaid-ares-access-history-v9'
    imem_storage = header['format'] in ('plaid-ares-access-history-v8','plaid-ares-access-history-v9')
    rsp_execution = header['format'] in ('plaid-ares-access-history-v7','plaid-ares-access-history-v8','plaid-ares-access-history-v9')
    dmem_storage = header['format'] in ('plaid-ares-access-history-v6','plaid-ares-access-history-v7','plaid-ares-access-history-v8','plaid-ares-access-history-v9')
    storage_clock = header['format'] in ('plaid-ares-access-history-v5','plaid-ares-access-history-v6','plaid-ares-access-history-v7','plaid-ares-access-history-v8','plaid-ares-access-history-v9')
    if storage_clock:
        assert header['policy'] == ('observed_storage_sp_execution_and_rooted_scalar_operands_with_pi_queue_sp_backing' if operands else 'observed_storage_dmem_imem_and_rsp_consumption_with_pi_queue_sp_backing' if imem_storage else 'observed_storage_dmem_and_performed_rsp_instructions_with_pi_queue_sp_backing' if rsp_execution else 'observed_ordinary_storage_and_dmem_mutations_with_pi_queue_sp_backing' if dmem_storage else 'observed_ordinary_storage_mutations_and_pi_queue_sp_backing')
    if header['format'] == 'plaid-ares-access-history-v3':
        assert header['policy'] == 'identity_ram_pi_queue_and_observed_sp_backing'
    assert header['lifecycle_policy'] == 'single_run_no_host_restore'
    assert header['rom_sha256'] == paired_header['rom_sha256'] == hashlib.sha256(source).hexdigest()
    assert header['firmware_sha256'] == paired_header['boot_inputs']['firmware_sha256']
    ram, resident, samples = {}, {}, {}
    half = burst = last_fill = writer = active = pending = None
    storage_attempt = None
    sp_memory,sp_receipts={},[]
    active_bus=None
    buffer = [None]*128
    digest = hashlib.sha256()
    count = full = partial = byte_count = words = contradictions = ordinal = 0
    ended = False
    rsp_active=None; rsp_reads={}; rsp_samples={}; rsp_digest=hashlib.sha256()
    rsp_count=rsp_full=rsp_partial=0

    def backing(address, values):
        nonlocal contradictions
        assert 0 <= address <= 8388608-len(values)
        origins = []
        for n, value in enumerate(values):
            a = address+n
            origin = ram.get(a)
            if origin is not None and source[origin[0]] != value:
                contradictions += 1
                ram.pop(a); origin = None
            origins.append(origin)
        return origins

    def origin_wire(origin):
        result=dict(rom_offset=origin[0],writer_ordinal=origin[1],transfer=origin[2])
        if len(origin)==4:
            ordinal,index,dram,read=origin[3]
            result['sp_writer']=dict(write_ordinal=ordinal,byte_index=index,
                kind=dict(kind='dma_sink',dram=dram,read_ordinal=read))
        return result

    def sp_read(bank,offset,word):
        parents=[]
        for n,value in enumerate(word.to_bytes(4,'big')):
            address=bank*4096+offset+n
            if address in sp_memory and sp_memory[address][0]!=value:sp_memory.pop(address)
            parents.append(sp_memory.get(address,(0,None))[1])
        return parents

    for e in history:
        assert not ended
        kind = e['record']
        if kind == 'end':
            assert e['record_count'] == ordinal and e['fetch_count'] == count and rsp_active is None
            ended = True
            continue
        ordinal += 1
        assert e['ordinal'] == ordinal <= 100000000
        if kind not in ('storage_effect','sp_dma_store','rsp_dmem_effect','imem_storage_effect','rsp_operand_root') and not \
            (kind=='scalar' and not e['write'] and e['device']==4):
            sp_receipts=[]
        if kind not in ('rsp_instruction','rsp_imem_read','rsp_dmem_effect','imem_storage_effect','rsp_operand_root','sp_word','sp_dma_store','storage_effect') and rsp_active is None:
            rsp_reads.clear()
        if kind == 'rsp_operand_root':
            assert operands and rsp_active is None
            continue
        if kind == 'imem_storage_effect':
            assert imem_storage
            if e['kind']==0:
                assert e['bytes'] in (1,2,4) and e['offset']%e['bytes']==0
                assert 0 <= e['offset'] <= 4096-e['bytes'] and 0 <= e['value'] < 1<<(8*e['bytes'])
            else:assert e['kind'] in (1,2) and (e['offset'],e['bytes'],e['value'])==(0,4096,0)
            for offset in range(e['offset'],e['offset']+e['bytes']):sp_memory.pop(4096+offset,None)
        elif kind == 'rsp_imem_read':
            assert rsp_execution and active is None
            assert 0 <= e['address'] <= 4099 and e['offset']==e['address']&0xffc
            if rsp_active is None:
                assert e['address']<4096
                rsp_reads.clear();logical=e['address']
            else:
                assert not rsp_reads and e['address']==rsp_active[0]['rsp_pc']+4
                logical=None
            rsp_reads[e['ordinal']]=(e,sp_read(1,e['offset'],e['word']),logical)
        elif kind == 'rsp_instruction':
            assert rsp_execution and active is None
            assert 0 <= e['rsp_pc'] < 4096 and 0 <= e['next_pc'] < 4096
            if e['begin']:
                assert rsp_active is None and e['next_pc']==e['rsp_pc']
                read,parents,logical=rsp_reads.pop(e['read_ordinal'])
                assert (read['pc'],read['word'],logical)==(e['pc'],e['word'],e['rsp_pc'])
                rsp_active=(e,read,parents)
            else:
                assert rsp_active is not None
                begin,read,parents=rsp_active;rsp_active=None
                assert all(begin[k]==e[k] for k in ('pc','rsp_pc','word','read_ordinal'))
                for identity,(pending,values,_) in list(rsp_reads.items()):rsp_reads[identity]=(pending,values,e['next_pc'])
                known=sum(o is not None for o in parents)
                rsp_count+=1;rsp_full+=known==4;rsp_partial+=0<known<4
                wire=[None if o is None else origin_wire(o) for o in parents]
                occurrence=dict(read_ordinal=read['ordinal'],begin_ordinal=begin['ordinal'],end_ordinal=e['ordinal'],
                    rsp_pc=e['rsp_pc'],read_address=read['address'],fetch_offset=read['offset'],
                    word=e['word'],next_pc=e['next_pc'],begin_halted=begin['halted'],halted=e['halted'],bytes=wire)
                rsp_digest.update((json.dumps(occurrence,separators=(',',':'))+'\n').encode())
                key=(e['rsp_pc'],read['address'],read['offset'],e['word'],e['next_pc'],begin['halted'],e['halted'],
                    tuple((-1,-1,-1,(-1,-1,-1,-1)) if o is None else o for o in parents))
                if key not in rsp_samples:
                    rsp_samples[key]=dict(rsp_pc=e['rsp_pc'],read_address=read['address'],fetch_offset=read['offset'],
                        word=e['word'],next_pc=e['next_pc'],begin_halted=begin['halted'],halted=e['halted'],bytes=wire,
                        first_read_ordinal=read['ordinal'],first_begin_ordinal=begin['ordinal'],first_end_ordinal=e['ordinal'],
                        last_begin_ordinal=begin['ordinal'],last_read_ordinal=read['ordinal'],last_end_ordinal=e['ordinal'],observations=0)
                rsp_samples[key].update(last_begin_ordinal=begin['ordinal'],last_read_ordinal=read['ordinal'],last_end_ordinal=e['ordinal'])
                rsp_samples[key]['observations']+=1
        elif kind == 'rsp_dmem_effect':
            assert dmem_storage and active is None
            assert e['bytes'] in (1,2,4,8) and e['offset'] % e['bytes']==0
            assert 0 <= e['offset'] <= 4096-e['bytes'] and 0 <= e['value'] < 1<<(8*e['bytes'])
            for address in range(e['offset'],e['offset']+e['bytes']): sp_memory.pop(address,None)
        elif kind == 'pi_rom_half':
            assert e['value'] == int.from_bytes(source[e['offset']:e['offset']+2], 'big')
            half = e
        elif kind == 'pi_dma':
            event = e['event']
            if event == 2: buffer = [None]*128
            elif event == 3:
                lane = e['lane']
                assert 0 <= lane < 128 and lane % 2 == 0
                joined = half is not None and half['ordinal']+1 == ordinal and half['transfer'] == e['transfer'] \
                    and half['block'] == e['block'] and half['offset']+0x10000000 == e['pbus'] \
                    and half['value'] == e['value']
                offset = half['offset'] if joined else None
                buffer[lane:lane+2] = [offset, offset+1 if offset is not None else None]
                half = None
            elif event == 4:
                writer = None
                storage_attempt = dict(begin=e,effect=None)
            elif event == 5:
                effect = None if storage_attempt is None else storage_attempt['effect']
                if effect is not None:
                    assert effect['ordinal']+(2 if writer is not None else 1) == ordinal
                    assert writer is None or effect['address'] == e['dram']
                sink = writer if writer is not None else effect
                if writer is not None:
                    assert (writer['pi']['transfer'],writer['pi']['lane'],writer['address'],writer['value']) \
                        == (e['transfer'],e['lane'],e['dram'],e['value'])
                if sink is not None:
                    offset = buffer[e['lane']]
                    if offset is not None:
                        assert source[offset] == e['value']
                        ram[sink['address']] = (offset,sink['ordinal'],e['transfer'])
                    else: ram.pop(sink['address'],None)
                writer = storage_attempt = None
        elif kind == 'storage_effect':
            assert storage_clock
            assert set(e) == {'record','ordinal','context','pc','kind','address','bytes','value'}
            if storage_attempt is not None:
                begin = storage_attempt['begin']
                assert (e['kind'],e['bytes'],e['context'],e['pc'],e['value'],e['ordinal']) \
                    == (0,1,0,begin['pc'],begin['value'],begin['ordinal']+1)
                assert storage_attempt['effect'] is None and writer is None
                storage_attempt['effect'] = e
            if e['kind'] == 0:
                assert e['bytes'] in (1,2,4) and e['address'] % e['bytes'] == 0
                assert 0 <= e['address'] <= 8388608-e['bytes'] and 0 <= e['value'] < 1 << (8*e['bytes'])
                for a in range(e['address'],e['address']+e['bytes']): ram.pop(a,None)
            else:
                assert e['kind'] in (1,2) and (e['address'],e['bytes'],e['value']) == (0,8388608,0)
                ram.clear()
        elif kind == 'scalar':
            assert e['bytes'] in (1,2,4,8)
            if not e['write'] and e['device']==4:
                values=e['value'].to_bytes(8,'big')[-e['bytes']:]
                parents=backing(e['aligned_address'],values) if e['address']==e['aligned_address'] \
                    and 0<=e['aligned_address']<=8388608-e['bytes'] else [None]*e['bytes']
                sp_receipts.append((e,parents))
            if e['write']:
                for a in range(e['aligned_address'], e['aligned_address']+e['bytes']): ram.pop(a,None)
                if 'pi' in e: writer = e
            elif e['bytes'] == 4 and e['device'] == 3 and active is not None:
                active.append(e)
        elif kind == 'burst':
            assert e['bytes'] in (16,32) and len(e['words']) == e['bytes']//4
            if e['write']:
                for a in range(e['address'], e['address']+e['bytes']): ram.pop(a,None)
            elif e['bytes'] == 32 and e['device'] == 1:
                backing(e['address'],b''.join(w.to_bytes(4,'big') for w in e['words']))
                burst = e
        elif kind == 'fill':
            address = (e['physical'] & ~4095) | e['index']
            joined = burst is not None and burst['ordinal']+1 == ordinal and burst['context'] == e['context'] \
                and burst['address'] == address and burst['words'] == e['words']
            origins = backing(address,b''.join(w.to_bytes(4,'big') for w in e['words'])) if joined else [None]*32
            resident[e['slot']] = dict(tag=(e['physical'] & ~4095)|1,words=e['words'],
                origins=origins,fill=ordinal if joined else None)
            last_fill = (ordinal,e['slot'])
        elif kind == 'cache_operation':
            slot = e['vaddr'] >> 5 & 511
            r = resident.get(slot)
            nested_fill = e['operation'] == 20 and last_fill == (ordinal-1,slot)
            keep = r is not None and r['tag'] == e['after_tag'] and r['words'] == e['after_words'] \
                and (nested_fill or (e['before_tag'] == e['after_tag'] and e['before_words'] == e['after_words']))
            if not keep: resident.pop(slot,None)
        elif kind == 'sp_dma_store':
            assert e['bank'] in (0,1) and e['bytes'] in (4,8)
            candidates=[n for n,(r,_) in enumerate(sp_receipts) if
                (r['pc'],r['address'],r['bytes'],r['value']) == (e['pc'],e['dram'],e['bytes'],e['value'])]
            read,parents=(sp_receipts.pop(candidates[0]) if len(candidates)==1 else (None,[None]*e['bytes']))
            values=e['value'].to_bytes(8,'big')[-e['bytes']:]
            for n,value in enumerate(values):
                parent=parents[n]
                sp_memory[e['bank']*4096+e['offset']+n]=(value,None if parent is None else
                    (*parent[:3],(ordinal,n,e['dram'],read['ordinal'])))
        elif kind == 'sp_word':
            assert e['bank'] in (0,1) and e['bytes']==4
            parents=[]
            for n,value in enumerate(e['value'].to_bytes(4,'big')):
                address=e['bank']*4096+e['offset']+n
                if e['write']: sp_memory[address]=(value,None)
                elif address in sp_memory and sp_memory[address][0]!=value: sp_memory.pop(address)
                parents.append(sp_memory.get(address,(0,None))[1])
            if not e['write'] and e['cpu'] and active is not None and e['address']==active_bus:
                active.append(dict(e,sp_origins=parents))
        elif kind == 'fetch_begin':
            assert rsp_active is None
            active,active_bus=[],e['bus']
        elif kind == 'fetch_end': pending, active = active, None
        elif kind == 'fetch':
            p = next(fetched)
            assert p['record'] == 'fetch' and e['fetch_seq'] == p['seq'] == count
            assert all(e[k] == p[k] for k in ('pc','word','physical','cached'))
            assert pending is not None
            origins, fill, read = [None]*4, None, None
            if e['cached']:
                line = p['cache_line']; r = resident.get(line['slot'])
                if r is not None:
                    if r['tag'] == line['tag_key'] and r['words'] == line['words']:
                        lane = e['physical'] >> 2 & 7
                        origins = r['origins'][lane*4:lane*4+4]; fill = r['fill']
                    else: resident.pop(line['slot'])
            elif len(pending) == 1 and pending[0]['address'] == e['physical'] and pending[0]['value'] == e['word']:
                if 'sp_origins' in pending[0]:
                    origins=pending[0]['sp_origins']
                    if any(o is not None for o in origins): read=pending[0]['ordinal']
                else:
                    origins = backing(e['physical'],e['word'].to_bytes(4,'big')); read = pending[0]['ordinal']
            pending = None
            known = sum(o is not None for o in origins)
            byte_count += known; full += known == 4; partial += 0 < known < 4
            if origins[0] is not None and all(o is not None and o[2] == origins[0][2]
                and o[0] == origins[0][0]+n for n,o in enumerate(origins)): words += 1
            digest.update(struct.pack('>7Q',count,e['pc'],e['physical'],e['word'],e['cached'],
                fill if fill is not None else (1<<64)-1,read if read is not None else (1<<64)-1))
            for o in origins:
                digest.update(bytes([o is not None]))
                if o is not None:
                    digest.update(struct.pack('>3Q',*o[:3]))
                    if len(o)==4:
                        encoded=json.dumps(origin_wire(o)['sp_writer'],separators=(',',':')).encode()
                        digest.update(b'\xff'+struct.pack('>I',len(encoded))+encoded)
            if known:
                key = (e['pc'],e['physical'],e['word'],e['cached'],fill if fill is not None else -1,
                    read if read is not None else -1,tuple(o if o is not None else (-1,-1,-1) for o in origins))
                if key not in samples:
                    samples[key] = dict(pc=e['pc'],physical=e['physical'],word=e['word'],cached=e['cached'],
                        fill_ordinal=fill,read_ordinal=read,bytes=[None if o is None else origin_wire(o) for o in origins],
                        first_fetch=count,last_fetch=count,observations=0)
                samples[key]['last_fetch'] = count; samples[key]['observations'] += 1
            count += 1
    footer = next(fetched)
    assert ended and footer['record'] == 'end' and footer['fetch_count'] == count
    assert next(fetched,None) is None
    result = dict(fetches=count,fully_attributed_fetches=full,partially_attributed_fetches=partial,
        unattributed_fetches=count-full-partial,observed_rom_byte_fetches=byte_count,
        single_transfer_word_fetches=words,contradicted_backing_bytes=contradictions,
        samples=[samples[k] for k in sorted(samples)],ordered_fetch_chains_sha256=digest.hexdigest(),
        mutation_coverage_certified=False,executable_lifetime_certified=False,native_complete=False)
    if rsp_count:
        result['rsp_consumption']=dict(instructions=rsp_count,fully_attributed_instructions=rsp_full,
            partially_attributed_instructions=rsp_partial,unattributed_instructions=rsp_count-rsp_full-rsp_partial,
            samples=[rsp_samples[k] for k in sorted(rsp_samples)],ordered_instruction_chains_sha256=rsp_digest.hexdigest())
    return result, history_hash.hexdigest(), fetch_hash.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history',type=Path,default=BASE/'traced.ndjson.history.ndjson')
    parser.add_argument('--fetch',type=Path,default=BASE/'traced.ndjson')
    parser.add_argument('--rom',type=Path,default=ROOT/'target/systemtest-spike/n64-systemtest.z64')
    parser.add_argument('--rust-report',type=Path,default=BASE/'rust-fetch-lineage-report.json')
    parser.add_argument('--output',type=Path,default=BASE/'python-fetch-lineage-report.json')
    args = parser.parse_args()
    result, history_hash, fetch_hash = inspect(args.history,args.fetch,args.rom.read_bytes())
    rust = json.loads(args.rust_report.read_text(encoding='utf-8'),object_pairs_hook=unique)
    assert history_hash == rust['projection']['history_sha256']
    projection = rust['projection']
    if rust['format'] in ('plaid-sp-pi-fetch-lineage-report-v0','plaid-sp-pi-fetch-lineage-report-v1','plaid-sp-pi-fetch-lineage-report-v2'):
        projection = projection['projection']
    assert fetch_hash == projection['projection']['projection']['fetch_sha256']
    for key,value in result.items(): assert rust[key] == value,key
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS independent lineage replay:',result['fetches'],'fetches;',result['fully_attributed_fetches'],
        'full;',result['partially_attributed_fetches'],'partial;',len(result['samples']),'samples',flush=True)
    print('ORDERED_CHAINS_SHA256='+result['ordered_fetch_chains_sha256'],flush=True)


if __name__ == '__main__': main()
