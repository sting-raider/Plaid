"""Compare every finite SP fact and exact retained nested Rust report."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--budget',type=int,default=610000)
    args=parser.parse_args();directory=ROOT/'target/ares-boot-sp-history-spike'/str(args.budget)
    original=json.loads((directory/'sp-history-results.json').read_text(encoding='utf-8'))
    path=directory/'rust-sp-history-report.json';rust=json.loads(path.read_text(encoding='utf-8'))
    keys=('format','scope','records','v2_records','fetches','sp_backed_fetches','other_or_unwitnessed_fetches',
        'samples','dma_store_receipts','unconsumed_dma_read_receipts','ordered_fetch_backing_sha256','history_sha256',
        'mutation_coverage_certified','executable_lifetime_certified','native_complete')
    assert all(original[k]==rust[k] for k in keys)
    assert original['counts']==rust['event_counts']
    assert original['v2_projection_sha256']==rust['projection']['history_sha256']
    assert original['paired_fetch_sha256']==rust['projection']['projection']['projection']['fetch_sha256']
    prior=ROOT/'target/ares-boot-pi-queue-history-spike/queue'/str(args.budget)/'rust-queue-report.json'
    if prior.exists():assert rust['projection']==json.loads(prior.read_text(encoding='utf-8'))
    print('PASS all independent Python/Rust SP observations and complete source/projection digests')
    print('RUST_REPORT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest())


if __name__=='__main__':main()
