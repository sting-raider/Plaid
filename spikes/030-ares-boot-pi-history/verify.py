"""Strict finite PI source/effect inspection and complete v0 projection."""
from collections import Counter
import hashlib
import json
import struct


FORMAT = "plaid-ares-access-history-v1"
POLICY = "identity_ram_fetch_and_buffered_pi_contexts"
COMMON = {"record", "ordinal", "context", "pc"}
PI_FIELDS = {"event", "transfer", "block", "dram", "pbus", "length", "lane", "value"}
ROM_FIELDS = {"transfer", "block", "offset", "value"}
BASE_FIELDS = {
    "scalar": {"write", "address", "aligned_address", "bytes", "device", "value"},
    "burst": {"write", "address", "bytes", "device", "words"},
    "fill": {"slot", "physical", "index", "words"},
    "cache_operation": {"operation", "vaddr", "physical", "before_tag", "after_tag", "before_words", "after_words"},
    "fetch_begin": {"vaddr", "translated", "bus", "cached", "value"},
    "fetch_end": {"vaddr", "translated", "bus", "cached", "value"},
    "fetch": {"fetch_context", "fetch_seq", "word", "physical", "cached"},
}


def inspect(rows, source, projection):
    header = next(rows)
    assert set(header) == {"record", "format", "policy", "revision", "rom_sha256", "budget",
                           "mapped_cartridge_size", "firmware_sha256", "lifecycle_policy", "paired_fetch_format"}
    assert header["record"] == "header" and header["format"] == FORMAT and header["policy"] == POLICY
    assert header["revision"] == "9408cb43d4948fc3ea6e152a307a34348df3fe04"
    assert header["lifecycle_policy"] == "single_run_no_host_restore"
    assert header["paired_fetch_format"] == "plaid-ares-fetch-research-v5"
    assert type(header["budget"]) is int and 0 < header["budget"] <= 1000000
    assert type(header["firmware_sha256"]) is str and len(header["firmware_sha256"]) == 64
    assert all(c in "0123456789abcdef" for c in header["firmware_sha256"])
    assert hashlib.sha256(source).hexdigest() == header["rom_sha256"]
    assert header["mapped_cartridge_size"] == len(source) & ~7
    projected_header = dict(header, format="plaid-ares-access-history-v0",
                            policy="identity_ram_successful_access_and_fetch_boundaries")

    def emit(row):
        projection.write((json.dumps(row, separators=(",", ":"))+"\n").encode())

    emit(projected_header)
    ordinal = projected_ordinal = active = projected_active = projected_pending = raw_pending = 0
    transfer = block = attempt = committed = None
    buffer = {}
    block_count = last_transfer = 0
    returned, status_contexts = set(), []
    counts = Counter()
    attempts = writes = known = failed = source_reads = unassociated_completion = 0
    origins = hashlib.sha256()
    previous = None
    ended = False
    for e in rows:
        assert not ended
        kind = e["record"]
        if kind == "end":
            assert set(e) == {"record", "record_count", "fetch_count", "reason"}
            assert type(e["record_count"]) is int and type(e["fetch_count"]) is int
            assert e["fetch_count"] == counts["fetch"] <= header["budget"] and e["reason"] == "instruction_call_budget"
            assert e["record_count"] == ordinal and active == 0
            assert transfer is block is attempt is None and projected_pending == raw_pending == 0
            emit(dict(e, record_count=projected_ordinal))
            ended = True
            continue
        ordinal += 1
        assert type(e["ordinal"]) is int and e["ordinal"] == ordinal
        assert type(e["pc"]) is int and 0 <= e["pc"] < 1 << 64
        assert type(e["context"]) is int
        counts[kind] += 1
        if raw_pending:
            assert kind == "fetch", "prologue must immediately follow access return"
        if previous is not None and previous["record"] == "pi_rom_half":
            assert kind == "pi_dma" and e["event"] == 3, "orphan delegated ROM result"
        if attempt is not None:
            assert (kind == "pi_dma" and e["event"] == 5) or (kind == "scalar" and "pi" in e)
        if kind == "fetch_begin":
            assert active == raw_pending == 0 and e["context"] == ordinal
            active, projected_active = ordinal, projected_ordinal+1
        else:
            assert e["context"] == active
        if kind in ("pi_dma", "pi_rom_half"):
            assert set(e) == COMMON | (PI_FIELDS if kind == "pi_dma" else ROM_FIELDS)
            for key in (PI_FIELDS if kind == "pi_dma" else ROM_FIELDS):
                assert type(e[key]) is int and 0 <= e[key] <= (1 << (64 if key == "transfer" else 32))-1
            if kind == "pi_rom_half":
                assert transfer == e["transfer"] and block == e["block"] and attempt is None
                offset = e["offset"]
                assert offset % 2 == 0 and offset+2 <= header["mapped_cartridge_size"]
                assert e["value"] == int.from_bytes(source[offset:offset+2], "big")
                source_reads += 1
            else:
                event = e["event"]
                assert 1 <= event <= 8
                if event == 1:
                    assert transfer is block is attempt is None and e["block"] == 0
                    last_transfer += 1
                    assert e["transfer"] == last_transfer
                    transfer, block_count = last_transfer, 0
                elif event == 8:
                    assert transfer is block is attempt is None and e["lane"] == 0 and e["value"] == 1
                    if e["transfer"] == 0:
                        unassociated_completion += 1
                    else:
                        assert e["transfer"] in returned
                        status_contexts.append(e["transfer"])
                else:
                    assert e["transfer"] == transfer
                if event == 2:
                    assert block is None and attempt is None
                    block_count += 1
                    assert e["block"] == block_count and 0 < e["length"] <= 128 and e["lane"] <= 7
                    block, buffer = block_count, {}
                elif event in (3, 4, 5, 6):
                    assert block is not None and e["block"] == block
                    if event == 3:
                        assert e["lane"] % 2 == 0 and e["lane"] < e["length"] and e["value"] <= 65535
                        assert e["lane"] not in buffer
                        witnessed = previous is not None and previous["record"] == "pi_rom_half" \
                            and previous["transfer"] == transfer and previous["block"] == block \
                            and previous["offset"]+0x10000000 == e["pbus"] and previous["value"] == e["value"]
                        for index in range(2):
                            buffer[e["lane"]+index] = ((e["value"] >> (8*(1-index))) & 255,
                                                       previous["offset"]+index if witnessed else None)
                    elif event == 4:
                        assert attempt is None and e["lane"] in buffer and e["value"] == buffer[e["lane"]][0]
                        attempt, committed = e, None
                        attempts += 1
                    elif event == 5:
                        assert attempt is not None
                        assert all(e[key] == attempt[key] for key in ("dram", "pbus", "length", "lane", "value"))
                        if committed is not None:
                            value, offset = buffer[e["lane"]]
                            writes += 1
                            known += int(offset is not None)
                            origins.update(struct.pack(">IIIQ", e["dram"], 0xffffffff if offset is None else offset,
                                                       value, committed["ordinal"]))
                        else:
                            failed += 1
                        attempt = committed = None
                    else:
                        assert attempt is None
                        block = None
                elif event == 7:
                    assert block is None and attempt is None and transfer not in returned
                    returned.add(transfer)
                    transfer = None
            previous = e
            continue
        assert kind in BASE_FIELDS
        extra = {"pi"} if kind == "scalar" and e["write"] and e["device"] == 5 else set()
        assert set(e) == COMMON | BASE_FIELDS[kind] | extra
        projected = dict(e)
        if kind == "scalar" and e["write"] and e["device"] == 5:
            assert set(e["pi"]) == {"transfer", "block", "lane"}
            assert all(type(e["pi"][key]) is int and e["pi"][key] >= 0 for key in e["pi"])
            assert attempt is not None and committed is None and e["bytes"] == 1
            assert e["pi"] == {"transfer": transfer, "block": block, "lane": attempt["lane"]}
            assert (e["address"], e["value"]) == (attempt["dram"], attempt["value"])
            assert e["aligned_address"] == e["address"] and e["address"] < 8388608
            committed = e
            del projected["pi"]
        else:
            assert "pi" not in e
        projected_ordinal += 1
        projected["ordinal"] = projected_ordinal
        projected["context"] = projected_active if active else 0
        if kind == "fetch_end":
            raw_pending = active
            active = 0
            projected_pending = projected_active
            projected_active = 0
        elif kind == "fetch":
            assert projected_pending and e["fetch_context"] == raw_pending
            projected["fetch_context"] = projected_pending
            projected_pending = raw_pending = 0
        emit(projected)
        previous = e
    assert ended
    return dict(records=ordinal, projected_records=projected_ordinal, event_counts=dict(sorted(counts.items())),
                source_half_reads=source_reads, byte_attempts=attempts, successful_pi_writes=writes,
                canonical_rom_byte_origins=known, unknown_pi_byte_origins=writes-known,
                failed_destination_witnesses=failed, returned_transfers=len(returned),
                completion_status_transitions=len(status_contexts)+unassociated_completion,
                observer_write_contexts_at_status=status_contexts,
                writes_without_observer_status=sorted(returned-set(status_contexts)),
                transfer_completion_certified=False, unassociated_completions=unassociated_completion,
                pi_origin_effects_sha256=origins.hexdigest())
