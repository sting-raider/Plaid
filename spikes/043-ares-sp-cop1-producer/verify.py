#!/usr/bin/env python3
from __future__ import annotations
import copy, hashlib, json, sys

FPRS = [
    0x1122334455667788,
    0x99AABBCCDDEEFF00,
    0xAABBCCDD55667788,
    0x13579BDF2468ACE0,
]
SWC1 = 0x39
SW = 0x2B

def select_u32(fr: int, ft: int) -> int:
    if fr:
        return FPRS[ft] & 0xffffffff
    pair = FPRS[ft & ~1]
    return (pair >> 32) & 0xffffffff if ft & 1 else pair & 0xffffffff

def verify(report: dict) -> dict:
    phases = {p['phase']: p for p in report['phases']}
    events = report['events']
    prev = 0
    cop1 = []
    for event in events:
        if event['ordinal'] <= prev:
            raise AssertionError('non-monotonic ordinal')
        prev = event['ordinal']
        if not event['write'] or not event['cpu']:
            raise AssertionError('unexpected non-CPU/non-write SP event')
        p = phases.get(event['phase'])
        if p is None:
            raise AssertionError('sink without phase')
        opcode = (p['instruction'] >> 26) & 0x3f
        expected_bank = 1 if (p['vaddr'] & 0x1000) else 0
        expected_offset = p['vaddr'] & 0xffc
        if event['bank'] != expected_bank or event['offset'] != expected_offset:
            raise AssertionError('bank/offset mismatch')
        if event['address'] & 0x1fff != ((expected_bank << 12) | expected_offset):
            raise AssertionError('physical SP sink mismatch')
        if opcode == SWC1:
            ft = (p['instruction'] >> 16) & 31
            if ft >= len(FPRS):
                raise AssertionError('fixture ft outside captured FPR set')
            expected = select_u32(p['fr'], ft)
            if event['value'] != expected:
                raise AssertionError('FR-sensitive payload mismatch')
            cop1.append({'generation': event['ordinal'], 'phase': event['phase'],
                         'bank': event['bank'], 'offset': event['offset'], 'value': event['value'],
                         'fr': p['fr'], 'ft': ft})
        elif opcode == SW:
            if event['value'] != p['rt9']:
                raise AssertionError('integer decoy payload mismatch')
        else:
            raise AssertionError('unexpected sink-producing opcode')
    if report['scenario'] == 'matrix':
        if len(events) != 11:
            raise AssertionError(f'expected 11 sinks, got {len(events)}')
        if len(cop1) != 10:
            raise AssertionError(f'expected 10 COP1 witnesses, got {len(cop1)}')
        a, b = [x for x in cop1 if x['phase'] in (7, 8)]
        if not (a['value'] == b['value'] and a['bank'] == b['bank'] and a['offset'] == b['offset'] and a['generation'] != b['generation']):
            raise AssertionError('same-value generation case not distinct')
        if not any(x['phase'] == 9 for x in cop1) or any(x['phase'] == 10 for x in cop1):
            raise AssertionError('integer equal-payload decoy stole COP1 identity')
    else:
        if events:
            raise AssertionError(f'fault/non-SP scenario emitted SP sink: {report["scenario"]}')
    return {'cop1_witnesses': cop1, 'event_count': len(events)}

def adversarial(report: dict) -> int:
    if report['scenario'] != 'matrix': return 0
    rejected = 0
    mutations = []
    r = copy.deepcopy(report); r['events'][0]['bank'] ^= 1; mutations.append(r)
    r = copy.deepcopy(report); r['events'][1]['value'] ^= 1; mutations.append(r)
    r = copy.deepcopy(report); r['events'][9]['phase'] = 9; mutations.append(r)
    r = copy.deepcopy(report); del r['events'][7]; mutations.append(r)
    r = copy.deepcopy(report); r['events'][6]['ordinal'], r['events'][7]['ordinal'] = r['events'][7]['ordinal'], r['events'][6]['ordinal']; mutations.append(r)
    r = copy.deepcopy(report); r['events'][10]['phase'] = 7; mutations.append(r)
    for forged in mutations:
        try: verify(forged)
        except AssertionError: rejected += 1
        else: raise AssertionError('forged history accepted')
    return rejected

def main(path: str) -> None:
    report = json.load(open(path, 'r', encoding='utf-8'))
    result = verify(report)
    rejected = adversarial(report)
    canonical = json.dumps({'result': result, 'rejected': rejected}, sort_keys=True, separators=(',', ':')).encode()
    print(f'PASS scenario={report["scenario"]} events={result["event_count"]} cop1={len(result["cop1_witnesses"])} forged_rejected={rejected}')
    print('verify_sha256=' + hashlib.sha256(canonical).hexdigest())
if __name__ == '__main__':
    main(sys.argv[1])
