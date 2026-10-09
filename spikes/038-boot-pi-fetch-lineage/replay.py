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
    assert header['format'] == 'plaid-ares-access-history-v2'
    assert header['lifecycle_policy'] == 'single_run_no_host_restore'
    assert header['rom_sha256'] == paired_header['rom_sha256'] == hashlib.sha256(source).hexdigest()
    assert header['firmware_sha256'] == paired_header['boot_inputs']['firmware_sha256']
    ram, resident, samples = {}, {}, {}
    half = burst = last_fill = writer = active = pending = None
    buffer = [None]*128
    digest = hashlib.sha256()
    count = full = partial = byte_count = words = contradictions = ordinal = 0
    ended = False

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

    for e in history:
        assert not ended
        kind = e['record']
        if kind == 'end':
            assert e['record_count'] == ordinal and e['fetch_count'] == count
            ended = True
            continue
        ordinal += 1
        assert e['ordinal'] == ordinal <= 100000000
        if kind == 'pi_rom_half':
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
            elif event == 4: writer = None
            elif event == 5 and writer is not None:
                assert (writer['pi']['transfer'],writer['pi']['lane'],writer['address'],writer['value']) \
                    == (e['transfer'],e['lane'],e['dram'],e['value'])
                offset = buffer[e['lane']]
                if offset is not None:
                    assert source[offset] == e['value']
                    ram[e['dram']] = (offset,writer['ordinal'],e['transfer'])
                else: ram.pop(e['dram'],None)
                writer = None
        elif kind == 'scalar':
            assert e['bytes'] in (1,2,4,8)
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
        elif kind == 'fetch_begin': active = []
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
                if o is not None: digest.update(struct.pack('>3Q',*o))
            if known:
                key = (e['pc'],e['physical'],e['word'],e['cached'],fill if fill is not None else -1,
                    read if read is not None else -1,tuple(o if o is not None else (-1,-1,-1) for o in origins))
                if key not in samples:
                    samples[key] = dict(pc=e['pc'],physical=e['physical'],word=e['word'],cached=e['cached'],
                        fill_ordinal=fill,read_ordinal=read,bytes=[None if o is None else
                            dict(rom_offset=o[0],writer_ordinal=o[1],transfer=o[2]) for o in origins],
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
    assert fetch_hash == rust['projection']['projection']['projection']['fetch_sha256']
    for key,value in result.items(): assert rust[key] == value,key
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS independent lineage replay:',result['fetches'],'fetches;',result['fully_attributed_fetches'],
        'full;',result['partially_attributed_fetches'],'partial;',len(result['samples']),'samples',flush=True)
    print('ORDERED_CHAINS_SHA256='+result['ordered_fetch_chains_sha256'],flush=True)


if __name__ == '__main__': main()
