from __future__ import annotations
from pathlib import Path
import hashlib, json, os, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
REF = Path(os.environ.get('PLAID_ARES_REF', ROOT / '.refs/ares'))
REV = '9408cb43d4948fc3ea6e152a307a34348df3fe04'
HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get('PLAID_EBUS_OUT', ROOT / 'target/ares-ebus-hidden-fetch-spike'))

CONTRACTS = {
    'ares/n64/mi/bus.hpp': [
        'if(unlikely(io.ebusTestMode) && device == RBusDevice::VR4300_UNCACHED)',
        'return rdram.ram.ebusRead<Size>(address);',
        'if(unlikely(io.ebusTestMode)) return ebusFreeze();',
    ],
    'ares/n64/rdram/rdram.hpp': [
        'u32 word = self.hidden.nibble(mapped & ~3);',
        'if constexpr(Size == Word) return word;',
        'self.hidden.update<Size>(address, value);',
        'self.hidden.ebusScatter<Size>(address, value);',
    ],
    'ares/n64/rdram/hidden.hpp': [
        'u8* h = &data[address >> 1];',
        'return (h[0] & 3) << 2 | (h[1] & 3);',
    ],
    'ares/n64/cpu/memory.cpp': [
        'if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);',
        'return busRead<Word>(paddr);',
    ],
}

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def guard_sources() -> dict:
    if (REF / '.git').exists():
        head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=REF, text=True).strip()
        assert head == REV, (head, REV)
        subprocess.run(['git','diff','--quiet','HEAD'], cwd=REF, check=True)
    out = {}
    for rel, needles in CONTRACTS.items():
        path = REF / rel
        text = path.read_text()
        for needle in needles:
            assert text.count(needle) >= 1, (rel, needle)
        out[rel] = sha256(path)
    return out

def build_probe() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    exe = OUT / 'probe'
    cmd = ['g++','-std=c++20','-O2','-Wall','-Wextra','-Werror',
           '-I', str(REF / 'ares/n64/rdram'), str(HERE / 'probe.cpp'), '-o', str(exe)]
    subprocess.run(cmd, check=True)
    return exe

def derived_word(raw0: int, raw1: int) -> int:
    return ((raw0 & 3) << 2) | (raw1 & 3)

def witness(fetch: dict, hidden_events: list[dict]) -> dict | None:
    if fetch.get('cache') or not fetch.get('ebus'):
        return None
    begin, end = fetch['begin'], fetch['end']
    inside = [e for e in hidden_events if begin < e['ordinal'] < end]
    if len(inside) != 1:
        return None
    e = inside[0]
    if e['request_paddr'] != fetch['bus_paddr'] or e['size'] != 4:
        return None
    if e['value'] != fetch['value']:
        return None
    if e['value'] != derived_word(e['raw0'], e['raw1']):
        return None
    return {
        'kind': 'derived_hidden_bits',
        'request_paddr': e['request_paddr'],
        'mapped_paddr': e['mapped_paddr'],
        'hidden_offsets': [e['mapped_paddr'] >> 1, (e['mapped_paddr'] >> 1) + 1],
        'bit_masks': [3, 3],
        'transform': '((raw0 & 3) << 2) | (raw1 & 3)',
        'value': e['value'],
    }

def reducer_tests() -> dict:
    f = {'begin':10,'end':20,'cache':False,'ebus':True,'bus_paddr':0x8000,'value':14}
    good = {'ordinal':15,'request_paddr':0x8000,'mapped_paddr':0x8000,'size':4,'raw0':0xff,'raw1':0xfe,'value':14}
    w = witness(f,[good]); assert w and w['kind']=='derived_hidden_bits'
    decoy = dict(good, ordinal=9, request_paddr=0x1000)
    assert witness(f,[decoy,good]) is not None
    other = dict(good, ordinal=16, request_paddr=0x9000, mapped_paddr=0x9000)
    assert witness(f,[good,other]) is None
    for changed in (dict(f, cache=True), dict(f, ebus=False), dict(f, bus_paddr=0x8004)):
        assert witness(changed,[good]) is None
    bad = dict(good, value=15); assert witness(f,[bad]) is None
    bad = dict(good, raw1=0xfd); assert witness(f,[bad]) is None
    assert witness(f,[dict(good, ordinal=21)]) is None
    return {'positive':1,'negative':7,'ambiguous_rejected':True,'copy_byte_origin_rejected':True}

def main() -> int:
    guards = guard_sources()
    exe = build_probe()
    a = subprocess.check_output([str(exe)], text=True)
    b = subprocess.check_output([str(exe)], text=True)
    assert a == b
    probe = json.loads(a)
    reducer = reducer_tests()
    result = {
        'ares_revision': REV,
        'source_sha256': guards,
        'probe_source_sha256': sha256(HERE/'probe.cpp'),
        'probe': probe,
        'reducer': reducer,
        'conclusion': {
            'word_is_byte_copy': False,
            'word_is_derived_from_two_hidden_storage_bytes': True,
            'effective_entropy_bits': 4,
            'n64_wide_invariant': False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(',',':')) + '\n'
    (OUT/'results.json').write_text(payload)
    print(payload, end='')
    print('results_sha256=' + hashlib.sha256(payload.encode()).hexdigest(), file=sys.stderr)
    return 0
if __name__ == '__main__': raise SystemExit(main())
