"""Deterministic bounded repair policy; all capture bytes are synthetic."""
import contextlib
import io
import json
import os
from pathlib import Path
from subprocess import CompletedProcess
import shutil
import subprocess
import tempfile
from unittest.mock import patch

import native
from repair_record import admit_records, native_manifest, write_record


def run_contract():
    with tempfile.TemporaryDirectory(prefix='plaid-repair-loop-') as temporary:
        root = Path(temporary)
        loads = root / 'loads.json'
        original = json.dumps(dict(loads=[]))
        calls = []

        def exercise(faults, payloads, cap=native.REPAIR_ROUND_CAP, initial=()):
            calls.clear()
            records = []

            def build(admitted):
                number = len(calls)
                calls.append(list(admitted))
                loads.write_text(original)
                admit_records(loads, admitted)
                images = json.loads(loads.read_text())['observed_images']
                assert [i['generation'] for i in images] == list(range(1, len(admitted) + 1))
                # Exercise the real manifest writer, including a scoped CLOSED map.
                spec = dict(observed={str(i['generation']): i['record'] for i in images},
                            loads=[dict(encoding=dict(observed=dict(generation=i['generation'])),
                                        destination=dict(start=0x80800000 + i['generation'] * 0x100)) for i in images])
                manifest = native_manifest(dict(load_images={'synthetic': spec}), dict(), False)
                assert manifest['native_complete'] == (not admitted)
                assert len(manifest['observed_images']) == len(admitted)
                fault = faults[number]
                record = None
                if fault in (3, 15) and payloads[number] is not None:
                    raw = root / 'raw.json'
                    raw.write_text(json.dumps(dict(format='plaid-repair-raw-v0', fault=fault,
                                   site='80000400', target='80000400', vi=number,
                                   physical_start=0x400, bytes=payloads[number])))
                    record = write_record(raw, root / 'repair')
                    records.append(record)
                stdout = json.dumps(dict(stop='fault' if fault else 'seconds', fault=fault,
                                         fault_pc='80000400'), separators=(',', ':'))
                return CompletedProcess([], int(bool(fault)), stdout, ''), record

            output = io.StringIO()
            failure = None
            with contextlib.redirect_stdout(output):
                try:
                    native.repair_loop(build, initial, cap)
                except SystemExit as error:
                    failure = str(error)
            lines = output.getvalue().splitlines()
            assert len(lines) == len(calls)
            assert all(line.startswith(f'repair round {n}: fault=') and 'pc=80000400' in line
                       for n, line in enumerate(lines, 1))
            return failure, lines, records

        # One captured stop, then a second build succeeds using that image.
        error, lines, records = exercise([3, 0], ['24020007', None])
        assert error is None and len(calls) == 2 and calls[1] == [records[0]]
        assert 'sha256=' in lines[0] and lines[-1].endswith('stop=success')
        # Multiple distinct generations stay in capture order.
        error, _, records = exercise([3, 15, 0], ['24020007', '24020008', None])
        assert error is None and calls[2] == records
        # VI/site/stop metadata may change while the payload stays unchanged.
        error, lines, _ = exercise([3, 15, 0], ['24020007', '24020007', None])
        assert 'repeated-hash' in error and len(calls) == 2 and 'repeated-hash' in lines[-1]
        error, _, _ = exercise([3, 3, 3, 3, 0], ['24020001', '24020002', '24020003', '24020004', None])
        assert 'round-cap' in error and len(calls) == native.REPAIR_ROUND_CAP
        for fault in (4, 11, 17):
            error, _, _ = exercise([fault, 0], [None, None])
            assert 'non-repairable-stop' in error and len(calls) == 1
        error, _, _ = exercise([3, 0], [None, None])
        assert 'capture-unavailable' in error and len(calls) == 1
        error, _, records = exercise([3], ['24020007'], cap=1)
        assert 'round-cap' in error and len(calls) == 1
        error, _, _ = exercise([3, 0], ['24020007', None], initial=records)
        assert 'repeated-hash' in error and len(calls) == 1
        # The public CLI carries forward refined baseline loads and explicit
        # records without silently selecting --deep, and honors --deep itself.
        for deep in (False, True):
            seen = []
            def build_once(args):
                seen.append((args.loads, list(args.repair_record), os.environ.get('PLAID_SITE_BUDGET')))
                fault = 3 if len(seen) == 1 else 0
                result = CompletedProcess([], int(bool(fault)), json.dumps(dict(
                    stop='synthetic', fault=fault, fault_pc='80000400'), separators=(',', ':')), '')
                return result, records[0] if fault else None, loads
            with patch.object(native, 'build_once', side_effect=build_once), \
                    patch('sys.argv', ['native.py', 'synthetic.z64', *(['--deep'] if deep else [])]), \
                    patch.dict(os.environ, {'PLAID_SITE_BUDGET': str(native.FAST_SITE_BUDGET)}), \
                    patch('sys.stdout', io.StringIO()):
                native.main()
            budget = None if deep else str(native.FAST_SITE_BUDGET)
            assert seen == [(None, [], budget), (loads, records, budget)], seen
        # A process exit without a valid stop cannot be mistaken for success.
        for stdout, rc in [('', 0), ('{"stop":', 0), ('{"stop":"seconds","fault":false,"fault_pc":"00000000"}', 0),
                           ('{"stop":"seconds","fault":0,"fault_pc":"00000000"}', 1)]:
            with patch('sys.stdout', io.StringIO()):
                try:
                    native.repair_loop(lambda _: (CompletedProcess([], rc, stdout, ''), None), [])
                except SystemExit:
                    pass
                else:
                    raise AssertionError('invalid validation accepted')
    print('PASS bounded repair: convergence, generations, hash repetition, cap, non-repairable stops and invalid runs')


def native_execution_contract(exe, root):
    """Actual discover/lower/compile/capture/admit/rebuild, without an oracle or ROM assets."""
    out = root / 'native-repair'
    out.mkdir()
    source, loads, mapping, c = (out / name for name in ('test.z64', 'loads.json', 'map.json', 'game.c'))
    rom = bytearray(4096)
    rom[:4] = bytes.fromhex('80371240')
    rom[64:76] = bytes.fromhex('8c9900000320000800000000')
    rom[96:100] = bytes.fromhex('0000000c')
    source.write_bytes(rom)
    sequence = []

    def build(records):
        loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='synthetic', loads=[])))
        admit_records(loads, records)
        def plaid(*args):
            result = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True)
            assert result.returncode == 0, (args, result.stdout, result.stderr)
            return result.stdout
        plaid('discover', source, '64', '0x80000000', '64', '0x80000000', mapping,
              *(['--loads', loads] if records else []))
        verdict = json.loads(plaid('solve', source, mapping, '--residual-dispatch'))
        assert verdict['status'] == 'closed' or (verdict.get('trapped_sites') and
               all(b in verdict['trapped_sites'] for b in verdict['blockers'])), verdict
        manifest = native_manifest(json.loads(mapping.read_text()), verdict, True)
        assert not manifest['native_complete'] and len(manifest['observed_images']) == len(records)
        plaid('lower-map', source, mapping, '0x80000000', '0x80000f00', c, '--residual-dispatch')
        harness, binary, raw = (out / name for name in ('harness.c', 'test.exe', 'raw.json'))
        harness.write_text('''#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "game.c"
#include "runtime.c"
#include "repair_capture.h"
static plaid_state s;
static unsigned char before[sizeof s.ram];
int main(int argc, char **argv) {
  assert(argc==2); plaid_load_images(&s);
  const unsigned char payload[]={0x24,2,0,7,3,0xe0,0,8,0,0,0,0};
  memcpy(s.ram+32,payload,sizeof payload);
  s.r[4]=SX32(0x80004000u); s.r[31]=SX32(0x80000f00u);
  s.ram[0x4000]=0x80; s.ram[0x4003]=0x20;
  memcpy(before,s.ram,sizeof before);
  int r=plaid_run(&s);
  assert(!plaid_safepoints && !s.native_frames && !s.hi && !s.lo && !s.cp0_known);
  assert(!memcmp(before,s.ram,sizeof before));
  assert((s.fault==3 && r && !s.r[2]) || (!s.fault && !r && s.r[2]==7 && s.pc==0x80000f00u));
  for(int i=0;i<32;i++) assert(s.r[i]==(i==2 ? (s.fault ? 0 : 7) :
    i==4 ? SX32(0x80004000u) : i==25 ? SX32(0x80000020u) : i==31 ? SX32(0x80000f00u) : 0));
  int captured=plaid_repair_capture(argv[1],s.ram,sizeof s.ram,s.fault,s.fault_pc,s.fault_target,0);
  assert(captured==(s.fault==3));
  printf("{\\"stop\\":\\"synthetic\\",\\"fault\\":%u,\\"fault_pc\\":\\"%08x\\"}\\n",s.fault,s.fault_pc);
  return s.fault ? 1 : 0;
}
''')
        cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
        subprocess.run([cc, '-O0', '-std=c11', '-I', str(native.ROOT / 'spikes/096-native-slice'),
                        '-I', str(native.ROOT / 'runtime'), str(harness), '-lm', '-o', str(binary)], check=True)
        raw.unlink(missing_ok=True)
        result = subprocess.run([str(binary), str(raw)], capture_output=True, text=True, timeout=30,
                                env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
        sequence.append(native.validation_stop(result)['fault'])
        return result, write_record(raw, out / 'repair') if raw.exists() else None

    native.repair_loop(build, [])
    assert sequence == [3, 0], sequence
    print('PASS native synthetic repair: fault 3 -> captured/admitted host-native rebuild -> fault 0, GPR/PC/RAM unchanged except v0')


if __name__ == '__main__':
    run_contract()
