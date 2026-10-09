#!/usr/bin/env python3
"""Build exact pinned ares and verify decoded LWC1/LDC1 -> FPR -> store lineage."""
from __future__ import annotations
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT / "target/ares-cop1-load-store-lineage"

spec = importlib.util.spec_from_file_location("ares_oracle_build", ROOT / "spikes/003-ares-oracle/run.py")
buildmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(buildmod)
lspec = importlib.util.spec_from_file_location("cop1_lineage", HERE / "lineage.py")
lineage = importlib.util.module_from_spec(lspec)
sys.modules[lspec.name] = lineage
lspec.loader.exec_module(lineage)

SOURCE_PHYS = 0x4000
DEST_PHYS = 0x5000
SOURCE_DUAL = 0x1021324354657687
SOURCE_WORD = SOURCE_DUAL >> 32
EE = [0xEE] * 8


def invoke(exe: Path, mode: str, load_op: str, load_fr: int, load_ft: int,
           store_op: str, store_fr: int, store_ft: int, action: str) -> dict:
    argv = [str(exe), mode, load_op, str(load_fr), str(load_ft), store_op,
            str(store_fr), str(store_ft), action]
    return json.loads(subprocess.check_output(argv, text=True, timeout=20))


def semantic(record: dict) -> dict:
    return {k: v for k, v in record.items() if k not in {"mode", "events"}}


def repeated_case(exe: Path, *args) -> tuple[dict, dict]:
    plain = invoke(exe, "plain", *args)
    traced = invoke(exe, "traced", *args)
    again = invoke(exe, "traced", *args)
    assert traced == again, (args, traced, again)
    assert semantic(plain) == semantic(traced), (args, semantic(plain), semantic(traced))
    assert plain["events"] == [], plain
    return plain, traced


def initial_model() -> object:
    return lineage.FprLineage(lineage.initial_fprs(SOURCE_WORD))


def check_success(record: dict, load_op: str, load_fr: int, load_ft: int,
                  store_op: str, store_fr: int, store_ft: int,
                  overwrite: bool) -> dict:
    assert record["exception"] == 0 and record["coprocessor_error"] == 0, record
    assert record["source"] == lineage.be_bytes(SOURCE_DUAL, 8), record
    events = record["events"]
    assert len(events) == 2, record
    read, write = events
    load_width = 4 if load_op == "LWC1" else 8
    store_width = 4 if store_op == "SWC1" else 8
    assert read == {
        "ordinal": 1, "phase": 1, "write": False, "address": SOURCE_PHYS,
        "bytes": load_width, "device": read["device"], "uncached_cpu": True,
        "value": SOURCE_WORD if load_width == 4 else SOURCE_DUAL,
    }, read
    assert write["ordinal"] == 2 and write["phase"] == 3 and write["write"] is True, write
    assert write["address"] == DEST_PHYS and write["bytes"] == store_width and write["uncached_cpu"] is True, write

    model = initial_model()
    load_origin = f"rdram-read:e{read['ordinal']}@0x{read['address']:x}"
    model.write(load_op, load_fr, load_ft,
                lineage.be_bytes(read["value"], load_width), load_origin)
    assert record["after_load_f0"] == model.raw_u64(0), record
    assert record["after_load_f1"] == model.raw_u64(1), record

    if overwrite:
        move_op = "MTC1" if load_op == "LWC1" else "DMTC1"
        model.write(move_op, load_fr, load_ft,
                    lineage.be_bytes(read["value"], load_width), "cop1-move:equal")
        assert record["after_overwrite_f0"] == model.raw_u64(0), record
        assert record["after_overwrite_f1"] == model.raw_u64(1), record
    else:
        assert record["after_overwrite_f0"] == record["after_load_f0"]
        assert record["after_overwrite_f1"] == record["after_load_f1"]

    payload, origins = model.read(store_op, store_fr, store_ft)
    expected_value = lineage.be_value(payload)
    assert write["value"] == expected_value, (record, payload, origins)
    assert record["destination"] == payload + [0xEE] * (8 - store_width), record
    assert record["final_f0"] == model.raw_u64(0) and record["final_f1"] == model.raw_u64(1), record
    return {
        "load_op": load_op, "load_fr": load_fr, "load_ft": load_ft,
        "store_op": store_op, "store_fr": store_fr, "store_ft": store_ft,
        "overwrite": overwrite, "read_value": read["value"], "store_value": write["value"],
        "store_origins": origins,
    }


def main() -> None:
    model_count, model_digest = lineage.selftest()
    exe = buildmod.build(
        HERE / "driver.cpp", OUTPUT,
        raw_fetch_access=True, physical_fetch_access=True, rdram_scalar_access=True,
    )

    receipts = []
    false_value_matches = 0
    mixed_outputs = 0
    full_load_outputs = 0
    logical_cases = 0

    for load_op in ("LWC1", "LDC1"):
        for load_fr in (0, 1):
            for load_ft in (0, 1):
                for store_op in ("SWC1", "SDC1"):
                    for store_fr in (0, 1):
                        for store_ft in (0, 1):
                            _, traced = repeated_case(
                                exe, load_op, load_fr, load_ft,
                                store_op, store_fr, store_ft, "success",
                            )
                            receipt = check_success(
                                traced, load_op, load_fr, load_ft,
                                store_op, store_fr, store_ft, False,
                            )
                            load_mark = "rdram-read:e1@0x4000"
                            marks = [origin.startswith(load_mark) for origin in receipt["store_origins"]]
                            if receipt["read_value"] == receipt["store_value"] and not any(marks):
                                false_value_matches += 1
                            if any(marks) and not all(marks):
                                mixed_outputs += 1
                            if marks and all(marks):
                                full_load_outputs += 1
                            receipts.append(receipt)
                            logical_cases += 1

    # Same-value MTC1/DMTC1 writes are deliberately inserted between the load
    # and same-lane store. Numeric payload equality must not preserve load origin.
    overwrite_cases = 0
    for load_op, store_op in (("LWC1", "SWC1"), ("LDC1", "SDC1")):
        for fr in (0, 1):
            for ft in (0, 1):
                _, traced = repeated_case(exe, load_op, fr, ft, store_op, fr, ft, "overwrite_equal")
                receipt = check_success(traced, load_op, fr, ft, store_op, fr, ft, True)
                assert receipt["read_value"] == receipt["store_value"], receipt
                assert all(origin.startswith("cop1-move:equal") for origin in receipt["store_origins"]), receipt
                receipts.append(receipt)
                overwrite_cases += 1
                logical_cases += 1

    # Failure paths must not mint a backing-read event or alter any FPR byte.
    expected_fault = {"cu1off": (11, 1), "misalign": (4, 0), "tlbmiss": (2, 0)}
    fault_cases = 0
    for load_op in ("LWC1", "LDC1"):
        for fr in (0, 1):
            for ft in (0, 1):
                for action, (code, ce) in expected_fault.items():
                    _, traced = repeated_case(exe, load_op, fr, ft, "SWC1", fr, ft, action)
                    assert traced["events"] == [], traced
                    assert (traced["exception"], traced["coprocessor_error"]) == (code, ce), traced
                    assert traced["after_load_f0"] == traced["before_f0"] and traced["after_load_f1"] == traced["before_f1"], traced
                    assert traced["destination"] == EE, traced
                    receipts.append({
                        "load_op": load_op, "fr": fr, "ft": ft, "fault": action,
                        "exception": code, "coprocessor_error": ce,
                    })
                    fault_cases += 1
                    logical_cases += 1

    # These are the adversarial heart of the experiment: at least the two
    # deliberate FR-flip decoys have load and store values equal while byte
    # generations prove the store did not come from that load.
    assert false_value_matches >= 2, false_value_matches
    assert mixed_outputs > 0 and full_load_outputs > 0, (mixed_outputs, full_load_outputs)
    assert overwrite_cases == 8 and fault_cases == 24

    encoded = (json.dumps(receipts, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    print(f"PASS: {logical_cases} logical decoded pinned-ares COP1 lineage cases")
    print(f"false_value_matches={false_value_matches} mixed_outputs={mixed_outputs} full_load_outputs={full_load_outputs}")
    print(f"model_cases={model_count} model_sha256={model_digest}")
    print("results_sha256=" + digest)


if __name__ == "__main__":
    main()
