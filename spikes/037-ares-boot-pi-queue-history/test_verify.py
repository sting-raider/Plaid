"""Adversarial scheduling contract only; no synthetic byte-origin certificate."""
import copy
import io
from verify import inspect, FORMAT, POLICY

def sample():
    rows = [dict(record='header', format=FORMAT, policy=POLICY,
                 revision='9408cb43d4948fc3ea6e152a307a34348df3fe04', rom_sha256='0'*64,
                 budget=1, mapped_cartridge_size=8, firmware_sha256='0'*64,
                 lifecycle_policy='single_run_no_host_restore', paired_fetch_format='plaid-ares-fetch-research-v5')]
    def add(record_kind, **fields):
        rows.append(dict(record=record_kind, ordinal=len(rows), context=0, pc=0, **fields))
    def queue(kind, slot=0, other=0, event=1, valid=True, token=1, request=1, active_request=0):
        add('queue', kind=kind, slot=slot, other=other, event=event, clock=10,
            valid=valid, token=token, request=request, active_request=active_request)
    add('pi_request_begin', request=1, direction=1, token=0, dram=0x1000, pbus=0x10000000, length=8)
    queue(4, active_request=1)
    add('pi_copy_request', transfer=1, request=1, token=1)
    add('pi_dma', event=1, transfer=1, block=0, dram=0x1000, pbus=0x10000000, length=8, lane=0, value=0)
    add('pi_dma', event=7, transfer=1, block=0, dram=0x1000, pbus=0x10000000, length=8, lane=0, value=0)
    add('pi_request_end', request=1, direction=1, token=1, dram=0x1000, pbus=0x10000000, length=8)
    queue(5)
    queue(7)
    add('dispatch_begin', event=1, token=1, request=1)
    add('pi_status_scope', dispatch=True, event=1, token=1, request=1)
    add('pi_dma', event=8, transfer=1, block=0, dram=0, pbus=0, length=8, lane=0, value=1)
    add('dispatch_end', event=1, token=1, request=1)
    rows.append(dict(record='end', record_count=len(rows)-1, fetch_count=0, reason='instruction_call_budget'))
    return rows

def main():
    rows = sample()
    result = inspect(iter(rows), io.BytesIO())
    assert result['request_status_links'] == [dict(event=1, token=1, request=1)]
    assert not result['native_complete'] and not result['guest_completion_claimed']
    for kind, field, value in [
        ('dispatch_begin', 'token', 2), ('dispatch_begin', 'event', 0),
        ('pi_status_scope', 'request', 2), ('pi_status_scope', 'dispatch', False),
        ('pi_copy_request', 'token', 2), ('pi_copy_request', 'transfer', 2),
        ('pi_request_end', 'length', 9), ('pi_request_begin', 'request', True),
        ('queue', 'token', 2), ('queue', 'valid', 1),
    ]:
        forged = copy.deepcopy(rows)
        next(e for e in forged if e['record'] == kind)[field] = value
        try:
            inspect(iter(forged), io.BytesIO())
        except (AssertionError, KeyError):
            continue
        raise AssertionError((kind, field, value))
    # Raw additions cannot disappear into a projection while a copy is open.
    forged = copy.deepcopy(rows)
    begin = next(i for i, e in enumerate(forged) if e['record'] == 'pi_dma' and e['event'] == 1)
    forged.insert(begin + 1, copy.deepcopy(next(e for e in rows if e['record'] == 'queue')))
    for i, e in enumerate(forged[1:-1], 1): e['ordinal'] = i
    forged[-1]['record_count'] += 1
    try:
        inspect(iter(forged), io.BytesIO())
    except AssertionError:
        pass
    else:
        raise AssertionError('new event inside copy accepted')
    forged = copy.deepcopy(rows)
    forged.insert(-1, copy.deepcopy(next(e for e in rows if e['record'] == 'queue' and e['kind'] == 5)))
    for i, e in enumerate(forged[1:-1], 1): e['ordinal'] = i
    forged[-1]['record_count'] += 1
    try:
        inspect(iter(forged), io.BytesIO())
    except AssertionError:
        pass
    else:
        raise AssertionError('removed identity reused')
    print('PASS: synthetic scheduling join and 12 forged histories; no byte-origin/closure claim')

if __name__ == '__main__': main()
