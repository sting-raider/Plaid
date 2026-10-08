"""Adversarial protocol cases; synthetic records are not CPU execution evidence."""
import copy
import hashlib
import io
import json
from verify import inspect, FORMAT, POLICY


def fixture():
    source = bytearray(16384)
    source[:4] = bytes.fromhex("80371240")
    source[0x1000:0x1004] = source[0x2000:0x2004] = bytes.fromhex("34081111")
    events = []
    def row(kind, **payload):
        events.append(dict(record=kind, ordinal=len(events)+1, context=0, pc=0xffffffff80000000, **payload))
    def pi(event, transfer, block, dram, pbus, length, lane=0, value=0):
        row("pi_dma", event=event, transfer=transfer, block=block, dram=dram, pbus=pbus,
            length=length, lane=lane, value=value)
    for transfer, destination, values, witnessed in ((1, 0x4000, bytes.fromhex("34081111"), True),
                                                   (2, 8388608, bytes.fromhex("3408"), True),
                                                   (3, 0x4004, bytes.fromhex("0007"), False)):
        pbus = 0x10001000 if witnessed else 0x1ff00000
        pi(1, transfer, 0, destination, pbus, len(values))
        pi(2, transfer, 1, destination, pbus, len(values), value=1)
        for lane in range(0, len(values), 2):
            value = int.from_bytes(values[lane:lane+2], "big")
            if witnessed:
                row("pi_rom_half", transfer=transfer, block=1, offset=0x1000+lane, value=value)
            pi(3, transfer, 1, destination, pbus+lane, len(values), lane, value)
        for lane, value in enumerate(values):
            pi(4, transfer, 1, destination+lane, pbus+len(values), len(values), lane, value)
            if destination < 8388608:
                row("scalar", write=True, address=destination+lane, aligned_address=destination+lane,
                    bytes=1, device=5, value=value, pi=dict(transfer=transfer, block=1, lane=lane))
            pi(5, transfer, 1, destination+lane, pbus+len(values), len(values), lane, value)
        pi(6, transfer, 1, destination+len(values), pbus+len(values), len(values), value=1)
        pi(7, transfer, 1, destination+len(values), pbus+len(values), 127)
        if transfer != 3:
            pi(8, transfer, 1, destination+len(values), pbus+len(values), 127, value=1)
    header = dict(record="header", format=FORMAT, policy=POLICY, revision="9408cb43d4948fc3ea6e152a307a34348df3fe04",
                  rom_sha256=hashlib.sha256(source).hexdigest(), budget=1, mapped_cartridge_size=len(source),
                  firmware_sha256="0"*64, lifecycle_policy="single_run_no_host_restore",
                  paired_fetch_format="plaid-ares-fetch-research-v5")
    return source, [header, *events, dict(record="end", record_count=len(events), fetch_count=0,
                                        reason="instruction_call_budget")]


def main():
    source, rows = fixture()
    output = io.BytesIO()
    report = inspect(iter(rows), source, output)
    assert (report["successful_pi_writes"], report["canonical_rom_byte_origins"],
            report["unknown_pi_byte_origins"], report["failed_destination_witnesses"]) == (6, 4, 2, 2)
    assert report["returned_transfers"] == 3 and report["completion_status_transitions"] == 2
    assert report["writes_without_observer_status"] == [3]
    assert report["observer_write_contexts_at_status"] == [1, 2] and not report["transfer_completion_certified"]
    projected = [json.loads(raw) for raw in output.getvalue().splitlines()]
    assert projected[0]["format"] == "plaid-ares-access-history-v0"
    assert [e["ordinal"] for e in projected[1:-1]] == list(range(1, 7))
    assert all("pi" not in row for row in projected)
    altered = copy.deepcopy(rows)
    next(e for e in altered if e["record"] == "pi_rom_half")["offset"] += 0x1000
    assert inspect(iter(altered), source, io.BytesIO())["canonical_rom_byte_origins"] == 2
    variants = []
    for kind, field, value in (("pi_rom_half", "value", 0), ("pi_dma", "transfer", 4),
                                ("scalar", "value", 0), ("scalar", "bytes", 2),
                                ("scalar", "address", 0x5000), ("scalar", "pi", dict(transfer=2, block=1, lane=0))):
        changed = copy.deepcopy(rows)
        next(e for e in changed if e["record"] == kind)[field] = value
        variants.append(changed)
    changed = copy.deepcopy(rows); changed[2]["ordinal"] = 1; variants.append(changed)
    changed = copy.deepcopy(rows); changed[-1]["record_count"] -= 1; variants.append(changed)
    variants.append(copy.deepcopy(rows[:-1]))
    changed = copy.deepcopy(rows)
    next(e for e in changed if e["record"] == "pi_dma" and e["event"] == 5)["event"] = 7
    variants.append(changed)
    changed = copy.deepcopy(rows); changed[1]["unexpected"] = 1; variants.append(changed)
    with_fetch = copy.deepcopy(rows[:-1])
    begin = len(with_fetch)
    pc = 0xffffffffa0004000
    for payload in (
        dict(record="fetch_begin", context=begin, pc=pc, vaddr=pc, translated=0x4000, bus=0x4000, cached=False, value=0),
        dict(record="scalar", context=begin, pc=pc, write=False, address=0x4000, aligned_address=0x4000, bytes=4, device=3, value=0x34081111),
        dict(record="fetch_end", context=begin, pc=pc, vaddr=pc, translated=0x4000, bus=0x4000, cached=False, value=0x34081111),
        dict(record="fetch", context=0, pc=pc, fetch_context=begin, fetch_seq=0, word=0x34081111, physical=0x4000, cached=False),
    ):
        payload["ordinal"] = len(with_fetch)
        with_fetch.append(payload)
    with_fetch.append(dict(record="end", record_count=len(with_fetch)-1, fetch_count=1, reason="instruction_call_budget"))
    projected_fetch = io.BytesIO()
    inspect(iter(with_fetch), source, projected_fetch)
    parsed = [json.loads(raw) for raw in projected_fetch.getvalue().splitlines()]
    assert parsed[-2]["fetch_context"] == parsed[-5]["ordinal"] == 7
    for field, value in (("fetch_context", begin+1), ("context", begin), ("ordinal", 1)):
        changed = copy.deepcopy(with_fetch); changed[-2][field] = value; variants.append(changed)
    changed = copy.deepcopy(rows); changed[0]["budget"] = True; variants.append(changed)
    changed = copy.deepcopy(rows); changed[0]["lifecycle_policy"] = "restore_untracked"; variants.append(changed)
    changed = copy.deepcopy(rows)
    next(e for e in changed if e["record"] == "scalar")["pi"]["transfer"] = True
    variants.append(changed)
    for changed in variants:
        try:
            inspect(iter(changed), source, io.BytesIO())
        except AssertionError:
            continue
        raise AssertionError("forged PI source/effect/context accepted")
    print("PASS: pending completion and v0 projection retain exact finite effects/context references; equal sources lose attribution; 17 forged/truncated PI protocols fail")


if __name__ == "__main__":
    main()
