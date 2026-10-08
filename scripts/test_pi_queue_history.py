"""V2 CLI gates and source rechecking with original synthetic PI effects."""
from pathlib import Path
import argparse
import copy
import json
import os
import shutil
import subprocess
import tempfile
from test_pi_history import ROOT, fixture as legacy_fixture


def fixture():
    source, firmware, legacy, fetches = legacy_fixture()
    rows = []
    snapshot = None
    def add(record_kind, pc, **fields):
        rows.append(dict(record=record_kind, context=0, pc=pc, **fields))
    def queue(kind, pc, token, request, active=0):
        add('queue', pc, kind=kind, slot=0, other=0, event=1, clock=10,
            valid=True, token=token, request=request, active_request=active)
    for e in legacy:
        if e['record'] == 'pi_dma' and e['event'] == 1:
            n = e['transfer']
            snapshot = dict(request=n, direction=1, token=0, dram=e['dram'], pbus=e['pbus'], length=e['length'])
            add('pi_request_begin', e['pc'], **snapshot)
            queue(4, e['pc'], n, n, n)
            add('pi_copy_request', e['pc'], transfer=n, request=n, token=n)
        if e['record'] == 'pi_dma' and e['event'] == 8:
            n = e['transfer']
            queue(5, e['pc'], n, n)
            queue(7, e['pc'], n, n)
            add('dispatch_begin', e['pc'], event=1, token=n, request=n)
            add('pi_status_scope', e['pc'], dispatch=True, event=1, token=n, request=n)
        rows.append(copy.deepcopy(e))
        if e['record'] == 'pi_dma' and e['event'] == 7:
            add('pi_request_end', e['pc'], **dict(snapshot, token=e['transfer']))
        if e['record'] == 'pi_dma' and e['event'] == 8:
            add('dispatch_end', e['pc'], event=1, token=n, request=n)
    rows[0].update(format='plaid-ares-access-history-v2', policy='identity_ram_buffered_pi_and_actual_queue_scopes')
    active = pending = 0
    for n, e in enumerate(rows[1:-1], 1):
        e['ordinal'] = n
        if e['record'] == 'fetch_begin': active = n
        e['context'] = active
        if e['record'] == 'fetch_end': pending, active = active, 0
        if e['record'] == 'fetch': e['fetch_context'], pending = pending, 0
    rows[-1]['record_count'] = len(rows)-2
    return source, firmware, rows, fetches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-build', action='store_true')
    options = parser.parse_args()
    cargo = os.environ.get('CARGO') or shutil.which('cargo') or str(Path.home()/'.cargo/bin/cargo.exe')
    if not options.no_build:
        subprocess.run([cargo, 'build', '-p', 'plaid', '--locked'], cwd=ROOT, check=True)
    exe = ROOT/('target/debug/plaid.exe' if os.name == 'nt' else 'target/debug/plaid')
    source, firmware_bytes, rows, fetches = fixture()
    with tempfile.TemporaryDirectory(prefix='pi-queue-cli-', dir=ROOT/'target') as temporary:
        directory = Path(temporary)
        firmware = directory/'firmware.bin'; firmware.write_bytes(firmware_bytes)
        trace = directory/'fetch.ndjson'; history = directory/'history.ndjson'
        def write(path, values):
            path.write_text(''.join(json.dumps(e)+'\n' for e in values), encoding='utf-8')
        write(trace, fetches); write(history, rows)
        def command(name, *args):
            return subprocess.run([str(exe), name, *map(str, args)], capture_output=True, text=True)
        reports = []
        for order in ('z64', 'v64', 'n64'):
            width = 2 if order == 'v64' else 4
            encoded = source if order == 'z64' else b''.join(source[i:i+width][::-1] for i in range(0,len(source),width))
            rom = directory/f'toy.{order}'; rom.write_bytes(encoded)
            output = directory/f'{order}-report.json'; inputs = (rom,firmware,trace,history)
            result = command('inspect-pi-queue-boot-history', *inputs, output)
            assert result.returncode == 0, result.stderr
            assert command('verify-pi-queue-boot-history', *inputs, output).returncode == 0
            report = json.loads(output.read_text(encoding='utf-8'))
            assert report['accepted_requests'] == report['successful_insertions'] == 3
            assert report['request_status_links'] == [dict(event=1,token=n,request=n) for n in (1,2)]
            assert report['requests_without_status'] == [3]
            assert report['projection']['canonical_rom_byte_origins'] == 4
            assert not report['native_complete'] and not report['guest_completion_claimed']
            reports.append(output.read_bytes())
            for source_path in inputs:
                before = source_path.read_bytes()
                assert command('inspect-pi-queue-boot-history', *inputs, source_path).returncode != 0
                assert source_path.read_bytes() == before
        assert reports[0] == reports[1] == reports[2]
        original = output.read_bytes()
        for field, value in [('native_complete', True), ('requests_without_status', []), ('unknown_statuses', 1)]:
            changed = dict(report, **{field:value}); output.write_text(json.dumps(changed), encoding='utf-8')
            assert command('verify-pi-queue-boot-history', *inputs, output).returncode != 0
        output.write_bytes(original)
        changed = copy.deepcopy(rows)
        next(e for e in changed if e['record'] == 'pi_dma' and e['event'] == 6)['dram'] += 1
        write(history,changed)
        assert command('verify-pi-queue-boot-history', *inputs, output).returncode != 0
        rejected = directory/'rejected.json'
        for values in (rows[:-1], [dict(rows[0], format='plaid-ares-access-history-v1'), *rows[1:]]):
            write(history,values)
            assert command('inspect-pi-queue-boot-history', *inputs,rejected).returncode != 0 and not rejected.exists()
        write(history,rows)
        for old in ('inspect-pi-boot-history','inspect-boot-history'):
            assert command(old,*inputs,rejected).returncode != 0 and not rejected.exists()
        changed = copy.deepcopy(rows)
        next(e for e in changed if e['record'] == 'dispatch_begin')['token'] += 1
        write(history,changed)
        assert command('inspect-pi-queue-boot-history',*inputs,rejected).returncode != 0 and not rejected.exists()
        write(history,rows)
        firmware.write_bytes(bytes([1])+firmware_bytes[1:])
        assert command('inspect-pi-queue-boot-history',*inputs,rejected).returncode != 0 and not rejected.exists()
    print('PI queue CLI: byte orders, actual status identities, complete-source/report rechecking, version/truncation gates and input protection passed')


if __name__ == '__main__':
    main()
