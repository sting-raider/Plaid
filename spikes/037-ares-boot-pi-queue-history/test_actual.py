"""Reject identity forgeries in an actual retained boot stream, without buffering."""
from pathlib import Path
import argparse
import importlib.util
from verify import inspect

ROOT = Path(__file__).resolve().parents[2]

class Discard:
    def write(self, payload):
        return len(payload)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', type=Path, default=ROOT / 'target/ares-boot-pi-queue-history-spike/queue/610000/traced.ndjson.history.ndjson')
    parser.add_argument('--positive', action='store_true', help='also recheck every scheduling record in the complete stream')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('actual_boot_rows', ROOT / 'spikes/027-ares-boot-history/run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if args.positive:
        result = inspect(module.records(args.history), Discard())
        print('PASS complete scheduling replay: ' + str(result['records']) + ' records; '
              + str(len(result['request_status_links'])) + ' identified statuses', flush=True)
    for kind in ('queue', 'pi_request_begin', 'pi_copy_request', 'pi_status_scope'):
        changed = False
        def forged():
            nonlocal changed
            for e in module.records(args.history):
                eligible = e['record'] == kind and (kind != 'queue' or e['kind'] == 4)
                if eligible and not changed:
                    e['request' if kind == 'pi_request_begin' else 'token'] += 1
                    changed = True
                yield e
        try:
            inspect(forged(), Discard())
        except AssertionError:
            assert changed, 'original stream failed before mutation'
        else:
            raise AssertionError('forged actual identity accepted: ' + kind)
        print('PASS actual identity forgery rejected: ' + kind, flush=True)
    print('PASS: four actual scheduling forgeries; complete-source positive check remains separate')

if __name__ == '__main__': main()
