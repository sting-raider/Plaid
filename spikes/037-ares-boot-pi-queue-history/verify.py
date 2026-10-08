"""Strict research-v2 request/queue replay with exact complete v1 projection."""
from collections import Counter
import json

FORMAT = 'plaid-ares-access-history-v2'
POLICY = 'identity_ram_buffered_pi_and_actual_queue_scopes'
COMMON = {'record', 'ordinal', 'context', 'pc'}
EXTRA = {
    'queue': {'kind', 'slot', 'other', 'event', 'clock', 'valid', 'token', 'request', 'active_request'},
    'pi_request_begin': {'request', 'direction', 'token', 'dram', 'pbus', 'length'},
    'pi_request_end': {'request', 'direction', 'token', 'dram', 'pbus', 'length'},
    'dispatch_begin': {'event', 'token', 'request'},
    'dispatch_end': {'event', 'token', 'request'},
    'pi_copy_request': {'transfer', 'request', 'token'},
    'pi_status_scope': {'dispatch', 'event', 'token', 'request'},
}


def inspect(rows, projection):
    header = next(rows)
    assert set(header) == {'record', 'format', 'revision', 'rom_sha256', 'budget',
                           'mapped_cartridge_size', 'firmware_sha256', 'policy',
                           'lifecycle_policy', 'paired_fetch_format'}
    assert header['record'] == 'header' and header['format'] == FORMAT and header['policy'] == POLICY
    assert header['lifecycle_policy'] == 'single_run_no_host_restore'
    projected_header = dict(header, format='plaid-ares-access-history-v1',
                            policy='identity_ram_fetch_and_buffered_pi_contexts')
    def emit(row):
        projection.write((json.dumps(row, separators=(',', ':')) + '\n').encode())
    emit(projected_header)
    raw_ordinal = ordinal = raw_active = active = raw_pending = pending = 0
    slots = [0] * 512
    tokens = {}
    requests = {}
    next_token = next_request = current = 0
    removal = dispatch = copy_join = status_join = None
    statuses = []
    unknown_statuses = 0
    counts = Counter()
    ended = copying = False
    for e in rows:
        assert not ended
        kind = e['record']
        if kind == 'end':
            assert e['record_count'] == raw_ordinal
            assert not current and removal is dispatch is copy_join is status_join is None
            assert raw_active == raw_pending == 0
            assert not copying
            emit(dict(e, record_count=ordinal))
            ended = True
            continue
        raw_ordinal += 1
        assert raw_ordinal <= 100000000
        assert type(e['ordinal']) is int and e['ordinal'] == raw_ordinal
        assert type(e['pc']) is int and 0 <= e['pc'] < 1 << 64
        assert type(e['context']) is int
        counts[kind] += 1
        if removal is not None:
            assert kind == 'dispatch_begin' or (kind == 'queue' and e['kind'] in (6, 7)), 'stale valid removal'
        if copy_join is not None:
            assert kind == 'pi_dma' and e['event'] == 1, 'orphan copy binding'
        if status_join is not None:
            assert kind == 'pi_dma' and e['event'] == 8, 'orphan status scope'
        if kind in EXTRA:
            assert not copying, 'new event inside buffered copy'
            assert set(e) == COMMON | EXTRA[kind]
            assert e['context'] == raw_active == raw_pending == 0, 'new event inside fetch boundary'
            bools = {'valid'} if kind == 'queue' else {'dispatch'} if kind == 'pi_status_scope' else set()
            assert all(type(e[k]) is bool for k in bools)
            assert all(type(e[k]) is int and 0 <= e[k] < 1 << 64 for k in EXTRA[kind] - bools)
            if kind == 'pi_request_begin':
                next_request += 1
                assert next_request <= 1000000
                assert not current and dispatch is None and e['request'] == next_request and e['token'] == 0
                assert e['direction'] in (0, 1) and 0 < e['length'] <= 0x1000000
                assert e['dram'] < 0x1000000 and e['pbus'] < 1 << 32
                current = next_request
                requests[current] = dict(direction=e['direction'], dram=e['dram'], pbus=e['pbus'],
                                         length=e['length'], token=0, outcome=None, returned=False, transfer=None, pc=e['pc'])
            elif kind == 'pi_request_end':
                assert current == e['request'] and current > 0
                req = requests[current]
                assert all(e[k] == req[k] for k in ('direction', 'dram', 'pbus', 'length', 'token'))
                assert e['pc'] == req['pc']
                assert req['outcome'] is not None
                assert req['direction'] == 0 or req['transfer'] is not None
                req['returned'] = True
                current = 0
            elif kind == 'queue':
                q = e['kind']
                assert 1 <= q <= 9 and e['clock'] < 1 << 32 and e['event'] < 1 << 32
                assert q != 9 or not e['valid'], 'host restore violates declared boot lifecycle'
                assert e['active_request'] == current
                token = 0
                if q == 1 or (q == 9 and e['valid']):
                    slots = [0] * 512
                    tokens.clear()
                    removal = None
                elif q == 9:
                    pass  # save-only preserves live identities
                elif q in (3, 6, 7):
                    assert e['slot'] < 512 and e['other'] < 512
                    token = slots[e['slot']] = slots[e['other']]
                    if token:
                        t = tokens[token]
                        assert (e['event'], e['clock'], e['valid']) == (t['event'], t['clock'], t['valid'])
                elif q == 4:
                    assert e['slot'] < 512 and e['valid']
                    next_token += 1
                    assert next_token <= 1000000
                    token = next_token
                    req = current if current and requests[current]['direction'] == e['event'] else 0
                    tokens[token] = dict(event=e['event'], clock=e['clock'], valid=True, request=req, removed=False)
                    slots[e['slot']] = token
                elif q in (5, 8):
                    assert e['slot'] < 512
                    token = slots[e['slot']]
                    if token:
                        t = tokens[token]
                        assert (e['event'], e['clock'], e['valid']) == (t['event'], t['clock'], t['valid'])
                        assert not t['removed'], 'reused removed queue identity'
                        if q == 8:
                            t['valid'] = False
                        else:
                            t['removed'] = True
                    if q == 5:
                        assert e['slot'] == 0 and e['other'] < 512
                        removal = (token, e['event'], e['pc']) if e['valid'] else None
                else:
                    assert q == 2 and e['slot'] == 512 and not e['valid']
                assert e['token'] == token
                assert e['request'] == (tokens[token]['request'] if token else 0)
                if q in (2, 4) and current and requests[current]['direction'] == e['event']:
                    req = requests[current]
                    assert e['pc'] == req['pc']
                    assert req['outcome'] is None
                    req['outcome'] = q == 4
                    req['token'] = token
            elif kind == 'dispatch_begin':
                assert not current and dispatch is None and removal == (e['token'], e['event'], e['pc'])
                req = tokens[e['token']]['request'] if e['token'] else 0
                assert e['request'] == req
                if req:
                    assert requests[req]['returned'] and requests[req]['direction'] == e['event']
                dispatch = dict(event=e['event'], token=e['token'], request=req, statuses=0, pc=e['pc'])
                removal = None
            elif kind == 'dispatch_end':
                assert dispatch is not None
                assert all(e[k] == dispatch[k] for k in ('event', 'token', 'request'))
                assert e['pc'] == dispatch['pc']
                assert dispatch['statuses'] == (1 if e['event'] in (0, 1) else 0)
                dispatch = None
            elif kind == 'pi_copy_request':
                assert current > 0 and e['request'] == current
                req = requests[current]
                assert req['direction'] == 1 and req['outcome'] is not None and req['transfer'] is None
                assert e['pc'] == req['pc'] and e['transfer'] > 0
                assert e['token'] == req['token']
                req['transfer'] = e['transfer']
                copy_join = e
            else:
                assert kind == 'pi_status_scope'
                assert e['dispatch'] == (dispatch is not None)
                if dispatch is None:
                    assert e['event'] == e['token'] == e['request'] == 0
                else:
                    assert dispatch['event'] in (0, 1)
                    assert all(e[k] == dispatch[k] for k in ('event', 'token', 'request'))
                    assert e['pc'] == dispatch['pc']
                    assert dispatch['statuses'] == 0
                    dispatch['statuses'] += 1
                status_join = e
            continue
        # Delegated v1 validation checks all legacy field shapes and buffered effects.
        if kind == 'pi_dma' and e['event'] == 1:
            assert copy_join is not None and e['transfer'] == copy_join['transfer']
            assert e['dram'] == requests[current]['dram'] and e['pbus'] == requests[current]['pbus']
            assert e['length'] == requests[current]['length'] and not copying
            assert e['pc'] == requests[current]['pc']
            copying = True
            copy_join = None
        if kind == 'pi_dma' and e['event'] == 7:
            assert copying
            copying = False
        if kind == 'pi_dma' and e['event'] == 8:
            assert status_join is not None
            assert e['pc'] == status_join['pc']
            if status_join['request']:
                statuses.append({k: status_join[k] for k in ('event', 'token', 'request')})
            else:
                unknown_statuses += 1
            status_join = None
        ordinal += 1
        row = dict(e, ordinal=ordinal)
        if kind == 'fetch_begin':
            assert raw_active == raw_pending == 0 and e['context'] == raw_ordinal
            raw_active, active = raw_ordinal, ordinal
        assert e['context'] == raw_active
        row['context'] = active
        if kind == 'fetch_end':
            raw_pending, pending = raw_active, active
            raw_active = active = 0
        if kind == 'fetch':
            assert e['fetch_context'] == raw_pending and raw_pending > 0
            row['fetch_context'] = pending
            raw_pending = pending = 0
        emit(row)
    assert ended
    return dict(records=raw_ordinal, v1_records=ordinal, counts=dict(counts), requests=next_request,
                successful_insertions=next_token,
                rejected_requests=sum(r['outcome'] is False for r in requests.values()),
                request_status_links=statuses, unknown_statuses=unknown_statuses,
                requests_without_status=[n for n in requests
                                         if not any(s['request'] == n for s in statuses)],
                native_complete=False, guest_completion_claimed=False)
